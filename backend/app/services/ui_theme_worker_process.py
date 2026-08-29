from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def _static_analysis(payload: dict) -> dict:
    from app.services.ui_theme_service import analyze_css_text, analyze_html_interactions

    html = str(payload.get("html") or "")
    css_text = str(payload.get("css_text") or "")
    analysis = analyze_css_text(css_text)
    interaction_structure = analyze_html_interactions(html)
    return {
        "analysis": analysis,
        "interaction_structure": interaction_structure,
    }


def _layout_contract(payload: dict) -> dict:
    from app.services.ui_theme_layout_contract_service import build_layout_contract

    return build_layout_contract(
        str(payload.get("html") or ""),
        str(payload.get("css_text") or ""),
    )


def _browser_snapshot(payload: dict) -> dict:
    from app.services.ui_theme_browser_analysis_service import _browser_snapshot_sync

    return _browser_snapshot_sync(
        str(payload.get("cdp_endpoint") or ""),
        str(payload.get("target_url") or ""),
    )


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    operation = str(sys.argv[1] or "").strip()
    input_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("worker input must be a JSON object")
        if operation == "static_analysis":
            result = _static_analysis(payload)
        elif operation == "layout_contract":
            result = _layout_contract(payload)
        elif operation == "browser_snapshot":
            result = _browser_snapshot(payload)
        else:
            raise ValueError(f"unknown Theme worker operation: {operation}")
        output_path.write_text(
            json.dumps({"ok": True, "result": result}, ensure_ascii=False),
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        try:
            output_path.write_text(
                json.dumps(
                    {
                        "ok": False,
                        "error": str(exc) or type(exc).__name__,
                        "traceback": traceback.format_exc()[-4000:],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
