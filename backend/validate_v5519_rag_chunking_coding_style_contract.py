from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rules_path = ROOT / "backend" / "app" / "data" / "coding_style" / "rules.json"
selector_path = ROOT / "backend" / "app" / "services" / "coding_rule_selector.py"
source_path = ROOT / "backend" / "app" / "data" / "coding_style" / "sources" / "chunking_strategy_comparison_notebook.md"
app_path = ROOT / "frontend" / "src" / "app" / "App.tsx"
routes_path = ROOT / "backend" / "app" / "api" / "routes.py"
main_path = ROOT / "backend" / "app" / "main.py"

rules = json.loads(rules_path.read_text(encoding="utf-8")).get("rules") or []
by_id = {str(rule.get("id")): rule for rule in rules}
required_ids = {f"CS-{number}" for number in range(185, 193)}
missing = sorted(required_ids - set(by_id))
assert not missing, f"missing coding rules: {missing}"

assert by_id["CS-185"]["level"] == "required"
assert "chunking" in by_id["CS-185"]["applies_to"]
assert "start_index" in by_id["CS-188"]["rule"]
assert "Retrieval" in by_id["CS-189"]["rule"]
assert "[0]" in by_id["CS-192"]["rule"]

selector = selector_path.read_text(encoding="utf-8")
for token in (
    '"chunking"',
    '"semantic_chunking"',
    '"korean_text"',
    '"tokenization"',
    '"evaluation"',
):
    assert token in selector, f"selector tag missing: {token}"

assert source_path.exists(), "coding style source evidence missing"
assert any(v in app_path.read_text(encoding="utf-8") for v in ("5.519", "5.520", "5.521"))
assert any(f'version="{v}"' in main_path.read_text(encoding="utf-8") for v in ("5.519", "5.520", "5.521"))
assert any(f'"version": "{v}"' in routes_path.read_text(encoding="utf-8") for v in ("5.519", "5.520", "5.521"))

print("[v5.519] RAG chunking coding style contract PASS")
