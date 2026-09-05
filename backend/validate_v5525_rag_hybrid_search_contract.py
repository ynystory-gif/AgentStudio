from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
payload=json.loads((ROOT/'backend/app/data/coding_style/rules.json').read_text(encoding='utf-8'))
selector=(ROOT/'backend/app/services/coding_rule_selector.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert payload.get('version') in {'5.525','5.526'}
rules=payload.get('rules',[])
ids={r.get('id') for r in rules}
for rid in [f'CS-{n}' for n in range(243,259)]:
    assert rid in ids, rid
assert len(ids)==len(rules)
assert (ROOT/'backend/app/data/coding_style/sources/rag_hybrid_search_guide.md').exists()
for token in ['hybrid_search','vector_search','bm25','fusion','rrf','deduplicate','reranking','tokenizer','observability']:
    assert token in selector, token
for literal in [
    "'hybrid search':'Vector 의미 검색과 BM25 정확 키워드 검색을 함께 사용'",
    "'bm25 search':'정확한 단어·코드·문서번호가 포함된 문서를 BM25로 검색'",
    "'rrf':'Vector와 BM25의 검색 순위를 안정적으로 결합'",
    "'search strategy router':'질문 유형에 따라 Vector·BM25·Exact·Hybrid 검색 전략을 선택'",
]:
    assert literal in app, literal
assert any(v in app for v in ("AGENTSTUDIO_FRONTEND_VERSION='5.525'", "AGENTSTUDIO_FRONTEND_VERSION='5.526'"))
assert any(f'version="{v}"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8') for v in ('5.525','5.526'))
assert any(f'"version": "{v}"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8') for v in ('5.525','5.526'))
print(f"v5.525 RAG Hybrid Search contract: PASS ({len(rules)} rules)")
