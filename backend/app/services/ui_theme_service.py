from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from collections import Counter
from urllib.parse import urljoin, urlparse

import httpx


_COLOR_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:#[0-9a-fA-F]{3,8}\b|rgba?\([^)]{3,80}\))"
)
_FONT_RE = re.compile(r"font-family\s*:\s*([^;}]+)", re.IGNORECASE)
_RADIUS_RE = re.compile(r"border-radius\s*:\s*([0-9.]+)px", re.IGNORECASE)
_STYLESHEET_RE = re.compile(
    r"<link[^>]+rel=[\"'][^\"']*stylesheet[^\"']*[\"'][^>]+href=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_STYLESHEET_RE_ALT = re.compile(
    r"<link[^>]+href=[\"']([^\"']+)[\"'][^>]+rel=[\"'][^\"']*stylesheet[^\"']*[\"']",
    re.IGNORECASE,
)


def _clamp(value: int) -> int:
    return max(0, min(255, int(value)))


def _normalize_color(value: str) -> str | None:
    raw = str(value or "").strip().lower()
    if raw.startswith("#"):
        digits = raw[1:]
        if len(digits) in {3, 4}:
            digits = "".join(ch * 2 for ch in digits[:3])
        elif len(digits) in {6, 8}:
            digits = digits[:6]
        else:
            return None
        try:
            int(digits, 16)
        except ValueError:
            return None
        return f"#{digits}"
    match = re.match(r"rgba?\(\s*([0-9.]+)[, ]+\s*([0-9.]+)[, ]+\s*([0-9.]+)", raw)
    if match:
        return "#%02x%02x%02x" % tuple(_clamp(float(v)) for v in match.groups())
    return None


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")[:6]
    return int(value[:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _luminance(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _saturation(hex_color: str) -> float:
    r, g, b = (v / 255.0 for v in _rgb(hex_color))
    high, low = max(r, g, b), min(r, g, b)
    return 0.0 if high == low else (high - low) / max(high, 0.001)


def _default_tokens() -> dict:
    return {
        "colors": {
            "primary": "#2563eb",
            "secondary": "#64748b",
            "background": "#f8fafc",
            "surface": "#ffffff",
            "textPrimary": "#0f172a",
            "textSecondary": "#475569",
            "border": "#dbe4ee",
            "success": "#16a34a",
            "danger": "#dc2626",
        },
        "typography": {
            "fontFamily": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "headingWeight": 700,
            "bodyWeight": 400,
        },
        "radius": {"button": 8, "card": 12, "input": 8},
        "shadow": {"card": "0 8px 24px rgba(15,23,42,.08)"},
        "spacing": {"unit": 4, "density": "comfortable"},
    }


def build_rules(tokens: dict) -> tuple[dict, dict]:
    colors = (tokens or {}).get("colors") or {}
    radius = (tokens or {}).get("radius") or {}
    component_rules = {
        "button": {
            "background": colors.get("primary", "#2563eb"),
            "color": "#ffffff",
            "radius": radius.get("button", 8),
        },
        "card": {
            "background": colors.get("surface", "#ffffff"),
            "border": colors.get("border", "#dbe4ee"),
            "radius": radius.get("card", 12),
        },
        "input": {
            "background": colors.get("surface", "#ffffff"),
            "border": colors.get("border", "#dbe4ee"),
            "radius": radius.get("input", 8),
        },
        "header": {
            "background": colors.get("surface", "#ffffff"),
            "accent": colors.get("primary", "#2563eb"),
        },
        "sidebar": {
            "background": colors.get("background", "#f8fafc"),
            "active": colors.get("primary", "#2563eb"),
        },
        "menu": {
            "normal": {
                "background": colors.get("surface", colors.get("background", "#ffffff")),
                "color": colors.get("textPrimary", "#0f172a"),
                "border": colors.get("border", "#dbe4ee"),
                "radius": radius.get("button", 8),
            },
            "hover": {
                "background": colors.get("primary", "#2563eb"),
                "color": "#ffffff",
                "border": colors.get("primary", "#2563eb"),
                "radius": radius.get("button", 8),
            },
            "active": {
                "background": colors.get("primary", "#2563eb"),
                "color": "#ffffff",
                "border": colors.get("primary", "#2563eb"),
                "radius": radius.get("button", 8),
            },
            "source": "TOKEN_INFERRED",
        },
        "submenu": {
            "normal": {"background": colors.get("surface", "#ffffff"), "color": colors.get("textPrimary", "#0f172a"), "border": colors.get("border", "#dbe4ee"), "radius": radius.get("card", 12)},
            "hover": {"background": colors.get("primary", "#2563eb"), "color": "#ffffff"},
            "source": "TOKEN_INFERRED",
        },
        "user_menu": {
            "normal": {"background": colors.get("surface", "#ffffff"), "color": colors.get("textPrimary", "#0f172a"), "border": colors.get("border", "#dbe4ee"), "radius": radius.get("card", 12)},
            "hover": {"background": colors.get("background", "#f8fafc"), "color": colors.get("textPrimary", "#0f172a")},
            "source": "TOKEN_INFERRED",
        },
        "tab": {
            "normal": {"background": "transparent", "color": colors.get("textSecondary", "#475569")},
            "hover": {"color": colors.get("primary", "#2563eb")},
            "active": {"color": colors.get("primary", "#2563eb"), "border": colors.get("primary", "#2563eb")},
            "source": "TOKEN_INFERRED",
        },
    }
    layout_rules = {
        "headerHeight": 64,
        "sidebarWidth": 240,
        "contentMaxWidth": 1440,
        "contentGap": 20,
    }
    return component_rules, layout_rules



def _declaration_map(body: str) -> dict:
    result: dict[str, str | int | float] = {}
    for chunk in str(body or "").split(";"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        name = key.strip().lower()
        raw = value.strip()
        if not name or not raw:
            continue
        if name in {"background", "background-color"}:
            color_match = _COLOR_RE.search(raw)
            color = _normalize_color(color_match.group(0)) if color_match else None
            if color:
                result["background"] = color
        elif name == "color":
            color_match = _COLOR_RE.search(raw)
            color = _normalize_color(color_match.group(0)) if color_match else None
            if color:
                result["color"] = color
        elif name in {"border", "border-color"}:
            color_match = _COLOR_RE.search(raw)
            color = _normalize_color(color_match.group(0)) if color_match else None
            if color:
                result["border"] = color
        elif name == "border-radius":
            match = re.search(r"([0-9.]+)px", raw, re.IGNORECASE)
            if match:
                try:
                    result["radius"] = int(round(float(match.group(1))))
                except ValueError:
                    pass
        elif name == "font-weight":
            match = re.search(r"\b([1-9]00)\b", raw)
            if match:
                result["fontWeight"] = int(match.group(1))
            elif raw.lower() in {"bold", "bolder"}:
                result["fontWeight"] = 700
        elif name == "text-decoration":
            result["textDecoration"] = raw[:80]
        elif name == "box-shadow":
            result["boxShadow"] = raw[:180]
        elif name == "transition":
            result["transition"] = raw[:180]
        elif name == "transform":
            result["transform"] = raw[:120]
        elif name == "opacity":
            try:
                result["opacity"] = max(0.0, min(1.0, float(raw.split()[0])))
            except (TypeError, ValueError):
                pass
        elif name == "font-size":
            match = re.search(r"([0-9.]+)px", raw, re.IGNORECASE)
            if match:
                try:
                    result["fontSize"] = float(match.group(1))
                except ValueError:
                    pass
        elif name == "line-height":
            result["lineHeight"] = raw[:60]
        elif name in {"padding", "padding-inline", "padding-block"}:
            result["padding"] = raw[:100]
        elif name == "outline":
            result["outline"] = raw[:120]
    return result


def _menu_selector_score(selector: str) -> int:
    value = str(selector or "").casefold()
    score = 0
    for token, weight in (
        ("sidebar", 8), ("sidenav", 8), ("side-nav", 8), ("navigation", 7),
        ("navbar", 7), ("nav-item", 7), ("nav-link", 7), ("menu-item", 7),
        ("menu", 6), (" nav ", 5), ("nav>", 5), ("nav.", 5), ("header", 3),
        (" a", 1),
    ):
        if token in value:
            score += weight
    if ":hover" in value:
        score += 3
    if any(token in value for token in (".active", "[aria-current", ":focus", ":selected")):
        score += 3
    return score


def extract_menu_rules(css_text: str, tokens: dict) -> dict:
    """Extract menu/navigation normal, hover and active states from CSS when possible.

    This intentionally converts CSS into reusable design rules instead of copying selectors
    or page content. If exact states cannot be found, token-derived defaults remain available.
    """
    defaults = build_rules(tokens)[0].get("menu") or {}
    best: dict[str, tuple[int, dict]] = {}
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", str(css_text or ""), re.DOTALL):
        selector = match.group(1).strip()
        score = _menu_selector_score(selector)
        if score <= 0:
            continue
        props = _declaration_map(match.group(2))
        if not props:
            continue
        selector_lower = selector.casefold()
        if ":hover" in selector_lower:
            state = "hover"
        elif any(token in selector_lower for token in (".active", "[aria-current", ":focus", ":selected")):
            state = "active"
        else:
            state = "normal"
        previous = best.get(state)
        if previous is None or score > previous[0]:
            best[state] = (score, props)

    result = {
        "normal": {**(defaults.get("normal") or {}), **(best.get("normal", (0, {}))[1])},
        "hover": {**(defaults.get("hover") or {}), **(best.get("hover", (0, {}))[1])},
        "active": {**(defaults.get("active") or {}), **(best.get("active", (0, {}))[1])},
        "source": "CSS_SELECTOR_ANALYSIS" if best else "TOKEN_INFERRED",
    }
    return result




def _selector_state(selector: str) -> str:
    value = str(selector or "").casefold()
    if ":hover" in value:
        return "hover"
    if ":active" in value or ".pressed" in value or "[aria-pressed=\"true\"]" in value or "[aria-pressed='true']" in value:
        return "pressed"
    if ":focus" in value or ":focus-visible" in value or ":focus-within" in value:
        return "focus"
    if ":disabled" in value or "[disabled" in value or ".disabled" in value:
        return "disabled"
    if any(token in value for token in (".active", ".selected", "[aria-current", "[aria-selected=\"true\"]", "[aria-selected='true']")):
        return "active"
    return "normal"


def _component_selector_score(selector: str, keywords: tuple[str, ...]) -> int:
    value = f" {str(selector or '').casefold()} "
    score = 0
    for keyword in keywords:
        if keyword in value:
            score += 8 if keyword.startswith((".", "#", "[")) else 5
    if score <= 0:
        return 0
    if any(token in value for token in (":hover", ":focus", ":active", ".active", ".selected", ":disabled")):
        score += 2
    return score


def _extract_component_states(css_text: str, keywords: tuple[str, ...], *, component: str) -> tuple[dict, dict]:
    """Return reusable state rules plus evidence without copying source content.

    The selected CSS selector is kept only as provenance so users can see whether a
    preview state came from a real public-site rule or a fallback inference.
    """
    best: dict[str, tuple[int, dict, str]] = {}
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", str(css_text or ""), re.DOTALL):
        selector = match.group(1).strip()
        score = _component_selector_score(selector, keywords)
        if score <= 0:
            continue
        props = _declaration_map(match.group(2))
        if not props:
            continue
        state = _selector_state(selector)
        previous = best.get(state)
        if previous is None or score > previous[0]:
            best[state] = (score, props, selector[:240])

    rules: dict = {}
    evidence: dict = {}
    for state, (score, props, selector) in best.items():
        rules[state] = props
        confidence = min(0.99, 0.70 + min(score, 24) / 100.0)
        evidence[f"{component}.{state}"] = {
            "status": "confirmed",
            "source": "URL_CSS_SELECTOR",
            "selector": selector,
            "confidence": round(confidence, 2),
        }
    if rules:
        rules["source"] = "CSS_SELECTOR_ANALYSIS"
    return rules, evidence


def extract_interaction_rules(css_text: str, tokens: dict) -> tuple[dict, dict]:
    """Extract interaction-oriented styles used by the interactive Theme preview."""
    defaults, _ = build_rules(tokens)
    definitions = {
        "menu": (".nav-item", ".nav-link", ".menu-item", ".sidebar", ".sidenav", ".navbar", " nav "),
        "submenu": (".dropdown-menu", ".dropdown-item", ".submenu", ".sub-menu", ".menu-popup", "[role=menu]"),
        "user_menu": (".user-menu", ".profile-menu", ".account-menu", ".user-dropdown", ".profile-dropdown", ".avatar-menu", ".account-dropdown"),
        "button": (" button", ".btn", "[role=button]"),
        "input": (" input", " textarea", " select", ".form-control", ".input"),
        "card": (".card", ".panel", ".tile", ".surface"),
        "tab": (".tab", ".tabs", "[role=tab]"),
    }
    components: dict = {}
    evidence: dict = {}
    for component, keywords in definitions.items():
        extracted, found = _extract_component_states(css_text, keywords, component=component)
        base = defaults.get(component) if isinstance(defaults.get(component), dict) else {}
        if extracted:
            merged = dict(base or {})
            for state, props in extracted.items():
                if state == "source":
                    continue
                if isinstance(props, dict):
                    merged[state] = {**(merged.get(state) or {}), **props}
            merged["source"] = "CSS_SELECTOR_ANALYSIS"
            components[component] = merged
            evidence.update(found)
    return components, evidence


def analyze_html_interactions(html: str) -> dict:
    source = str(html or "")[:1_000_000]
    checks = {
        "submenu": (r"aria-haspopup\s*=", r"\bdropdown\b", r"\bsubmenu\b", r"\bsub-menu\b", r"role=[\"']menu[\"']"),
        "user_menu": (r"\buser[-_ ]?menu\b", r"\bprofile[-_ ]?menu\b", r"\baccount[-_ ]?menu\b", r"\bavatar\b"),
        "tabs": (r"role=[\"']tab[\"']", r"\btablist\b", r"class=[\"'][^\"']*\btabs?\b"),
    }
    result = {}
    for key, patterns in checks.items():
        hits = sum(1 for pattern in patterns if re.search(pattern, source, re.IGNORECASE))
        result[key] = {"detected": hits > 0, "signals": hits}
    return result

def _most_common(values: list):
    normalized = [value for value in values if value not in (None, "", {}, [])]
    if not normalized:
        return None
    counts: Counter = Counter()
    original: dict[str, object] = {}
    for value in normalized:
        key = repr(value)
        counts[key] += 1
        original.setdefault(key, value)
    key = counts.most_common(1)[0][0]
    return original[key]


def _median_number(values: list, default: float | int):
    numbers = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not numbers:
        return default
    return numbers[len(numbers) // 2]


def merge_theme_analyses(analyses: list[dict]) -> dict:
    """Merge URL CSS analysis and one-to-three screenshot analyses into one canonical Theme."""
    rows = [row for row in analyses or [] if isinstance(row, dict)]
    if not rows:
        base = _default_tokens()
        components, layout = build_rules(base)
        return {"tokens": base, "component_rules": components, "layout_rules": layout, "preview_colors": []}

    # Prefer CSS-derived typography/menu semantics, but use consensus across all sources for colors.
    url_rows = [row for row in rows if str(row.get("analysis_source") or "").upper() == "URL"]
    first = (url_rows or rows)[0]
    first_tokens = first.get("tokens") or _default_tokens()
    tokens = _default_tokens()

    color_keys = set(tokens["colors"].keys())
    for row in rows:
        color_keys.update(((row.get("tokens") or {}).get("colors") or {}).keys())
    for key in color_keys:
        value = _most_common([((row.get("tokens") or {}).get("colors") or {}).get(key) for row in rows])
        if value:
            tokens["colors"][key] = value

    typography_rows = url_rows or rows
    for key in set(tokens["typography"].keys()).union(*[set(((r.get("tokens") or {}).get("typography") or {}).keys()) for r in typography_rows]):
        value = _most_common([((row.get("tokens") or {}).get("typography") or {}).get(key) for row in typography_rows])
        if value is not None:
            tokens["typography"][key] = value

    for key in ("button", "card", "input"):
        tokens["radius"][key] = int(round(_median_number([
            ((row.get("tokens") or {}).get("radius") or {}).get(key) for row in rows
        ], tokens["radius"][key])))

    shadow = _most_common([((row.get("tokens") or {}).get("shadow") or {}).get("card") for row in (url_rows or rows)])
    if shadow:
        tokens["shadow"]["card"] = shadow

    components, layout = build_rules(tokens)
    # First merge generic component rules from screenshots/URL, then strongly prefer CSS menu states.
    for row in rows:
        for component, rules in (row.get("component_rules") or {}).items():
            if component == "menu":
                continue
            if isinstance(rules, dict):
                components[component] = {**(components.get(component) or {}), **rules}
    menu_candidates = [
        (row.get("component_rules") or {}).get("menu")
        for row in (url_rows or rows)
        if isinstance((row.get("component_rules") or {}).get("menu"), dict)
    ]
    if menu_candidates:
        menu = components.get("menu") or {}
        if url_rows:
            # URL CSS selectors are the strongest source for hover/active semantics.
            candidate = menu_candidates[0]
            for state in ("normal", "hover", "active"):
                if isinstance(candidate.get(state), dict):
                    menu[state] = {**(menu.get(state) or {}), **candidate[state]}
            menu["source"] = candidate.get("source") or "CSS_SELECTOR_ANALYSIS"
        else:
            # For 1~3 screenshots, use consensus across the inferred menu regions/states.
            for state in ("normal", "hover", "active"):
                state_rows = [candidate.get(state) for candidate in menu_candidates if isinstance(candidate.get(state), dict)]
                if not state_rows:
                    continue
                merged_state = dict(menu.get(state) or {})
                keys = set().union(*(set(item.keys()) for item in state_rows))
                for key in keys:
                    value = _most_common([item.get(key) for item in state_rows])
                    if value is not None:
                        merged_state[key] = value
                menu[state] = merged_state
            menu["source"] = "IMAGE_MULTI_REFERENCE" if len(menu_candidates) > 1 else (menu_candidates[0].get("source") or "IMAGE_INFERRED")
        components["menu"] = menu

    # Use the first URL layout as a semantic baseline; screenshot values fill missing fields.
    for row in rows:
        for key, value in (row.get("layout_rules") or {}).items():
            if key not in layout or layout[key] in (None, ""):
                layout[key] = value
    if url_rows:
        layout.update(url_rows[0].get("layout_rules") or {})

    preview: list[str] = []
    for row in rows:
        for color in row.get("preview_colors") or []:
            if color and color not in preview:
                preview.append(color)
            if len(preview) >= 8:
                break
        if len(preview) >= 8:
            break

    evidence: dict = {}
    for row in rows:
        for key, item in (((row.get("component_rules") or {}).get("_evidence") or {}).items()):
            if isinstance(item, dict):
                current = evidence.get(key)
                if current is None or float(item.get("confidence") or 0) >= float(current.get("confidence") or 0):
                    evidence[key] = dict(item)
        role = str(row.get("reference_role") or "").strip().lower()
        file_name = str(row.get("file_name") or "").strip()
        role_map = {
            "default":"menu.normal", "menu_hover":"menu.hover", "menu_active":"menu.active",
            "submenu_open":"submenu.normal", "user_menu_open":"user_menu.normal",
            "button_hover":"button.hover", "input_focus":"input.focus", "mobile":"layout.mobile",
        }
        if role in role_map:
            evidence[role_map[role]] = {
                "status":"reference", "source":"SCREENSHOT_REFERENCE", "reference_role":role,
                "file_name":file_name, "confidence":0.78 if role not in {"default","mobile"} else 0.72,
            }
    components["_evidence"] = evidence
    components["_source_summary"] = {
        "url_css": bool(url_rows),
        "screenshots": len([row for row in rows if str(row.get("analysis_source") or "").upper()=="IMAGE"]),
        "confirmed_states": sum(1 for item in evidence.values() if str(item.get("status"))=="confirmed"),
        "reference_states": sum(1 for item in evidence.values() if str(item.get("status"))=="reference"),
    }
    return {
        "tokens": tokens,
        "component_rules": components,
        "layout_rules": layout,
        "preview_colors": preview,
    }

def analyze_css_text(css_text: str) -> dict:
    tokens = _default_tokens()
    colors = []
    for match in _COLOR_RE.findall(css_text or ""):
        color = _normalize_color(match)
        if color:
            colors.append(color)
    counts = Counter(colors)
    palette = [color for color, _ in counts.most_common(20)]

    if palette:
        darkest = min(palette, key=_luminance)
        lightest = max(palette, key=_luminance)
        saturated = [c for c in palette if 0.12 < _luminance(c) < 0.92 and _saturation(c) >= 0.28]
        primary = max(saturated or palette, key=lambda c: (_saturation(c), counts[c]))
        light_candidates = [c for c in palette if _luminance(c) >= 0.88]
        background = light_candidates[0] if light_candidates else lightest
        surface = lightest
        border_candidates = [c for c in palette if 0.68 <= _luminance(c) <= 0.93 and _saturation(c) < 0.28]
        border = border_candidates[0] if border_candidates else "#dbe4ee"
        text_secondary_candidates = [c for c in palette if 0.18 <= _luminance(c) <= 0.52]
        text_secondary = text_secondary_candidates[0] if text_secondary_candidates else "#475569"
        tokens["colors"].update({
            "primary": primary,
            "background": background,
            "surface": surface,
            "textPrimary": darkest,
            "textSecondary": text_secondary,
            "border": border,
        })

    fonts = [m.strip().strip('"\'') for m in _FONT_RE.findall(css_text or "") if m.strip()]
    if fonts:
        tokens["typography"]["fontFamily"] = Counter(fonts).most_common(1)[0][0][:300]

    radii = []
    for item in _RADIUS_RE.findall(css_text or ""):
        try:
            value = int(round(float(item)))
        except ValueError:
            continue
        if 0 <= value <= 64:
            radii.append(value)
    if radii:
        common = Counter(radii).most_common(1)[0][0]
        tokens["radius"].update({"button": common, "card": common, "input": common})

    if re.search(r"box-shadow\s*:", css_text or "", re.IGNORECASE):
        tokens["shadow"]["card"] = "0 8px 24px rgba(15,23,42,.12)"

    component_rules, layout_rules = build_rules(tokens)
    component_rules["menu"] = extract_menu_rules(css_text, tokens)
    interaction_rules, interaction_evidence = extract_interaction_rules(css_text, tokens)
    for component, rules in interaction_rules.items():
        if component == "menu":
            continue
        component_rules[component] = {**(component_rules.get(component) or {}), **rules}
    menu_source = component_rules.get("menu") or {}
    evidence = dict(interaction_evidence)
    for state in ("normal", "hover", "active"):
        state_rule = menu_source.get(state)
        if isinstance(state_rule, dict) and menu_source.get("source") == "CSS_SELECTOR_ANALYSIS":
            evidence.setdefault(f"menu.{state}", {"status":"confirmed","source":"URL_CSS_SELECTOR","confidence":0.92})
    component_rules["_evidence"] = evidence
    return {
        "tokens": tokens,
        "component_rules": component_rules,
        "layout_rules": layout_rules,
        "preview_colors": (palette[:6] if palette else [
            tokens["colors"]["primary"],
            tokens["colors"]["background"],
            tokens["colors"]["surface"],
            tokens["colors"]["textPrimary"],
        ]),
    }


async def _resolve_public_host(hostname: str) -> None:
    host = (hostname or "").strip().lower()
    if not host or host in {"localhost", "localhost.localdomain"}:
        raise ValueError("로컬/내부 주소는 URL Theme 가져오기에서 사용할 수 없습니다. 로컬 화면은 캡처 이미지로 가져오세요.")
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
        addresses = []
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue
    if not addresses:
        raise ValueError("URL 호스트를 확인할 수 없습니다.")
    for address in addresses:
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            raise ValueError("보안을 위해 사설망/로컬 주소는 URL Theme 가져오기에서 차단합니다. 화면 캡처 이미지를 사용하세요.")


async def validate_public_theme_url(url: str) -> str:
    raw = str(url or "").strip()
    if raw and "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("http 또는 https 웹사이트 URL을 입력하세요.")
    if parsed.username or parsed.password:
        raise ValueError("인증정보가 포함된 URL은 사용할 수 없습니다.")
    await _resolve_public_host(parsed.hostname)
    if parsed.port not in {None, 80, 443}:
        raise ValueError("URL Theme 가져오기는 공개 웹사이트의 80/443 포트만 지원합니다.")
    return raw


async def _safe_get(client: httpx.AsyncClient, url: str, *, max_redirects: int = 3) -> tuple[httpx.Response, str]:
    current = await validate_public_theme_url(url)
    for _ in range(max_redirects + 1):
        response = await client.get(current, follow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location") or ""
            if not location:
                break
            current = await validate_public_theme_url(urljoin(current, location))
            continue
        if response.status_code in {401, 403, 406, 429}:
            raise ValueError(
                f"대상 사이트가 자동 Theme 분석 요청을 차단했습니다(HTTP {response.status_code}). "
                "이 사이트는 화면 캡처 이미지로 Theme을 가져오세요."
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"웹사이트 응답 오류 HTTP {response.status_code}: {current}") from exc
        return response, current
    raise ValueError("리다이렉트가 너무 많아 Theme 분석을 중단했습니다.")


async def analyze_theme_from_url(url: str) -> dict:
    target = await validate_public_theme_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 THEANOVA-AgentStudio-ThemeImporter/5.393",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/css;q=0.8,*/*;q=0.6",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Cache-Control": "no-cache",
    }
    timeout = httpx.Timeout(12.0, connect=7.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        response, final_url = await _safe_get(client, target)
        content_type = (response.headers.get("content-type") or "").lower()
        html = response.text[:1_000_000]
        looks_html = bool(re.search(r"<(?:!doctype\s+html|html|head|body)\b", html[:5000], re.IGNORECASE))
        if "text/html" not in content_type and "application/xhtml" not in content_type and not looks_html:
            raise ValueError("HTML 웹페이지 URL을 입력하세요.")
        css_parts = [html]
        links = []
        for pattern in (_STYLESHEET_RE, _STYLESHEET_RE_ALT):
            links.extend(pattern.findall(html))
        fetched_css = 0
        for href in list(dict.fromkeys(links))[:12]:
            css_url = urljoin(final_url, href)
            parsed_css = urlparse(css_url)
            try:
                # Public CDN stylesheets are allowed after the same SSRF validation.
                css_response, _ = await _safe_get(client, css_url)
                css_type = (css_response.headers.get("content-type") or "").lower()
                if "css" not in css_type and not parsed_css.path.lower().endswith(".css"):
                    continue
                css_parts.append(css_response.text[:500_000])
                fetched_css += 1
                if fetched_css >= 6:
                    break
            except Exception:
                continue

    css_text = "\n".join(css_parts)
    analysis = analyze_css_text(css_text)
    analysis["analysis_source"] = "URL"
    analysis["source_url"] = final_url
    analysis["source_meta"] = {
        "css_files": fetched_css,
        "analysis": "HTML/CSS interaction-state design-token extraction",
        "content_copied": False,
        "interaction_structure": analyze_html_interactions(html),
        "evidence_count": len(((analysis.get("component_rules") or {}).get("_evidence") or {})),
    }
    return analysis
