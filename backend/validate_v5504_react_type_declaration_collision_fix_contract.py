from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
APP = SRC / "App.tsx"

def require(cond: bool, message: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL v5.504: {message}")

source = APP.read_text(encoding="utf-8")
require(not (SRC / "__temp_typecheck_shim__.d.ts").exists(), "temporary typecheck shim must never ship")
require("declare module 'react'" not in "\n".join(p.read_text(encoding='utf-8', errors='ignore') for p in SRC.rglob('*.d.ts')), "local declarations must not override React package types")
require("declare module '@xterm/xterm'" not in "\n".join(p.read_text(encoding='utf-8', errors='ignore') for p in SRC.rglob('*.d.ts')), "local declarations must not override xterm package types")
require("declare module '@xterm/addon-fit'" not in "\n".join(p.read_text(encoding='utf-8', errors='ignore') for p in SRC.rglob('*.d.ts')), "local declarations must not override xterm addon types")
require("const renderField=(label: string,name: string,type: string='text',placeholder: string='')=>" in source, "settings renderField must use string contract")
require("const renderTestResult=(name: string)=>{" in source, "settings renderTestResult must use string contract")
require("AGENTSTUDIO_FRONTEND_VERSION='5.504'" in source, "frontend version must be 5.504")
print("PASS v5.504 React/xterm package type declaration collision fix contract")
