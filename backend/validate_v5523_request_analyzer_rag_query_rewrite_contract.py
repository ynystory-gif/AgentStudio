from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
payload=json.loads((ROOT/'backend/app/data/coding_style/rules.json').read_text(encoding='utf-8'))
selector=(ROOT/'backend/app/services/coding_rule_selector.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert payload.get('version') in {'5.523','5.524'}
rules=payload.get('rules',[])
ids={r.get('id') for r in rules}
for rid in [f'CS-{n}' for n in range(217,229)]:
    assert rid in ids, rid
assert len(ids)==len(rules)
assert (ROOT/'backend/app/data/coding_style/sources/request_analyzer_query_rewrite_guide.md').exists()
for token in ['request_analysis','capability_routing','query_analysis','query_rewrite','conversation_rewrite','search_type','multi_query','permission_filter','multi_hop']:
    assert token in selector, token
for literal in [
    "'request analysis':'사용자의 요청·의도와 필요한 Capability를 분석'",
    "'query analysis':'RAG 질문의 주제·기간·조건과 검색 유형을 분석'",
    "'query rewrite':'RAG 질문을 Semantic·Keyword·Exact·Metadata 검색 계획으로 변환'",
    "'conversation rewrite':'이전 대화를 참고해 독립적으로 검색 가능한 질문으로 변환'",
    "'search type detection':'Exact·Semantic·Filter·Comparison·Multi-hop 검색 유형을 자동 판단'",
    "'permission filter':'사용자에게 접근 권한이 있는 문서만 검색'",
]:
    assert literal in app, literal
assert any(v in app for v in ("AGENTSTUDIO_FRONTEND_VERSION='5.523'", "AGENTSTUDIO_FRONTEND_VERSION='5.524'"))
assert any(f'version="{v}"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8') for v in ('5.523','5.524'))
assert any(f'"version": "{v}"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8') for v in ('5.523','5.524'))
print(f"v5.523 Request Analyzer / RAG Query Rewrite contracts: PASS ({len(rules)} rules)")
