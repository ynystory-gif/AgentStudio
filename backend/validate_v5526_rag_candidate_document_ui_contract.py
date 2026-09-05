from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
payload=json.loads((ROOT/'backend/app/data/coding_style/rules.json').read_text(encoding='utf-8'))
selector=(ROOT/'backend/app/services/coding_rule_selector.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert payload.get('version') in {'5.526','5.527'}
rules=payload.get('rules',[])
ids={r.get('id') for r in rules}
for rid in [f'CS-{n}' for n in range(259,275)]:
    assert rid in ids, rid
assert len(ids)==len(rules)
assert (ROOT/'backend/app/data/coding_style/sources/rag_candidate_document_list_ui_guide.md').exists()
for token in ['candidate_ui','document_grouping','explainability','pipeline_summary','diversity','source_navigation','latency']:
    assert token in selector, token
for literal in [
    "'candidate documents':'RRF 이후 Reranker가 다시 평가할 후보 문서를 확인'",
    "'final context':'실제 LLM 답변에 사용된 최종 문서와 Chunk를 확인'",
    "'document grouping':'같은 문서에서 검색된 여러 Chunk를 문서 단위로 묶어 표시'",
    "'search evidence':'문서가 검색·선택된 이유와 관련 조건을 확인'",
]:
    assert literal in app, literal
assert any(v in app for v in ("AGENTSTUDIO_FRONTEND_VERSION='5.526'", "AGENTSTUDIO_FRONTEND_VERSION='5.527'"))
assert any(f'version="{v}"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8') for v in ('5.526','5.527'))
assert any(f'"version": "{v}"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8') for v in ('5.526','5.527'))
print(f"v5.526 RAG Candidate Document UI contract: PASS ({len(rules)} rules)")
