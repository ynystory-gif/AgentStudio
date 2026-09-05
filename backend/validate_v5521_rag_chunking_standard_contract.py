from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
rules_path = ROOT / "backend/app/data/coding_style/rules.json"
selector_path = ROOT / "backend/app/services/coding_rule_selector.py"
source_path = ROOT / "backend/app/data/coding_style/sources/rag_chunking_standard.md"

payload = json.loads(rules_path.read_text(encoding="utf-8"))
rules = payload["rules"]
by_id = {r["id"]: r for r in rules}
assert source_path.exists(), "RAG chunking standard source guide missing"
assert payload.get("version") == "5.521"
expected = {f"CS-{n}" for n in range(205, 217)}
assert expected <= set(by_id), sorted(expected - set(by_id))
assert len(by_id) == len(rules), "duplicate coding rule IDs"
selector = selector_path.read_text(encoding="utf-8")
for token in ("parent_child_chunking","hybrid_chunking","incremental_indexing","chunk_versioning","context_expansion","deduplication","auto_tuning","chunk_preview"):
    assert token in selector, token

sys.path.insert(0, str(ROOT / "backend"))
from app.services.coding_rule_selector import coding_rules_for_request

def ids(request: str, path: str = "") -> set[str]:
    return {r["id"] for r in coding_rules_for_request(request, path=path)["rules"]}

base = ids("개발팀 문서를 기반으로 RAG Agent를 만들어줘")
for required in ("CS-205","CS-206","CS-208","CS-211","CS-215"):
    assert required in base, (required, sorted(base))
assert "CS-207" in ids("Semantic Chunking으로 RAG를 만들고 최대 token도 제한해줘")
assert "CS-209" in ids("대형 기술 문서를 parent-child chunking으로 RAG 검색해줘")
assert "CS-210" in ids("Markdown 문서를 hybrid chunking으로 처리해줘")
assert "CS-212" in ids("RAG chunk version을 관리하고 rollback 가능하게 해줘")
assert "CS-213" in ids("검색 결과 중복 청크를 제거하고 context expansion 해줘")
assert "CS-214" in ids("Recall@K MRR 기반으로 청킹 자동 튜닝 해줘")
assert "CS-216" in ids("RAG 색인 전에 청크 미리보기를 보여줘")
print("v5.521 RAG chunking standard contracts: PASS")
print("coding rules:", len(rules))
