from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []
def check(name, ok):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

check('frontend version 5.476', "AGENTSTUDIO_FRONTEND_VERSION='5.476'" in APP)
check('backend version 5.476', 'version="5.476"' in MAIN)
check('health version 5.476', '"version": "5.476"' in ROUTES)
check('codex client version 5.476', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.476"' in CODEX)
check('save handler ignores non-string React event', "const explicitPath=typeof pathOverride==='string'?pathOverride:''" in APP)
check('save handler uses explicit path only after type guard', 'explicitPath||activeEditorPathRef.current||selectedEditorFileRef.current||selected' in APP)
check('toolbar save button does not bind saveFile directly', 'onClick={saveFile}' not in APP)
check('toolbar save button calls saveFile without event path', "onClick={()=>saveFile('', '저장 버튼')}" in APP)
check('save completion log identifies trigger', '[저장 완료 · ${triggerLabel}]' in APP)
check('Ctrl+S explicit active path behavior retained', 'saveFile(shortcutPath)' in APP)
check('save write path still uses writeEditorFile', 'const result=await writeEditorFile(' in APP)
check('save dirty reset behavior retained', '[relativePath]:false' in APP)

failed=[name for name,ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.476 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.476 save button click contract: ALL PASS ({len(checks)}/{len(checks)})')
