from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"
APP = SRC / "App.tsx"
TSCONFIG = ROOT / "frontend" / "tsconfig.app.json"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL v5.504: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


require(APP.exists(), "frontend/src/App.tsx missing")
source = APP.read_text(encoding="utf-8")

legacy_js = [p for p in SRC.rglob("*") if p.suffix.lower() in {".js", ".jsx"}]
require(not legacy_js, f"legacy JS/JSX remains: {[str(p.relative_to(SRC)) for p in legacy_js[:10]]}")

nocheck = []
for path in SRC.rglob("*"):
    if path.suffix.lower() not in {".ts", ".tsx"}:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if "@ts-nocheck" in text:
        nocheck.append(str(path.relative_to(SRC)))
require(not nocheck, f"@ts-nocheck remains: {nocheck}")

config = json.loads(TSCONFIG.read_text(encoding="utf-8"))
compiler = config.get("compilerOptions") or {}
require(compiler.get("allowJs") is False, "allowJs must be false")
require(compiler.get("strict") is True, "strict must be true")
require(compiler.get("noUncheckedIndexedAccess") is True, "noUncheckedIndexedAccess must stay true")

legacy_types = (SRC / "types" / "legacy-globals.d.ts").read_text(encoding="utf-8")
require("type LegacyValue = any" in legacy_types, "LegacyValue compatibility boundary missing")

# Direct any usage must not spread through application source. The compatibility alias is the only exception.
direct_any = []
patterns = [re.compile(r"\bas\s+any\b"), re.compile(r":\s*any\b"), re.compile(r"<\s*any\s*>")]
for path in SRC.rglob("*"):
    if path.suffix.lower() not in {".ts", ".tsx"} or path.name == "legacy-globals.d.ts":
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if any(pattern.search(line) for pattern in patterns):
            direct_any.append(f"{path.relative_to(SRC)}:{line_no}")
require(not direct_any, f"direct any usage remains outside compatibility boundary: {direct_any[:20]}")

require("AGENTSTUDIO_FRONTEND_VERSION='5.504'" in source, "frontend version is not 5.504")

# Core UI/regression anchors requested for stabilization.
anchors = {
    "memo": ["ProjectMemoPanel", "useMediaSession"],
    "stt": ["ProjectMemoPanel", "MediaSessionProvider"],
    "workflow": ["MediaWorkflowEditor", "onWorkflowChange"],
    "db_erd": ["DatabaseErdPanel", "DatabaseDiagramViewer"],
    "codex": ["CodexPanel", "onCodeProposal"],
    "project_files": ["fileTreeRootRef", "const openFile=async", "const writeEditorFile=async"],
    "terminal": ["TerminalPanel"],
    "notebook": ["NotebookEditor"],
}
for label, values in anchors.items():
    missing = [value for value in values if value not in source]
    require(not missing, f"{label} regression anchors missing: {missing}")

# Component-level type contracts should exist for the high-risk panels.
component_contracts = {
    "components/memo/ProjectMemoPanel.tsx": ["type Props", "projectRoot"],
    "components/terminal/TerminalPanel.tsx": ["interface TerminalPanelProps"],
    "components/notebook/NotebookEditor.tsx": ["export interface NotebookEditorProps"],
    "components/database/DatabaseErdPanel.tsx": ["export interface DatabaseErdPanelProps"],
    "components/codex/CodexPanel.tsx": ["type Props", "CodexThread"],
    "components/ai/AiAttachmentPicker.tsx": ["AiAttachmentAnalysisFile"],
}
for rel, values in component_contracts.items():
    text = (SRC / rel).read_text(encoding="utf-8")
    missing = [value for value in values if value not in text]
    require(not missing, f"typed component contract missing in {rel}: {missing}")

print("PASS v5.504 TypeScript strict stabilization + core regression contract")
