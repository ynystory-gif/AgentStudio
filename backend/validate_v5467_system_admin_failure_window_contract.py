from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = (ROOT / "SYSTEM_ADMIN.ps1").read_text(encoding="utf-8-sig")
CMD = (ROOT / "SYSTEM_ADMIN.cmd").read_text(encoding="utf-8")
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = []
def check(ok: bool, label: str):
    checks.append((ok, label))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")

check(PS1.lstrip().startswith("param("), "SYSTEM_ADMIN supports explicit elevated-child mode")
check("[switch]$ElevatedChild" in PS1, "ElevatedChild switch exists")
check('"-ElevatedChild"' in PS1, "UAC relaunch passes ElevatedChild flag")
check("if ($ElevatedChild)" in PS1, "failure hold is limited to elevated child")
check("오류 확인을 위해 이 관리자 창을 자동으로 닫지 않습니다" in PS1, "failure window explains hold behavior")
check("[void](Read-Host)" in PS1, "elevated error window waits for user acknowledgement")
check('$PreviousErrorActionPreference = $ErrorActionPreference' in PS1, "npm build preserves PowerShell error preference")
check('$ErrorActionPreference = "Continue"' in PS1, "npm stderr cannot abort build capture prematurely")
check('$ErrorActionPreference = $PreviousErrorActionPreference' in PS1, "PowerShell error preference is restored")
check('& npm run build 2>&1 | Tee-Object -FilePath $FrontendBuildLog' in PS1, "frontend build output remains fully logged")
check('$FrontendBuildExitCode = $LASTEXITCODE' in PS1, "frontend build uses npm exit code")
check('if ($FrontendBuildExitCode -ne 0)' in PS1, "frontend build fails only after exit-code evaluation")
check("This window will remain open." in CMD, "outer launcher also remains open on completion/failure")
check("pause" in CMD.lower(), "outer launcher requires explicit user acknowledgement")
check("AGENTSTUDIO_FRONTEND_VERSION='5.467'" in APP, "frontend version 5.467")
check('version="5.467"' in MAIN, "backend version 5.467")
check('"version": "5.467"' in ROUTES, "route health version 5.467")
check('AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.467"' in CODEX, "Codex client version 5.467")
check("ElevatedFailureWindowHold" in ROUTES and "PowerShellNpmStderrGuard" in ROUTES, "build marker records v5.467 reliability fixes")

failed = [label for ok, label in checks if not ok]
if failed:
    raise SystemExit(f"v5.467 contract failed: {len(failed)} / {len(checks)} -> {failed}")
print(f"v5.467 SYSTEM_ADMIN failure-window contract: ALL PASS ({len(checks)}/{len(checks)})")
