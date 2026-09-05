from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
controller=(ROOT/'frontend/src/features/terminal/hooks/useTerminalController.ts').read_text(encoding='utf-8')
socket=(ROOT/'frontend/src/features/terminal/services/terminalSocketService.ts').read_text(encoding='utf-8')

for token in [
 'terminalSessions','terminalSocketsRef','terminalIntentionalCloseRef',
 'xtermInstancesRef','xtermContainersRef','xtermFitAddonsRef','xtermDisposablesRef',
 'xtermCommandBuffersRef','xtermCommandHistoryRef','xtermCursorIndexRef',
 'terminalCommandBusyRef','terminalCwdRef','terminalRootRef',
 'terminalReconnectTimersRef','terminalReconnectAttemptsRef',
 'fitTerminalViewport','sendSocketMessage','scheduleReconnect','resetReconnect'
]:
    assert token in controller, token

assert "useTerminalController()" in app
assert "createTerminalSocket(wsTarget)" in app
assert "terminalSocketUrl(wsTarget)" in app
assert "scheduleReconnect(sessionId" in app
assert "const [terminalSessions,setTerminalSessions]=useState<TerminalSession[]>" not in app
assert "const terminalSocketsRef=useRef<LegacyRecord>" not in app
assert "function terminalSocketUrl" in socket
assert "AGENTSTUDIO_FRONTEND_VERSION='5.546'" in app
assert len(app.splitlines()) < 22160
print('v5.546 Terminal Controller extraction: PASS')
print('App.tsx lines:',len(app.splitlines()))
print('Terminal controller lines:',len(controller.splitlines()))
