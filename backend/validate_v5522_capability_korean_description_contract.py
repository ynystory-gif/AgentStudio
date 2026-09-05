from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert any(v in app for v in ("AGENTSTUDIO_FRONTEND_VERSION='5.522'", "AGENTSTUDIO_FRONTEND_VERSION='5.523'"))
assert 'CAPABILITY_KO_DESCRIPTIONS' in app
assert "'request analysis':'사용자의 요청·의도와 필요한 Capability를 분석'" in app
assert "'query rewrite':'RAG 질문을 Semantic·Keyword·Exact·Metadata 검색 계획으로 변환'" in app
assert "'hybrid search':'의미 검색과 키워드 검색을 함께 사용'" in app
assert "'reranker':'검색된 문서를 관련성이 높은 순서로 재정렬'" in app
assert "'grounding':'검색된 문서를 근거로 답변하고 출처를 연결'" in app
assert 'capabilityDisplayLabel(item.label,item.id)' in app
main=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert any(f'version="{v}"' in main for v in ("5.522","5.523"))
print('v5.522 capability Korean description contract: PASS')
