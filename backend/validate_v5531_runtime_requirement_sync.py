from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
for token in [
 "React + Vite + TypeScript","React + Vite + JavaScript",
 "runtimeFrontendConfigured","runtimeBackendConfigured",
 "confirmed?.ui||runtimeFrontendConfigured",
 "confirmed?.backend||runtimeBackendConfigured",
 "runtimeSetup.frontend?.technology",
 "runtimeSetup.backend?.technology",
 "technology:e.target.value,user_fixed:true",
]:
    assert token in app, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.532'" in app
print('v5.532 runtime requirement sync: PASS')
