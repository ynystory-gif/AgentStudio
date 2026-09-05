from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
for token in [
    'function Invoke-LocalJsonNoProxy',
    '$request.Proxy = $null',
    'Invoke-LocalJsonNoProxy -Url $BackendHealthUrl',
    'Invoke-LocalJsonNoProxy -Url $DbHealthUrl',
    'Get-NetTCPConnection -LocalPort $BackendPort -State Listen',
    'THEANOVA AgentStudio',
    'FastAPI Health 직접 연결',
]:
    assert token in ps, token
assert '$FallbackAgentStudioVersion = "5.555"' in ps
assert "AGENTSTUDIO_FRONTEND_VERSION='5.555'" in app
print('v5.555 local backend health no-proxy: PASS')
