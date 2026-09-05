from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
controller=(ROOT/'frontend/src/features/terminal/hooks/useTerminalController.ts').read_text(encoding='utf-8')
types=(ROOT/'frontend/src/types/terminal.ts').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

assert "import { serializeTerminalClientMessage } from '../../../utils/terminal'" in controller
assert "import type { TerminalClientMessage } from '../../../types/terminal'" in controller
assert "type TerminalClientMessage } from '../../../utils/terminal'" not in controller
assert "payload:TerminalClientMessage" in controller
assert "TerminalClientMessage" in types
assert "AGENTSTUDIO_FRONTEND_VERSION='5.548'" in app
print('v5.548 TerminalClientMessage import path: PASS')
