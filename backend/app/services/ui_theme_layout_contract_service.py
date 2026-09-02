from __future__ import annotations

import asyncio
import html as html_lib
import re

from app.services.ui_theme_fetch_context_service import (
    analyze_theme_source_context,
    fetch_theme_source_context,
)


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
        "version": 2,
        "source": "SHARED_HTML_CSS_LAYOUT_ANALYSIS",
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
    """Analyze Theme + interaction + layout from one shared network context.

    The HTML is fetched once. Only rel=stylesheet resources are selected and up to six
    CSS files are downloaded with bounded concurrency. Theme token analysis and layout
    analysis then reuse the same HTML/CSS text, eliminating the previous second URL pass.
    CPU-heavy regex work is kept off the FastAPI event loop.
    """
    context = await fetch_theme_source_context(url)
    analysis = await analyze_theme_source_context(context)
    html = str(context.get("html") or "")
    css_text = str(context.get("css_text") or "")
    contract = await asyncio.to_thread(build_layout_contract, html, css_text)

    layout = dict(analysis.get("layout_rules") or {})
    layout["layoutContract"] = contract
    layout["mobileDrawerSide"] = ((contract.get("mobile") or {}).get("drawer") or {}).get("side", "left")
    layout["mobileDrawerWidth"] = ((contract.get("mobile") or {}).get("drawer") or {}).get("width", "82%")
    layout["desktopSidebarPresent"] = bool((contract.get("desktop") or {}).get("sidebar_present"))
    navigation = dict(contract.get("navigation") or {})
    layout["sourceNavigationItems"] = list(navigation.get("items") or [])
    layout["sourceNavigationItemDetails"] = list(navigation.get("item_details") or [])
    layout["sourceNavigationPresentation"] = dict(navigation.get("presentation") or {})
    analysis["layout_rules"] = layout

    source_meta = dict(analysis.get("source_meta") or {})
    source_meta["layout_contract"] = contract
    source_meta["layout_css_files"] = int(context.get("css_files") or 0)
    source_meta["network_passes"] = 1
    source_meta["stylesheet_only"] = True
    source_meta["parallel_stylesheet_fetch"] = True
    source_meta["stylesheet_candidates"] = len(context.get("stylesheet_urls") or [])
    source_meta["fetch_warnings"] = list(context.get("warnings") or [])
    analysis["source_meta"] = source_meta
    return analysis
