from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PS1 = (ROOT / "SYSTEM_ADMIN.ps1").read_text(encoding="utf-8-sig")
MAIN = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("$ExpectedAgentStudioVersion = \"5.349\"" not in PS1, "stale hard-coded 5.349 launcher version remains")
require("Resolve-LocalAgentStudioVersion" in PS1, "SYSTEM_ADMIN must derive local expected version")
require("backend\\app\\main.py" in PS1, "SYSTEM_ADMIN must derive version from local backend source")
require("$FallbackAgentStudioVersion = \"5.356\"" in PS1, "launcher fallback version must be 5.356")
require("AGENTSTUDIO_FRONTEND_VERSION='5.356'" in APP, "frontend version must be 5.356")
require('version="5.356"' in MAIN or "version='5.356'" in MAIN, "FastAPI version must be 5.356")
require('"version": "5.356"' in ROUTES, "health endpoint version must be 5.356")

main_match = re.search(r'FastAPI\s*\([\s\S]*?version\s*=\s*[\"\'](?P<v>\d+\.\d+)[\"\']', MAIN)
health_match = re.search(r'\"version\"\s*:\s*\"(?P<v>\d+\.\d+)\"', ROUTES)
require(main_match is not None and main_match.group("v") == "5.356", "could not resolve local backend version")
require(health_match is not None and health_match.group("v") == main_match.group("v"), "backend health version drift")

print("PASS v5.356 SYSTEM_ADMIN Launcher Version Sync contract")
