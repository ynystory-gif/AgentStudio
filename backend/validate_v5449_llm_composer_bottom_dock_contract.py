from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.449'" in APP,
    'backend version': 'version="5.449"' in MAIN and '"version": "5.449"' in ROUTES,
    'codex version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.449"' in CODEX,
    'chat always reserves flexible space': '<div className="code-llm-chat" ref={codeEditChatRef}>' in APP and '(codeEditChat.length>0||codeEditBusy||codeEditProposal)&&<div className="code-llm-chat"' not in APP,
    'attachment immediately precedes composer input': 'onAnalysisStateChange={setCodeEditAttachmentAnalysis}\n            />\n\n            <div className="code-llm-input">' in APP,
    'flex column bottom dock': '.llm-code-chat-panel .code-llm-side.chat-only{\n  height:100%;\n  min-height:0;\n  display:flex;\n  flex-direction:column;' in CSS,
    'chat takes remaining height': '.llm-code-chat-panel .code-llm-chat{\n  flex:1 1 auto;' in CSS,
    'dock ordering': '>.ai-attachment-picker{\n  order:30;' in CSS and '>.code-llm-input{\n  order:40;' in CSS,
    'save label clarified': '>코드 저장</button>' in APP and '현재 열린 코드의 변경 내용을 디스크에 저장합니다. (Ctrl+S)' in APP,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit('v5.449 contract failed: ' + ', '.join(failed))
print(f"v5.449 contracts: {len(checks)}/{len(checks)} PASS")
