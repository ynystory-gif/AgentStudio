from pathlib import Path
root = Path(__file__).resolve().parents[1]
service = root / 'frontend' / 'src' / 'features' / 'prompt-tool-studio' / 'service.ts'
api = root / 'frontend' / 'src' / 'api.ts'
app = root / 'frontend' / 'src' / 'app' / 'App.tsx'
main = root / 'backend' / 'app' / 'main.py'
text = service.read_text(encoding='utf-8')
assert "from '../../api'" in text, text.splitlines()[:3]
assert api.is_file(), api
assert "AGENTSTUDIO_FRONTEND_VERSION='5.581'" in app.read_text(encoding='utf-8')
assert 'version="5.581"' in main.read_text(encoding='utf-8')
print('v5.581 Prompt & Tool Studio API import regression validation: PASS')
