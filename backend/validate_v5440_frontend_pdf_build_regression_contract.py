from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "frontend" / "src" / "components" / "viewers" / "DocumentViewers.tsx"
APP = ROOT / "frontend" / "src" / "App.jsx"
MAIN = ROOT / "backend" / "app" / "main.py"
ROUTES = ROOT / "backend" / "app" / "api" / "routes.py"


def check(name: str, ok: bool) -> None:
    if not ok:
        raise AssertionError(name)
    print(f"[PASS] {name}")


def main() -> None:
    viewer = VIEWER.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    main_py = MAIN.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")

    # v5.438/v5.439 regression: runtimeInfo import was removed while a stale
    # runtimeInfo().apiBase line remained in PresentationViewer. TypeScript build
    # therefore failed before Backend startup.
    check("DocumentViewers has no stale runtimeInfo reference", "runtimeInfo()" not in viewer)
    check("DocumentViewers imports apiFetch", "apiFetch" in viewer.splitlines()[1])
    check("PDF preview uses authenticated apiFetch", "apiFetch(`/files/pdf?${params.toString()}`)" in viewer)
    check("PowerPoint PDF preview uses authenticated apiFetch", "apiFetch(`/files/presentation/pdf?${params.toString()}`)" in viewer)
    check("raw binary read uses authenticated apiFetch", "apiFetch(`/files/raw?${params.toString()}`)" in app)
    check("frontend version is 5.440", "AGENTSTUDIO_FRONTEND_VERSION='5.440'" in app)
    check("backend FastAPI version is 5.440", 'version="5.440"' in main_py)
    check("health API version is 5.440", '"version": "5.440"' in routes)


if __name__ == "__main__":
    main()
