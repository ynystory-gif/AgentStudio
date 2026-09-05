from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin

import httpx

from app.services.ui_theme_killable_process_service import run_theme_worker
from app.services.ui_theme_service import _safe_get, validate_public_theme_url

_STYLESHEET_PATTERNS = (
    re.compile(r"<link[^>]+rel=[\"'][^\"']*stylesheet[^\"']*[\"'][^>]+href=[\"']([^\"']+)[\"']", re.IGNORECASE),
    re.compile(r"<link[^>]+href=[\"']([^\"']+)[\"'][^>]+rel=[\"'][^\"']*stylesheet[^\"']*[\"']", re.IGNORECASE),
)

_MAX_HTML_BYTES = 1_000_000
_MAX_CSS_BYTES = 500_000
_MAX_STYLESHEETS = 6
_CSS_FETCH_CONCURRENCY = 3
# v5.429: token extraction is critical-path work, so it may use the full backend
# 5-minute hard deadline. Owning-job cancellation still kills the worker process tree
# immediately when 300 seconds is reached.
_STATIC_WORKER_TIMEOUT_SECONDS = 300


def _stylesheet_urls(html: str, final_url: str) -> list[str]:
    hrefs: list[str] = []
    for pattern in _STYLESHEET_PATTERNS:
        hrefs.extend(pattern.findall(str(html or "")))
    result: list[str] = []
    for href in hrefs:
        absolute = urljoin(final_url, href)
        if absolute not in result:
            result.append(absolute)
        if len(result) >= _MAX_STYLESHEETS:
            break
    return result


async def fetch_theme_source_context(url: str) -> dict:
    """Fetch one HTML document and only its stylesheet links."""
    target = await validate_public_theme_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 THEANOVA-AgentStudio-ThemeImporter/5.450",
        "Accept": "text/html,application/xhtml+xml,text/css,*/*;q=0.6",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Cache-Control": "no-cache",
    }
    timeout = httpx.Timeout(12.0, connect=7.0)
    warnings: list[str] = []
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response, final_url = await _safe_get(client, target)
        content_type = (response.headers.get("content-type") or "").casefold()
        html = response.text[:_MAX_HTML_BYTES]
        looks_html = bool(re.search(r"<(?:!doctype\s+html|html|head|body)\b", html[:5000], re.IGNORECASE))
        if "text/html" not in content_type and "application/xhtml" not in content_type and not looks_html:
            raise ValueError("HTML 웹페이지 URL을 입력하세요.")

        css_urls = _stylesheet_urls(html, final_url)
        semaphore = asyncio.Semaphore(_CSS_FETCH_CONCURRENCY)

        async def fetch_css(index: int, css_url: str) -> tuple[int, str, str | None]:
            async with semaphore:
                try:
                    css_response, resolved = await _safe_get(client, css_url)
                    css_type = (css_response.headers.get("content-type") or "").casefold()
                    path = resolved.casefold().split("?", 1)[0]
                    if "css" not in css_type and not path.endswith(".css"):
                        return index, "", f"stylesheet 후보가 CSS가 아니어서 제외: {css_url}"
                    return index, css_response.text[:_MAX_CSS_BYTES], None
                except Exception as exc:
                    return index, "", f"stylesheet 다운로드 실패: {css_url} · {str(exc) or type(exc).__name__}"

        results = await asyncio.gather(*(fetch_css(i, item) for i, item in enumerate(css_urls))) if css_urls else []

    css_rows: list[tuple[int, str]] = []
    for index, text, warning in results:
        if warning:
            warnings.append(warning)
        if text:
            css_rows.append((index, text))
    css_rows.sort(key=lambda item: item[0])
    css_parts = [html, *[text for _, text in css_rows]]
    return {
        "requested_url": url,
        "final_url": final_url,
        "html": html,
        "css_text": "\n".join(css_parts),
        "stylesheet_urls": css_urls,
        "css_files": len(css_rows),
        "warnings": warnings,
        "fetch_mode": "single_html_parallel_stylesheets",
        "css_concurrency": _CSS_FETCH_CONCURRENCY,
    }


async def analyze_theme_source_context(context: dict) -> dict:
    """Run regex/token extraction in a disposable, killable Python process."""
    html = str(context.get("html") or "")
    css_text = str(context.get("css_text") or "")
    worker = await run_theme_worker(
        "static_analysis",
        {"html": html, "css_text": css_text},
        timeout=_STATIC_WORKER_TIMEOUT_SECONDS,
    )
    analysis = dict(worker.get("analysis") or {})
    interaction_structure = dict(worker.get("interaction_structure") or {})
    analysis["analysis_source"] = "URL"
    analysis["source_url"] = str(context.get("final_url") or context.get("requested_url") or "")
    analysis["source_meta"] = {
        "css_files": int(context.get("css_files") or 0),
        "stylesheet_candidates": len(context.get("stylesheet_urls") or []),
        "analysis": "single-fetch HTML/CSS killable-process interaction-state design-token extraction",
        "content_copied": False,
        "interaction_structure": interaction_structure,
        "evidence_count": len(((analysis.get("component_rules") or {}).get("_evidence") or {})),
        "fetch_mode": context.get("fetch_mode") or "",
        "css_concurrency": int(context.get("css_concurrency") or 0),
        "fetch_warnings": list(context.get("warnings") or []),
        "worker_mode": "KILLABLE_PROCESS",
        "worker_timeout_seconds": _STATIC_WORKER_TIMEOUT_SECONDS,
    }
    return analysis
