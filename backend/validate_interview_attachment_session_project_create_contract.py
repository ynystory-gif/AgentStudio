from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
ATTACH = (ROOT / 'backend' / 'app' / 'services' / 'ai_attachment_service.py').read_text(encoding='utf-8')

checks = {
    'v5.341 frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,
    'no per-turn attachment label builder': 'const interviewAttachmentLabel=' not in APP,
    'frontend hidden attachment session memory': 'interviewAttachmentMemory' in APP and 'attachment_memory:interviewAttachmentMemory' in APP,
    'attachment ids consumed after successful analysis': 'setInterviewAttachments([])' in APP and "/ai/attachments/release" in APP,
    'old draft display secret scrub': 'sanitizeInterviewDisplayText' in APP and '[REDACTED_TOKEN]' in APP,
    'backend attachment memory contract': 'attachment_memory: str = ""' in ROUTES and '_merge_interview_attachment_memory' in ROUTES,
    'backend credential redaction before AI context': 'def redact_sensitive_text' in ATTACH and 'content = redact_sensitive_text' in ATTACH,
    'workflow uses compact attachment memory': 'build_requirements_attachment_context' in ROUTES and '[인터뷰 참고자료 세션 메모리]' in ROUTES,
    'project create smart flow': 'const createAgentProjectSmart=async()=>{' in APP and 'workflowResult=await previewTargetWorkflow()' in APP and 'return await createAgentProjectFromInterview()' in APP,
    'project button available before workflow when collected': "stage==='REQUIREMENTS'&&workflowEnabled" in APP and '＋ 프로젝트 생성' in APP,
}

failed = []
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
    if not ok:
        failed.append(name)

sys.path.insert(0, str(ROOT / 'backend'))
from app.services.ai_attachment_service import redact_sensitive_text
sample = (
    'OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456\n'
    'SUPABASE_DB_PASSWORD=real-password\n'
    'DATABASE_URL=postgresql://postgres:secret@host:5432/postgres\n'
    'OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")\n'
)
redacted = redact_sensitive_text(sample)
smoke = (
    'sk-proj-' not in redacted
    and 'real-password' not in redacted
    and 'secret@host' not in redacted
    and 'os.getenv("OPENAI_API_KEY")' in redacted
)
print(('PASS' if smoke else 'FAIL'), 'credential redaction smoke')
if not smoke:
    failed.append('credential redaction smoke')

if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
print('INTERVIEW_ATTACHMENT_SESSION_PROJECT_CREATE_CONTRACT_PASS')
