from pathlib import Path
root=Path(__file__).resolve().parents[1]
svc=(root/'backend/app/services/live_stt_service.py').read_text(encoding='utf-8')
routes=(root/'backend/app/api/routes.py').read_text(encoding='utf-8')
ui=(root/'frontend/src/features/project/components/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
assert 'AGENTSTUDIO_STT_REFINE_MODEL' in svc
assert 'refine_whisper_runtime.ensure_model' in svc
assert 're.sub(r"(?m)^\\s*\\[?\\d{1,2}:\\d{2}:\\d{2}' in routes
assert '@router.get("/media-stt/history")' in routes
assert 'recording_history.json' in routes
assert '이전 녹음 기록' in ui
assert "persistLiveTextFile('TRANSCRIPT', mediaSession.transcriptText)" in ui
print('v5.574 STT quality/history validation: PASS')
