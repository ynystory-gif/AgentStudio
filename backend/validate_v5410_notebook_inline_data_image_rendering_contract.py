from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
RENDERERS = (ROOT / "frontend/src/components/notebook/NotebookRenderers.tsx").read_text(encoding="utf-8")

checks = {
    "version": "AGENTSTUDIO_FRONTEND_VERSION='5.410'" in APP and 'version="5.410"' in MAIN and '"version": "5.410"' in ROUTES,
    "build badge": "NotebookInlineDataImageRenderingFix" in ROUTES,
    "data image whitelist": r"data:image\/(?:png|jpe?g|gif|webp|svg\+xml)" in RENDERERS,
    "payload whitespace normalization": r"payload.replace(/\s/g, '')" in RENDERERS,
    "markdown data image token": "data:image" in RENDERERS and "attachment:" in RENDERERS,
    "split markdown recovery": r"\]\s*\(" in RENDERERS,
    "safe inline image component": "NotebookInlineImage" in RENDERERS,
    "attachment support retained": "notebookAttachmentDataUrl" in RENDERERS,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.410 contract FAIL: " + ", ".join(failed))
print(f"v5.410 Notebook Inline Data Image Rendering contract PASS {len(checks)}/{len(checks)}")
