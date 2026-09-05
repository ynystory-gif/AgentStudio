from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"
remaining = sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in SRC.rglob("*") if p.is_file() and p.suffix.lower() in {".js", ".jsx"})
if remaining:
    raise SystemExit("FAIL v5.501 JS/JSX remains under frontend/src: " + ", ".join(remaining))
if not (SRC / "App.tsx").exists():
    raise SystemExit("FAIL v5.501 frontend/src/App.tsx missing")
if (SRC / "App.jsx").exists():
    raise SystemExit("FAIL v5.501 legacy App.jsx still exists")
tsconfig = json.loads((ROOT / "frontend" / "tsconfig.app.json").read_text(encoding="utf-8"))
if tsconfig.get("compilerOptions", {}).get("allowJs") is not False:
    raise SystemExit("FAIL v5.501 tsconfig.app.json allowJs must be false")
validator_source = (ROOT / "frontend" / "validate_frontend_contracts.cjs").read_text(encoding="utf-8")
if "App.tsx" not in validator_source or "App.jsx" in validator_source:
    raise SystemExit("FAIL v5.501 frontend contract validator must target App.tsx")
expected = [
    "components/ai/AgentDesignProjectManager.tsx",
    "components/global/GlobalStudioOverlays.tsx",
    "components/media/MediaWorkflowEditor.tsx",
    "services/mediaWorkflowApi.ts",
]
missing = [rel for rel in expected if not (SRC / rel).exists()]
if missing:
    raise SystemExit("FAIL v5.501 migrated frontend files missing: " + ", ".join(missing))
print("PASS v5.501 React TypeScript frontend migration contract")
