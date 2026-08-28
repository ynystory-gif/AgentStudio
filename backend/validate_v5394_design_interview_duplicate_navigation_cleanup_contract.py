from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.394'" in APP,
    "backend version": 'version="5.394"' in MAIN,
    "readme": "v5.394 DesignInterviewDuplicateNavigationCleanup" in README,
    "unified interview keeps status": '<span className="live-dot">● 대화형 수집</span>' in APP,
    "no UI layout button in interview header": '>▦ UI Layout</button>' not in APP,
    "no workflow view button in interview header": '◇ Workflow 보기' not in APP,
    "workspace workflow tab remains": "['WORKFLOW','워크플로우']" in APP,
    "layout command remains": "title:'UI Layout 템플릿 선택'" in APP,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL"), name)
if failed:
    raise SystemExit("v5.394 contract failed: " + ", ".join(failed))
print(f"v5.394 contract PASS {len(checks)}/{len(checks)}")
