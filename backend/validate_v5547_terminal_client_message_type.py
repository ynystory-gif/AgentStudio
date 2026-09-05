from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
controller=(ROOT/'frontend/src/features/terminal/hooks/useTerminalController.ts').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

assert "type TerminalClientMessage" in controller
assert "payload:TerminalClientMessage" in controller
assert "payload:LegacyRecord" not in controller
assert "serializeTerminalClientMessage(payload)" in controller
assert "AGENTSTUDIO_FRONTEND_VERSION='5.547'" in app
assert 'version="5.547"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.547"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.547 TerminalClientMessage type contract: PASS')
