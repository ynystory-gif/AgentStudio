from pathlib import Path
import importlib.util
import sys
import types

ROOT = Path(__file__).resolve().parent
AGENT_PATH = ROOT / 'app/services/requirements_agent.py'
ROUTES_PATH = ROOT / 'app/api/routes.py'
WORKFLOW_PATH = ROOT / 'app/services/agent_workflow.py'
APP_PATH = ROOT.parent / 'frontend/src/App.jsx'
MAIN_PATH = ROOT / 'app/main.py'

AGENT = AGENT_PATH.read_text(encoding='utf-8')
ROUTES = ROUTES_PATH.read_text(encoding='utf-8')
WORKFLOW = WORKFLOW_PATH.read_text(encoding='utf-8')
APP = APP_PATH.read_text(encoding='utf-8')
MAIN = MAIN_PATH.read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
    'backend version': 'version="5.369"' in MAIN or "version='5.369'" in MAIN,
    'health version': '"version": "5.369"' in ROUTES,
    'fast interview classifier': 'def _is_fast_interview_turn(' in AGENT,
    'fast interview deterministic response': 'def _fast_interview_message(' in AGENT,
    'asked slot tracking': 'def _asked_question_slots(' in AGENT,
    'assistant duplicate detection': 'def _is_duplicate_assistant_reply(' in AGENT,
    'fresh attachment separated': 'fresh_attachment_text = str(attachment_context.get("text") or "").strip()' in ROUTES,
    'cached attachment memory separate argument': 'attachment_memory=attachment_memory' in ROUTES,
    'echo guard fresh only': 'if fresh_attachment_block and _looks_like_attachment_echo(content, fresh_attachment_block):' in AGENT,
    'db preview deferred while interview busy': 'if(busy||interviewAttachmentSummaryBusy)' in APP,
    'focused repair materializes replacements': 'def _materialize_focused_repair_change(' in WORKFLOW and '_safe_replacement(content, old, new)' in WORKFLOW,
    'focused repair recovery retry': '[Focused Patch Recovery]' in WORKFLOW,
    'focused repair partial retry policy': 'validation["partial"] = bool(combined_changes) and bool(missing)' in WORKFLOW and 'validation["ok"] = bool(combined_changes)' in WORKFLOW,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('v5.369 contract failed: ' + ', '.join(failed))

# Dependency-light behavioral checks for deterministic interview logic.
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

spec = importlib.util.spec_from_file_location('requirements_agent_v5358_contract', AGENT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

history = [
    {'role': 'assistant', 'content': '어떤 Agent를 만들고 싶으신가요?'},
    {'role': 'user', 'content': '온라인 리테일 주문 Agent를 만들고 싶다.'},
    {
        'role': 'assistant',
        'content': '첨부 파일의 구조와 주요 내용을 분석해 요구사항 Context에 반영했습니다.\n\n'
                   '다음으로 이 Agent가 입력으로 반드시 지원해야 하는 파일 형식은 무엇인가요?'
    },
]
reply = module._fast_interview_message(
    '상품 검색시 문장으로 벡터 검색이 되어야 한다.',
    history,
    'PostgreSQL pgvector',
)
assert '첨부 파일의 구조와 주요 내용을 분석' not in reply, reply
assert '벡터 검색' in reply or '벡터' in reply, reply
assert reply.count('?') == 1, reply
assert '파일 형식' not in reply, reply  # already asked once; move to another missing slot
assert module._is_duplicate_assistant_reply(history[-1]['content'], history) is True
assert module._attachment_ack_already_sent(history) is True
assert module._is_fast_interview_turn('추가로 필요한 사항이 있는가?', history, '') is True
assert module._is_fast_interview_turn('추가로 필요한 사항이 있는가?', history, 'fresh attachment body') is False

print('PASS v5.369 Fast Interview State Dedup + Repair Recovery contract')
