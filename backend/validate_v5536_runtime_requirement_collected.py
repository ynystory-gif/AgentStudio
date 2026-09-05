from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
for token in [
    "case 'runtime':{",
    "Frontend ${frontendTech}",
    "Backend ${backendTech}",
    "runtimeHasConfiguredService",
    "runtimeHasResolvedPorts",
    "runtime_setup:safeAgentRuntimeSetup(next)",
    "approved:Boolean(next?.approved)",
]:
    assert token in app, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.536'" in app
assert 'version="5.536"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.536"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.536 runtime requirement collected: PASS')
