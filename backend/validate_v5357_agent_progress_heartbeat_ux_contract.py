from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
PICKER = (ROOT / 'frontend' / 'src' / 'components' / 'ai' / 'AiAttachmentPicker.tsx').read_text(encoding='utf-8')
PROGRESS = (ROOT / 'frontend' / 'src' / 'components' / 'ai' / 'AgentActivityProgress.tsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')

checks = {
    'v5.368 frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,
    'manual attachment deep analysis gate': '첨부만 먼저 분석' in APP and '파일 첨부만으로 DB·Workflow·Architecture 심층 분석을 자동 시작하지 않습니다.' in APP,
    'no automatic summary effect': 'const summarizeInterviewAttachments=async()=>{' in APP,
    'progress panel': '<AgentActivityProgress' in APP and 'AgentActivityProgress' in APP,
    'backend heartbeat': "await api('/health')" in PROGRESS and '5000' in PROGRESS,
    'elapsed time and delay warnings': '45' in PROGRESS and '120' in PROGRESS and '응답이 평소보다 오래' in PROGRESS,
    'cancel and retry': 'AbortController' in APP and 'cancelInterviewActivity' in APP and 'retryInterviewActivity' in APP,
    'detail progress log': '상세 진행 로그' in PROGRESS,
    'explicit deep analysis wait label': 'AI 심층 분석 대기' in PICKER,
    'backend version': '"version": "5.368"' in ROUTES,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('v5.368 contract failed: ' + ', '.join(failed))
print('PASS v5.368 Agent Progress Heartbeat UX contract')
