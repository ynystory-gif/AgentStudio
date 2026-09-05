from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
rules_path = ROOT / "backend/app/data/coding_style/rules.json"
selector_path = ROOT / "backend/app/services/coding_rule_selector.py"
source_path = ROOT / "backend/app/data/coding_style/sources/document_type_detection_chunking_guide.md"
rules = json.loads(rules_path.read_text(encoding="utf-8"))["rules"]
by_id = {r["id"]: r for r in rules}
assert source_path.exists(), "document type detection source guide missing"
expected = {f"CS-{n}" for n in range(193, 205)}
assert expected <= set(by_id), sorted(expected - set(by_id))
assert len(by_id) == len(rules), "duplicate coding rule IDs"
selector = selector_path.read_text(encoding="utf-8")
for token in ("document_detection", "code_chunking", "structured_data", "mixed_document"):
    assert token in selector, token

import sys
sys.path.insert(0, str(ROOT / "backend"))
from app.services.coding_rule_selector import infer_coding_tags, coding_rules_for_request

def ids(req, path=""):
    return {r["id"] for r in coding_rules_for_request(req, path=path)["rules"]}

base = ids("개발팀 문서를 기반으로 RAG Agent를 만들어줘")
assert "CS-193" in base and "CS-194" in base and "CS-201" in base
mixed = ids("PDF와 Markdown이 섞인 mixed 문서를 section별로 분류하여 RAG로 검색해줘")
assert "CS-197" in mixed
code = ids("TypeScript 소스코드를 AST symbol 단위로 RAG 코드 검색해줘", "src/App.tsx")
assert "CS-199" in code
nb = ids("Notebook ipynb를 RAG에 넣어 셀별로 분류해줘", "lesson.ipynb")
assert "CS-198" in nb
structured = ids("CSV JSON 구조화 데이터를 RAG에 색인해줘")
assert "CS-200" in structured
print("v5.520 RAG document detection contracts: PASS")
print("coding rules:", len(rules))
