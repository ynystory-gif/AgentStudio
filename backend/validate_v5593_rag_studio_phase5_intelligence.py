from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding='utf-8')

models=read('backend/app/models/rag_entities.py')
routes=read('backend/app/api/rag_routes.py')
retrieval=read('backend/app/rag/retrieval_service.py')
logic=read('backend/app/rag/retrieval_logic.py')
intel=read('backend/app/rag/intelligence_service.py')
ui=read('frontend/src/features/rag/components/RagStudio.tsx')
api=read('frontend/src/features/rag/ragApi.ts')
types=read('frontend/src/features/rag/ragTypes.ts')
app=read('frontend/src/app/App.tsx')
main=read('backend/app/main.py')
api_routes=read('backend/app/api/routes.py')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.593'" in app
assert 'version="5.593"' in main
assert '"version": "5.593"' in api_routes

for cls,table in [
    ('RagIntelligenceSetting','rag_intelligence_settings'),
    ('RagRecommendationRun','rag_recommendation_runs'),
]:
    block=re.search(rf'class {cls}\(Base\):(.*?)(?=\nclass |\Z)',models,re.S)
    assert block, cls
    text=block.group(0)
    assert f'__tablename__ = "{table}"' in text
    assert 'id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)' in text

for endpoint in [
    "@router.get('/intelligence/settings')",
    "@router.put('/intelligence/settings')",
    "@router.get('/evaluation')",
    "@router.post('/recommendations')",
    "@router.post('/recommendations/{recommendation_id}/apply')",
]:
    assert endpoint in routes, endpoint

for token in [
    'route_retrieval_mode',
    'rerank_results',
    'router_enabled',
    'reranking_enabled',
    'rerank_top_n',
    'LIGHTWEIGHT_RELEVANCE_V1',
]:
    assert token in retrieval or token in logic, token

for token in [
    'create_ai_recommendation',
    'apply_ai_recommendation',
    'evaluate_rag_settings',
    'model_for_task(LLMTask.SIMPLE_QUESTION)',
    'RULE_FALLBACK',
    'diff_json',
    'RagAgentTool',
    'tool_rows',
]:
    assert token in intel, token

for token in [
    'AI RAG 추천 / 설정 평가',
    'runAiRecommendation',
    'applyRecommendation',
    'Retrieval Router',
    'Reranking',
    'recommendation.diff',
    'executeRetrievalTest(nextRetrieval,nextIntelligence)',
]:
    assert token in ui, token

for token in [
    'createRagAiRecommendation',
    'applyRagAiRecommendation',
    'evaluateRagSettings',
    'loadRagIntelligenceSetting',
]:
    assert token in api, token

for token in [
    'RagIntelligenceSetting',
    'RagAiRecommendation',
    'RagRecommendationApplyResult',
    'RagRetrievalRouterDecision',
    'rerank_score',
]:
    assert token in types, token

# Preserve v5.592 strict array-safety repair.
assert 'const firstTool=toolItems[0]' in ui
assert 'if(firstTool)setSelectedAgentToolId(firstTool.id)' in ui
assert 'const firstCollection=collectionItems[0]' in ui
assert 'if(firstCollection)setToolCollectionId(firstCollection.id)' in ui
assert 'if(toolItems.length)setSelectedAgentToolId(toolItems[0].id)' not in ui
assert 'if(collectionItems.length)setToolCollectionId(collectionItems[0].id)' not in ui

# Pure routing/reranking behavior smoke test.
sys.path.insert(0,str(ROOT/'backend'))
from app.rag.retrieval_logic import route_retrieval_mode, rerank_results
exact=route_retrieval_mode('ERR-109 오류가 뭐야?')
assert exact['selected_mode'] in {'KEYWORD','HYBRID'}
natural=route_retrieval_mode('로그인 인증 구조가 전체적으로 어떻게 동작하는지 설명해줘')
assert natural['selected_mode'] in {'VECTOR','HYBRID'}
rows=[
    {'chunk_id':1,'score':0.70,'vector_similarity':0.70,'keyword_score':0.20,'content':'OAuth2 로그인 인증 구조','heading':'인증','symbol_name':'','document_path':'API.md'},
    {'chunk_id':2,'score':0.80,'vector_similarity':0.80,'keyword_score':0.10,'content':'기타 내용','heading':'','symbol_name':'','document_path':'misc.md'},
]
ranked=rerank_results(rows,'로그인 인증 구조',2)
assert ranked and ranked[0]['chunk_id']==1
assert ranked[0].get('rerank_score') is not None

print('[PASS] v5.593 RAG Studio phase 5 Intelligence contracts')
