from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVICE = (ROOT / 'backend/app/services/ai_attachment_service.py').read_text(encoding='utf-8')
AGENT = (ROOT / 'backend/app/services/requirements_agent.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')

checks = {
    'requirements digest builder': 'def build_requirements_attachment_context(' in SERVICE,
    'bounded requirements context': '_REQUIREMENTS_TOTAL_CONTEXT_CHARS = 18_000' in SERVICE and '_REQUIREMENTS_PER_FILE_CHARS = 8_000' in SERVICE,
    'structural outline': 'def _requirements_outline(' in SERVICE and '문서/코드 구조 및 핵심 단서' in SERVICE,
    'interview route uses digest': 'attachment_context = build_requirements_attachment_context(' in ROUTES,
    'legacy 90k interview context removed': 'attachment_context = build_requirements_attachment_context(' in ROUTES and 'purpose="Agent 설계 인터뷰 요구사항/참고자료 분석",\n            total_char_limit=90000' not in ROUTES,
    'system no raw attachment rule': '첨부 파일의 코드/문서 원문을 답변에 그대로 복사' in AGENT,
    'echo guard': 'def _looks_like_attachment_echo(' in AGENT and 'if _looks_like_attachment_echo(content, attachment_block):' in AGENT,
    'safe fallback': 'def _safe_attachment_fallback(' in AGENT,
    'frontend last-resort guard': 'const protectInterviewAssistantAnswer=' in APP and 'const answer=protectInterviewAssistantAnswer(' in APP,
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.345'" in APP,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    print('FAILED:', ', '.join(failed))
    sys.exit(1)
print('Attachment context leak guard contract: PASS')
