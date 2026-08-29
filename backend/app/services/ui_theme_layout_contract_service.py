from __future__ import annotations

import asyncio
import html as html_lib
import re
from urllib.parse import urljoin

import httpx

from app.services.ui_theme_service import _safe_get, analyze_theme_from_url, validate_public_theme_url


_DRAWER_SELECTOR_TOKENS = (
    "drawer", "offcanvas", "off-canvas", "mobile-menu", "mobile_nav", "mobile-nav",
    "side-menu", "side_menu", "sidebar", "sidenav", "sheet", "menu-panel", "nav-panel",
)
_OVERLAY_SELECTOR_TOKENS = ("overlay", "backdrop", "scrim", "drawer-mask", "menu-mask")


def _css_blocks(css_text: str):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", str(css_text or ""), re.DOTALL):
        yield match.group(1).strip(), match.group(2).strip()


def _drawer_score(selector: str) -> int:
    value = str(selector or "").casefold()
    score = 0
    for token in _DRAWER_SELECTOR_TOKENS:
        if token in value:
            score += 8
    if "mobile" in value:
        score += 5
    if "menu" in value or "nav" in value:
        score += 3
    return score


def _infer_drawer(css_text: str) -> dict:
    left_score = 0
    right_score = 0
    widths: list[tuple[int, str]] = []
    evidence: list[str] = []

    for selector, body in _css_blocks(css_text):
        score = _drawer_score(selector)
        if score <= 0:
            continue
        compact = re.sub(r"\s+", " ", body).casefold()
        side_hit = False
        if re.search(r"(?:^|;)\s*left\s*:\s*0(?:px|rem|em|%|vw)?\b", compact):
            left_score += score + 7
            side_hit = True
        if re.search(r"(?:^|;)\s*right\s*:\s*0(?:px|rem|em|%|vw)?\b", compact):
            right_score += score + 7
            side_hit = True
        if "translatex(-100%" in compact or "translate3d(-100%" in compact:
            left_score += score + 5
            side_hit = True
        if "translatex(100%" in compact or "translate3d(100%" in compact:
            right_score += score + 5
            side_hit = True
        if re.search(r"\binset(?:-inline-start)?\s*:\s*[^;]*\b0\b", compact) and "right:" not in compact:
            left_score += max(2, score // 2)
        width = re.search(r"(?:^|;)\s*(?:width|max-width)\s*:\s*([0-9.]+(?:px|rem|em|vw|%))", compact)
        if width:
            widths.append((score + (4 if side_hit else 0), width.group(1)))
        if side_hit and len(evidence) < 4:
            evidence.append(selector[:180])

    side = "left" if left_score >= right_score else "right"
    confidence = 0.55
    if left_score or right_score:
        total = max(1, left_score + right_score)
        confidence = min(0.98, 0.62 + abs(left_score - right_score) / total * 0.34)
    width = sorted(widths, reverse=True)[0][1] if widths else "82%"
    return {
        "side": side,
        "width": width,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "left_score": left_score,
        "right_score": right_score,
    }


def _infer_overlay(css_text: str) -> dict:
    detected = False
    color = "rgba(0,0,0,.42)"
    for selector, body in _css_blocks(css_text):
        value = selector.casefold()
        if not any(token in value for token in _OVERLAY_SELECTOR_TOKENS):
            continue
        detected = True
        match = re.search(r"background(?:-color)?\s*:\s*(rgba?\([^;]+\)|#[0-9a-fA-F]{3,8})", body, re.IGNORECASE)
        if match:
            color = match.group(1).strip()
            break
    return {"detected": detected, "color": color}


def _clean_text(raw: str) -> str:
    value = re.sub(r"<[^>]+>", " ", raw or "")
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_menu_items(html: str) -> list[str]:
    source = str(html or "")[:1_000_000]
    regions = re.findall(r"<(?:nav|aside)\b[^>]*>(.*?)</(?:nav|aside)>", source, re.IGNORECASE | re.DOTALL)
    scan = "\n".join(regions) if regions else source
    candidates = re.findall(r"<(?:a|button)\b[^>]*>(.*?)</(?:a|button)>", scan, re.IGNORECASE | re.DOTALL)
    result: list[str] = []
    blocked = {"close", "open", "menu", "toggle", "login", "log in", "sign in", "sign up"}
    for raw in candidates:
        label = _clean_text(raw)
        if not label or len(label) > 48 or label.casefold() in blocked:
            continue
        if not re.search(r"[A-Za-z0-9가-힣]", label):
            continue
        if label not in result:
            result.append(label)
        if len(result) >= 10:
            break
    return result


def _infer_breakpoint(css_text: str) -> int:
    values = []
    for item in re.findall(r"@media[^{}]{0,180}max-width\s*:\s*([0-9.]+)px", css_text, re.IGNORECASE):
        try:
            number = int(round(float(item)))
        except ValueError:
            continue
        if 480 <= number <= 1280:
            values.append(number)
    if not values:
        return 768
    return min(values, key=lambda value: abs(value - 768))


def build_layout_contract(html: str, css_text: str) -> dict:
    source = str(html or "")[:1_000_000]
    drawer = _infer_drawer(css_text)
    overlay = _infer_overlay(css_text)
    aside_detected = bool(re.search(r"<aside\b", source, re.IGNORECASE))
    header_detected = bool(re.search(r"<header\b", source, re.IGNORECASE))
    menu_items = _extract_menu_items(source)
    return {
        "version": 1,
        "source": "HTML_CSS_LAYOUT_ANALYSIS",
        "header": {"detected": header_detected},
        "desktop": {"sidebar_present": aside_detected},
        "mobile": {
            "breakpoint": _infer_breakpoint(css_text),
            "drawer": {
                "detected": bool(drawer["left_score"] or drawer["right_score"]),
                "side": drawer["side"],
                "width": drawer["width"],
                "overlay": overlay,
                "confidence": drawer["confidence"],
                "evidence": drawer["evidence"],
            },
        },
        "navigation": {
            "items": menu_items,
            "use_source_items_in_preview": bool(menu_items),
        },
    }


async def analyze_theme_with_layout_contract(url: str) -> dict:
    """Analyze design tokens plus actual navigation/layout behavior from the same public URL.

    Network work remains async. CPU-heavy HTML/CSS regex analysis is moved to a worker
    thread so the FastAPI event loop stays responsive and asyncio timeouts/cancellation
    can still fire while large stylesheets are being inspected.
    """
    analysis = await analyze_theme_from_url(url)
    target = await validate_public_theme_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 THEANOVA-AgentStudio-LayoutImporter/5.429",
        "Accept": "text/html,application/xhtml+xml,text/css,*/*;q=0.6",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
    }
    html = ""
    css_parts: list[str] = []
    fetched_css = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=7.0), headers=headers) as client:
            response, final_url = await _safe_get(client, target)
            html = response.text[:1_000_000]
            css_parts.append(html)
            hrefs = re.findall(r"<link[^>]+href=[\"']([^\"']+)[\"'][^>]*>", html, re.IGNORECASE)
            for href in list(dict.fromkeys(hrefs))[:12]:
                css_url = urljoin(final_url, href)
                try:
                    css_response, _ = await _safe_get(client, css_url)
                    content_type = (css_response.headers.get("content-type") or "").casefold()
                    if "css" not in content_type and not css_url.casefold().split("?", 1)[0].endswith(".css"):
                        continue
                    css_parts.append(css_response.text[:500_000])
                    fetched_css += 1
                    if fetched_css >= 6:
                        break
                except Exception:
                    continue
    except Exception:
        html = ""
        css_parts = []

    css_text = "\n".join(css_parts)
    contract = await asyncio.to_thread(build_layout_contract, html, css_text)
    layout = dict(analysis.get("layout_rules") or {})
    layout["layoutContract"] = contract
    layout["mobileDrawerSide"] = ((contract.get("mobile") or {}).get("drawer") or {}).get("side", "left")
    layout["mobileDrawerWidth"] = ((contract.get("mobile") or {}).get("drawer") or {}).get("width", "82%")
    layout["desktopSidebarPresent"] = bool((contract.get("desktop") or {}).get("sidebar_present"))
    layout["sourceNavigationItems"] = list((contract.get("navigation") or {}).get("items") or [])
    analysis["layout_rules"] = layout
    source_meta = dict(analysis.get("source_meta") or {})
    source_meta["layout_contract"] = contract
    source_meta["layout_css_files"] = fetched_css
    analysis["source_meta"] = source_meta
    return analysis
