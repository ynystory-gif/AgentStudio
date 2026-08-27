from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')

checks={
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.390'" in APP,
    'backend version': 'version="5.390"' in MAIN,
    'unified design toolbar': "workspaceTab==='DESIGN'&&<div className=\"unified-agent-design\"" in APP and APP.count('<AgentDesignProjectToolbar')>=2,
    'toolbar save action': "onSave={()=>saveAgentDesignProject" in APP,
    'toolbar load action': 'onLoad={loadAgentDesignProject}' in APP,
    'unified feature manager': 'className="unified-feature-manager-shell"' in APP and APP.count('<AgentFeatureManager')>=2,
    'feature delete button': "changeStatus(item,'REMOVE')" in (ROOT/'frontend/src/components/ai/AgentDesignProjectManager.jsx').read_text(encoding='utf-8'),
    'theme list modal': 'ui-layout-theme-target-modal-backdrop' in APP,
    'theme list not inline narrow': 'onClick={()=>setFrontendThemeListOpen(true)}>지원 목록 보기' in APP,
    'unified grid row reserved': 'grid-template-rows:auto 58px minmax(0,1fr) auto!important' in CSS,
    'right feature compact css': '.design-info-panel .agent-feature-row' in CSS,
    'theme modal css': '.ui-layout-theme-target-modal{' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
print(f"v5.390 contract: {sum(checks.values())}/{len(checks)} PASS")
if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
