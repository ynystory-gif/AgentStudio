from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
admin = (ROOT / "SYSTEM_ADMIN.ps1").read_text(encoding="utf-8")
validator = (ROOT / "frontend" / "validate_frontend_contracts.cjs").read_text(encoding="utf-8")
app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL v5.505: {message}")

require("AGENTSTUDIO_FRONTEND_VERSION='5.505'" in app, "frontend version must be 5.505")
require('__temp_typecheck_shim__.d.ts' in admin, "SYSTEM_ADMIN must remove the known v5.503 stale shim")
require('__temp_typecheck_*.d.ts' in admin, "SYSTEM_ADMIN must remove stale typecheck shim variants")
require('tsconfig.app.tsbuildinfo' in admin, "SYSTEM_ADMIN must clear incremental TypeScript build metadata")
require('obsolete TypeScript shim detected' in validator, "frontend contract must detect stale shim")
require(not (ROOT / 'frontend' / 'src' / '__temp_typecheck_shim__.d.ts').exists(), "distribution must not contain stale shim")
print("PASS v5.505 stale TypeScript shim auto-cleanup contract")
