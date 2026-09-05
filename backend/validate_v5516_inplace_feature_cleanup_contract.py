from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_ADMIN = (ROOT / "SYSTEM_ADMIN.ps1").read_text(encoding="utf-8", errors="replace")
APP = (ROOT / "frontend" / "src" / "app" / "App.tsx").read_text(encoding="utf-8", errors="replace")

required_cleanup_tokens = [
    r"src\components\notebook",
    r"src\components\memo\ProjectMemoPanel.tsx",
    r"src\components\viewers\DocumentViewers.tsx",
    r"src\utils\notebook.ts",
    r"src\components\database",
    r"src\components\codex",
    r"src\components\media\MediaWorkflowEditor.tsx",
]
for token in required_cleanup_tokens:
    assert token in SYSTEM_ADMIN, f"missing cleanup contract: {token}"

assert "$RetiredFrontendFeaturePaths" in SYSTEM_ADMIN
assert "Remove-Item -LiteralPath $retiredFeaturePath -Recurse -Force" in SYSTEM_ADMIN
assert "5.516" in APP
assert not (ROOT / "frontend" / "src" / "components" / "database").exists()
assert not (ROOT / "frontend" / "src" / "components" / "codex").exists()
assert not (ROOT / "frontend" / "src" / "components" / "notebook").exists()

print("[v5.516] in-place retired feature cleanup contract: PASS")
