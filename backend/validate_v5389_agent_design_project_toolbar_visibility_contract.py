from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
COMP=(ROOT/'frontend/src/components/ai/AgentDesignProjectManager.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')

checks={
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.389'" in APP,
    'backend version': 'version="5.389"' in MAIN,
    'toolbar rendered': '<AgentDesignProjectToolbar' in APP,
    'save button visible contract': '프로젝트 저장' in COMP and 'agent-design-save-button' in COMP,
    'load button visible contract': '프로젝트 로드' in COMP and 'agent-design-load-button' in COMP,
    'project list modal': 'Agent 설계 프로젝트 목록' in COMP,
    'five builder rows': 'grid-template-rows:auto auto minmax(0,1fr) auto auto!important' in CSS,
    'toolbar forced visible': '.agent-design-project-toolbar{' in CSS and 'visibility:visible!important' in CSS,
    'list endpoint': '@router.get("/agent-design-projects")' in ROUTES,
    'load endpoint': '@router.get("/agent-design-projects/{design_project_id}")' in ROUTES,
    'save endpoint': '@router.post("/agent-design-projects/save")' in ROUTES,
}
failed=[name for name,ok in checks.items() if not ok]
print(f"v5.389 contract: {sum(checks.values())}/{len(checks)} PASS")
if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
