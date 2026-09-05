from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ps=(ROOT/'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')
example=(ROOT/'.env.example').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

for token in [
    'Set-AgentStudioEnvDefaultIfMissing',
    '[string]$DefaultValue = ""',
    '-DefaultPort 8000',
    '-DefaultPort 5173',
    'Get-BootstrapSetting "OLLAMA_AUTO_START" "true"',
    'Secrets are never generated here.',
    'Existing root .env values remain authoritative',
]:
    assert token in ps, token

for token in [
    'AGENTSTUDIO_BACKEND_PORT=8000',
    'AGENTSTUDIO_FRONTEND_PORT=5173',
    'OLLAMA_AUTO_START=true',
]:
    assert token in example, token

assert "AGENTSTUDIO_FRONTEND_VERSION='5.538'" in app
assert 'version="5.538"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.538"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.538 env bootstrap self-heal: PASS')
