from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
COMP = (ROOT / 'frontend/src/components/ai/AgentDesignProjectManager.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
MODELS = (ROOT / 'backend/app/models/entities.py').read_text(encoding='utf-8')
PROVISION = (ROOT / 'backend/app/services/database_provisioning.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.385'" in APP,
    'backend version': 'version="5.385"' in MAIN,
    'design project model': 'class AgentDesignProject(Base):' in MODELS,
    'design project version model': 'class AgentDesignProjectVersion(Base):' in MODELS,
    'design project core tables': '"agent_design_projects"' in PROVISION and '"agent_design_project_versions"' in PROVISION,
    'design project list endpoint': '@router.get("/agent-design-projects")' in ROUTES,
    'design project load endpoint': '@router.get("/agent-design-projects/{design_project_id}")' in ROUTES,
    'design project save endpoint': '@router.post("/agent-design-projects/save")' in ROUTES,
    'version snapshot endpoint': '@router.post("/agent-design-projects/{design_project_id}/version")' in ROUTES,
    'project toolbar': '<AgentDesignProjectToolbar' in APP and '프로젝트 저장' in COMP and '프로젝트 목록 / 열기' in COMP,
    'feature manager': '<AgentFeatureManager' in APP and '＋ 기능 추가' in COMP,
    'feature modify disable remove': 'MODIFY' in COMP and 'DISABLE' in COMP and 'REMOVE' in COMP,
    'delete impact confirmation': '영향 가능 영역' in COMP and '삭제 전 현재 설계 Snapshot' in COMP,
    'feature registry snapshot': 'feature_registry:designFeatureRegistry||[]' in APP,
    'feature registry generation prompt': '기능 관리 Registry - 최신 기능 추가/수정/비활성화/삭제 상태' in APP,
    'incremental invalidation': '변경된 기능의 영향도를 기준으로 Workflow를 증분 재설계' in APP,
    'load resume': '이전 인터뷰와 기능 정의를 이어서 진행합니다.' in APP,
    'autosave existing design project': 'void saveAgentDesignProject()' in APP,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.385 contract: ' + ', '.join(failed))
print('PASS v5.385 Agent Design Project + Feature Lifecycle contract')
