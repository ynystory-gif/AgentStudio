from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN_TSX = (ROOT / 'frontend/src/main.tsx').read_text(encoding='utf-8')
MEDIA = (ROOT / 'frontend/src/components/media/MediaSessionProvider.tsx').read_text(encoding='utf-8')
VIEWER = (ROOT / 'frontend/src/components/media/TemporaryMediaViewer.tsx').read_text(encoding='utf-8')
MEMO = (ROOT / 'frontend/src/components/memo/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
STYLES = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []
def check(name, condition):
    checks.append((name, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")

check('frontend version 5.477', "AGENTSTUDIO_FRONTEND_VERSION='5.477'" in APP)
check('backend version 5.477', 'version="5.477"' in MAIN)
check('health version 5.477', '"version": "5.477"' in ROUTES)
check('codex client version 5.477', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.477"' in CODEX)
check('global MediaSessionProvider wraps App', 'MediaSessionProvider><App />' in MAIN_TSX)
check('microphone capture', 'getUserMedia({ audio: true })' in MEDIA)
check('screen/system audio capture', 'getDisplayMedia({ video: true, audio: true })' in MEDIA)
check('MediaRecorder session', 'new MediaRecorder' in MEDIA and 'mediaChunksRef' in MEDIA)
check('SpeechRecognition support', 'webkitSpeechRecognition' in MEDIA and 'interimResults = true' in MEDIA)
check('SpeechRecognition auto reconnect', "setSttStatus('STT 재연결 중…')" in MEDIA and 'recognitionRestartTimerRef' in MEDIA)
check('recording survives memo tab unmount by provider architecture', 'useMediaSession()' in APP and 'useMediaSession()' in MEMO)
check('project binding is fixed during recording', 'mediaSession.projectRoot !== projectRoot' in MEMO and '자동 변경되지 않습니다' in MEMO)
check('global status bar recording indicator', 'global-media-status' in APP and 'formatMediaElapsed(mediaSession.elapsedSeconds)' in APP)
check('status bar opens Memo panel', "setCodeRightPanelTab('MEMO')" in APP)
check('memo live recording tab', "'MEMO' | 'LIVE'" in MEMO and '● 실시간 기록' in MEMO)
check('live transcript segment UI', 'project-live-transcript-body' in MEMO and 'mediaSession.transcriptSegments.map' in MEMO)
check('transcript to file memo', 'appendTranscriptToCurrentMemo' in MEMO and '현재 파일 메모에 넣기' in MEMO)
check('transcript to LLM reference', "source: 'live-transcript'" in MEMO and 'LLM 참조 문구' in MEMO)
check('backend transcript GET endpoint', '@router.get("/project-live-transcript")' in ROUTES)
check('backend transcript POST endpoint', '@router.post("/project-live-transcript")' in ROUTES)
check('project transcript hidden store', '"live_transcript.json"' in ROUTES and '/ ".agentstudio" /' in ROUTES)
check('recording file export', 'recordingUrl' in MEDIA and '녹음 파일 저장' in MEMO)
check('external media URL launcher', 'YouTube 또는 외부 영상 URL' in MEMO and 'onOpenExternalMedia' in MEMO)
check('temporary media editor tab', 'temporary-media-tab' in APP and 'TemporaryMediaViewer' in APP)
check('YouTube embed support', 'youtube.com/embed' in VIEWER and '<iframe' in VIEWER)
check('temporary media is not a project file', '프로젝트 파일은 생성하지 않습니다.' in VIEWER)
check('recording/status CSS present', '.global-media-status' in STYLES and '.live-recording-dot.active' in STYLES)
check('previous single memo per file policy retained', 'dedupeMemosByFile' in MEMO and '파일별 메모는 1개' in MEMO)
check('previous save click guard retained', "onClick={()=>saveFile('', '저장 버튼')}" in APP)

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.477 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.477 global media session contract: ALL PASS ({len(checks)}/{len(checks)})')
