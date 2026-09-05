from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert '[int]$Retry = 90' in ps
assert 'Wait-ApiHealth $BackendHealthUrl 90 1' in ps
assert 'Backend 초기화 진행 중' in ps
assert 'FastAPI Health Check 90초 초과' in ps
assert '$FallbackAgentStudioVersion = "5.554"' in ps
assert "AGENTSTUDIO_FRONTEND_VERSION='5.554'" in app
print('v5.554 backend health startup wait: PASS')
