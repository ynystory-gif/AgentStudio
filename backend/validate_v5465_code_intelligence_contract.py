from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.services.code_intelligence_service import resolve_code_intelligence


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "src" / "App.jsx"
NOTEBOOK = ROOT / "frontend" / "src" / "components" / "notebook" / "NotebookEditor.tsx"
UTILITY = ROOT / "frontend" / "src" / "utils" / "codeIntelligence.ts"
ROUTES = ROOT / "backend" / "app" / "api" / "routes.py"
MAIN = ROOT / "backend" / "app" / "main.py"


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    app = APP.read_text(encoding="utf-8")
    notebook = NOTEBOOK.read_text(encoding="utf-8")
    utility = UTILITY.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")
    main_py = MAIN.read_text(encoding="utf-8")

    check("AGENTSTUDIO_FRONTEND_VERSION='5.465'" in app, "frontend version 5.465")
    check('version="5.465"' in main_py, "backend version 5.465")
    check('"/code-intelligence/resolve"' in routes, "code intelligence API endpoint")
    check("resolve_code_intelligence" in routes, "code intelligence service wired to route")
    check("registerDefinitionProvider" in utility, "Monaco definition provider")
    check("registerHoverProvider" in utility, "Monaco hover provider")
    check("registerSignatureHelpProvider('python'" in utility, "Python signature help provider")
    check("Ctrl+Click" in utility, "Ctrl+Click definition navigation hint/fallback")
    check("registerEditorOpener" in utility, "cross-resource definition opener")
    check("KeyCode.LeftArrow" in app and "KeyCode.RightArrow" in app, "Alt left/right navigation history in source editor")
    check("registerCodeIntelligence(monaco,editor" in app.replace(" ", ""), "source editors register code intelligence")
    check("registerCodeIntelligence(monaco, editor" in notebook, "Notebook cells register code intelligence")
    check("getNotebookContent: buildLiveNotebookContent" in notebook, "Notebook live cells participate in symbol resolution")
    check("definition.cell_index" in notebook, "Notebook definition can navigate across cells")
    check("code-definition-preview" in app and "code-definition-preview" in (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8"), "external library read-only definition preview")

    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        package = project / ".venv" / "Lib" / "site-packages" / "langchain_classic" / "chains"
        package.mkdir(parents=True)
        (package.parent / "__init__.py").write_text("", encoding="utf-8")
        (package / "__init__.py").write_text(
            "from langchain_classic.chains.retrieval import create_retrieval_chain\n",
            encoding="utf-8",
        )
        (package / "retrieval.py").write_text(
            'def create_retrieval_chain(retriever: object, combine_docs_chain: object) -> object:\n'
            '    """Create a retrieval chain."""\n'
            '    return None\n',
            encoding="utf-8",
        )
        source = (
            "from langchain_classic.chains import create_retrieval_chain\n\n"
            "intro_chain_prompt = 'hello'\n"
            "intro_rag_chain = create_retrieval_chain(retriever, chain)\n"
        )
        local = resolve_code_intelligence({
            "root": str(project), "relative_path": "main.py", "language": "python",
            "content": source, "line": 3, "column": 4, "action": "definition",
        })
        check(local.get("definition", {}).get("symbol") == "intro_chain_prompt", "local variable definition resolution")

        signature = resolve_code_intelligence({
            "root": str(project), "relative_path": "main.py", "language": "python",
            "content": source, "line": 4, "column": 43, "action": "signature",
        })
        check("create_retrieval_chain" in str(signature.get("signature") or ""), "imported function signature resolution")
        check(len(signature.get("parameters") or []) == 2, "imported function parameter list")
        check(bool((signature.get("definition") or {}).get("external")), "virtualenv package treated as read-only external definition")

        notebook_doc = {
            "cells": [
                {"cell_type": "code", "source": ["intro_chain_prompt = 123\n"]},
                {"cell_type": "code", "source": ["print(intro_chain_prompt)\n"]},
            ],
            "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
        }
        cross_cell = resolve_code_intelligence({
            "root": str(project), "relative_path": "demo.ipynb", "language": "python",
            "content": "print(intro_chain_prompt)\n", "line": 1, "column": 10,
            "action": "definition", "notebook_content": json.dumps(notebook_doc), "cell_index": 1,
        })
        check((cross_cell.get("definition") or {}).get("cell_index") == 0, "Notebook cross-cell definition resolution")

    print("v5.465 code intelligence contract: ALL PASS")


if __name__ == "__main__":
    main()
