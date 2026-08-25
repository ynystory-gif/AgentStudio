"""Dependency-light smoke test for the deterministic v5.342 interview gate."""
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# The runtime project installs LangChain, but CI/artifact inspection may not.
# Stub imports because this smoke test only exercises deterministic gate code.
lc = types.ModuleType('langchain_core')
msgs = types.ModuleType('langchain_core.messages')
class _Message:
    def __init__(self, content=''):
        self.content = content
msgs.SystemMessage = _Message
msgs.HumanMessage = _Message
sys.modules.setdefault('langchain_core', lc)
sys.modules.setdefault('langchain_core.messages', msgs)
router = types.ModuleType('app.services.model_router')
class _Task:
    REQUIREMENTS_ANALYSIS = 'requirements_analysis'
router.model_for_task = lambda *args, **kwargs: None
router.LLMTask = _Task
sys.modules['app.services.model_router'] = router

spec = importlib.util.spec_from_file_location(
    'requirements_agent_contract',
    ROOT / 'app/services/requirements_agent.py',
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

bad_question = (
    '이 과정에서 사용되는 알고리즘은 무엇인가요? '
    '자연어 처리 기반 검색과 상품 벡터화 및 검색 알고리즘은 어떻게 결합되어야 할까요?'
)
user_text = (
    'PostgreSQL, Redis, pgvector를 사용하는 AI 상품 검색·추천·주문 Agent를 만들고 싶다. '
    '자연어 상품 검색은 의미 기반 Vector 검색과 PostgreSQL 조건 검색을 결합하고, '
    '재고 확인 후 사용자 확인을 거쳐 주문을 생성한다.'
)
answer, diagnostics = module.apply_question_quality_gate(
    bad_question,
    user_text,
    [{'role': 'user', 'content': 'AI 상품 검색·추천·주문 Agent를 만들고 싶다.'}],
)
assert diagnostics['replaced'] is True, diagnostics
assert 'multiple_questions' in diagnostics['reasons'], diagnostics
assert 'technical_design_delegation' in diagnostics['reasons'], diagnostics
assert answer.count('?') == 1, answer
assert '사용자 화면' in answer, answer
assert 'PostgreSQL' in answer and 'Redis' in answer and 'pgvector' in answer, answer
print('[v5.342-question-quality-behavior] PASS')
print(answer)
