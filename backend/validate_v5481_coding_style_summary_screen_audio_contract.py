from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MEMO = (ROOT / 'frontend/src/components/memo/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
MEDIA = (ROOT / 'frontend/src/components/media/MediaSessionProvider.tsx').read_text(encoding='utf-8')
VIEWER = (ROOT / 'frontend/src/components/media/TemporaryMediaViewer.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []
def check(name, condition):
    checks.append((name, bool(condition)))

check('frontend version 5.481', "AGENTSTUDIO_FRONTEND_VERSION='5.481'" in APP)
check('backend version 5.481', 'version="5.481"' in MAIN)
check('health version 5.481', '"version": "5.481"' in ROUTES)
check('codex client version 5.481', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.481"' in CODEX)
check('health build marker coding style', 'CodingStylePopoverLayout' in ROUTES)
check('health build marker live summary', 'LiveTranscriptSummary' in ROUTES)
check('health build marker screen audio guard', 'ScreenAudioTrackGuard' in ROUTES)

check('coding style grouped layout', "const groups=['이름 · 타입','구조 · Notebook']" in APP)
check('coding style count badge', '<span>코딩 스타일</span><b>' in APP)
check('coding style default restore action', '기본값 복원' in APP)
check('coding style popup internal button width guard', '.right-agent-build-card .agent-coding-style-popover button' in CSS and 'width:auto !important' in CSS)
check('coding style popup ancestor overflow guard', ':has(.agent-coding-style-menu[open])' in CSS)
check('coding style two-column groups', '.agent-coding-style-groups' in CSS and 'grid-template-columns:1fr 1fr' in CSS)

check('summary button exists', "'✦ 요약정리'" in MEMO)
check('summary API called', "'/media-stt/summarize'" in MEMO)
check('summary result panel exists', 'Transcript 요약정리' in MEMO and 'project-live-summary-body' in MEMO)
check('summary stale indicator exists', '요약 이후' in MEMO and '다시 ‘요약정리’' in MEMO)
check('summary backend endpoint exists', '@router.post("/media-stt/summarize")' in ROUTES)
check('summary uses simple question routing', 'model_for_task(LLMTask.SIMPLE_QUESTION)' in ROUTES)
check('summary structured sections', '[핵심 포인트]' in ROUTES and '[결정/할 일]' in ROUTES and '[키워드]' in ROUTES)
check('summary long transcript chunking', 'chunk_size = 18_000' in ROUTES and 'max_chunks = 6' in ROUTES)

check('screen share prefers current tab', 'preferCurrentTab: true' in MEDIA)
check('screen share asks for system audio', "systemAudio: 'include'" in MEDIA)
check('screen audio missing guard', "stream.getAudioTracks().length === 0" in MEDIA)
check('screen audio missing blocks fake STT', '실시간 STT와 종료 후 정밀 보정 모두 텍스트를 생성할 수 없습니다.' in MEDIA)
check('screen audio UI guidance', 'Chrome 탭 선택 → 탭 오디오 공유 ON' in MEMO)
check('temporary media guidance matches', '오디오 Track이 없으면 종료 후 보정에서도 텍스트가 생성되지 않습니다.' in VIEWER)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\n{len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit(1)
