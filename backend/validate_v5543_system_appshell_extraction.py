from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
system=(ROOT/'frontend/src/features/system/SystemPage.tsx').read_text(encoding='utf-8')
shell=(ROOT/'frontend/src/app/AppShell.tsx').read_text(encoding='utf-8')
brand=(ROOT/'frontend/src/components/layout/StudioBrand.tsx').read_text(encoding='utf-8')
contract=(ROOT/'frontend/validate_frontend_contracts.cjs').read_text(encoding='utf-8')
assert 'function SystemPage()' not in app
assert "export function SystemPage()" in system
for token in ["api('/system/status')","GpuSettingsPanel","OllamaSettingsPanel","RuntimeDatabasePanel","ServicePortSettingsPanel","CodexSettingsPanel"]:
    assert token in system, token
assert "export function AppShell" in shell
assert "location.pathname.startsWith('/system')" in shell
assert "export function StudioBrand" in brand
assert "<StudioBrand version={AGENTSTUDIO_FRONTEND_VERSION}" in app
assert "export default function App(){return <AppShell Workspace={IDE}/>}" in app
assert "adaptiveAiSource" in contract
assert "AGENTSTUDIO_FRONTEND_VERSION='5.543'" in app
assert len(app.splitlines()) < 23524
print('v5.543 System + AppShell extraction: PASS')
print('App.tsx lines:',len(app.splitlines()))
