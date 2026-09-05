from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
types=(ROOT/'frontend/src/features/workspace/workspace.types.ts').read_text(encoding='utf-8')
shell=(ROOT/'frontend/src/features/workspace/WorkspaceShell.tsx').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

assert "workspaceTabDefinition=(tab:WorkspaceTab):WorkspaceTabDefinition" in types
assert "if(match) return match" in types
assert "id:'DESIGN'" in types
assert "const compactResult=Boolean(def?.compactResult)" in shell
assert "def.compactResult?" not in shell
assert "AGENTSTUDIO_FRONTEND_VERSION='5.545'" in app
print('v5.545 WorkspaceShell TS18048 fix: PASS')
