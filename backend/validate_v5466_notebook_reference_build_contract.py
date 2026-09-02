from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "src" / "App.jsx"
NOTEBOOK = ROOT / "frontend" / "src" / "components" / "notebook" / "NotebookEditor.tsx"
CSS = ROOT / "frontend" / "src" / "styles.css"
SYSTEM_ADMIN = ROOT / "SYSTEM_ADMIN.ps1"
MAIN = ROOT / "backend" / "app" / "main.py"
ROUTES = ROOT / "backend" / "app" / "api" / "routes.py"
CODE_INTEL = ROOT / "frontend" / "src" / "utils" / "codeIntelligence.ts"


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    app = APP.read_text(encoding="utf-8")
    notebook = NOTEBOOK.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    system_admin = SYSTEM_ADMIN.read_text(encoding="utf-8")
    main_py = MAIN.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")
    code_intel = CODE_INTEL.read_text(encoding="utf-8")

    check("AGENTSTUDIO_FRONTEND_VERSION='5.466'" in app, "frontend version 5.466")
    check('version="5.466"' in main_py, "backend version 5.466")
    check('"version": "5.466"' in routes, "route health version 5.466")

    check("line: Math.max(1, Number(sourceLocation?.line || 1))" in notebook, "Code Intelligence navigation always supplies line")
    check("column: Math.max(1, Number(sourceLocation?.column || 1))" in notebook, "Code Intelligence navigation always supplies column")
    check("{ ...sourceLocation, cellIndex: sourceCellIndex }" not in notebook, "optional sourceLocation is not spread into required navigation type")
    check("if (!target) return" in notebook, "navigation history guards empty target")
    check("registerDefinitionProvider" in code_intel and "registerSignatureHelpProvider('python'" in code_intel, "v5.465 Code Intelligence retained")

    check("extractNotebookNameErrorSymbol" in notebook, "Notebook NameError symbol extraction")
    check("findNotebookDefinitionCells" in notebook, "Notebook definition-cell candidate search")
    check("[NameError 안내]" in notebook, "Notebook NameError user guidance")
    check("Backend/Notebook 세션이 재시작" in notebook, "Notebook session-reset cause guidance")

    check("documentTextReferenceMenu" in app, "document text LLM reference menu state")
    check("onContextMenuCapture={openDocumentTextReferenceMenu}" in app, "document-wide selected text context capture")
    check("source:'document-text-selection'" in app, "document text reference source marker")
    check("className=\"document-text-reference-menu\"" in app, "document text reference menu rendered")
    check(".document-text-reference-menu" in css, "document text reference menu styled")
    check("notebook-markdown-selection" in notebook, "Notebook Markdown editor LLM reference action")

    check("참조 등록 후 이전 selection을 그대로 남겨 두지 않는다" in app, "source editor stale selection guard")
    check("직전 참조 selection이 다음 우클릭에서 다시" in notebook, "Notebook stale selection guard")
    check("codeEditPromptRef.current?.focus?.()" not in app[app.find("const addCodeEditReference="):app.find("const addCodeEditReferenceFromMonaco=")], "LLM reference add no longer steals focus to prompt")

    check('"frontend_build.log"' in system_admin, "SYSTEM_ADMIN persistent frontend build log")
    check("FrontendBuildTail" in system_admin and "Select-Object -Last 50" in system_admin, "SYSTEM_ADMIN failure includes build tail")
    check("requiredFrontendPackageFiles" in system_admin, "SYSTEM_ADMIN verifies package files, not only directories")
    check('"vite\\\\client.d.ts"' in system_admin or '"vite\\client.d.ts"' in system_admin, "SYSTEM_ADMIN checks Vite type file")
    check('"@types\\\\node\\\\index.d.ts"' in system_admin or '"@types\\node\\index.d.ts"' in system_admin, "SYSTEM_ADMIN checks Node type file")

    check("NotebookNameErrorDiagnostic" in routes, "build signature includes NameError diagnostic")
    check("DocumentWideLlmReferenceSelection" in routes, "build signature includes document-wide reference")
    check("FrontendBuildFailureDetail" in routes, "build signature includes frontend build diagnostics")

    print("v5.466 notebook/reference/build contract: ALL PASS")


if __name__ == "__main__":
    main()
