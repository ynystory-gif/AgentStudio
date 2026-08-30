from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
TOOLBAR = (ROOT/'frontend/src/components/ai/AgentDesignProjectManager.jsx').read_text(encoding='utf-8')
ENHANCER = (ROOT/'frontend/src/components/layout/ImportedThemePreviewEnhancer.jsx').read_text(encoding='utf-8')
BROWSER = (ROOT/'backend/app/services/ui_theme_browser_analysis_service.py').read_text(encoding='utf-8')
HYBRID = (ROOT/'backend/app/services/ui_theme_hybrid_analysis_service.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT/'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
MAIN = (ROOT/'backend/app/main.py').read_text(encoding='utf-8')

checks = {
    'frontend version 5.434': "AGENTSTUDIO_FRONTEND_VERSION='5.434'" in APP,
    'backend version 5.434': 'version="5.434"' in MAIN,
    'unsent interview input persisted': 'interview_input_draft:input' in APP,
    'unsent interview input restored': "setInput(String(snapshot?.interview_input_draft||''))" in APP,
    'project autosave can create first DB row': "void saveAgentDesignProject({silent:true})" in APP and "if(!designProjectId||designProjectSaving" not in APP,
    'project autosave reacts to input': '    input,\n    designFeatureRegistry,' in APP,
    'project autosave reacts to resume state': '    restoredBuildResume\n  ])' in APP,
    'silent autosave does not overwrite build status': 'if(!silent){' in APP and "Agent 설계 프로젝트 자동 저장 실패" in APP,
    'toolbar exposes autosave state': '● 자동 저장 ON' in TOOLBAR and '● 자동 저장 중...' in TOOLBAR and '✓ 자동 저장됨' in TOOLBAR,
    'manual save remains version snapshot': '💾 지금 저장' in TOOLBAR and '버전 Snapshot' in TOOLBAR,
    'rendered DOM captures icon evidence': "iconCandidates=Array.from(el.querySelectorAll('svg,img" in BROWSER,
    'rendered DOM captures navigation context': 'navigationContext:Boolean' in BROWSER,
    'browser contract emits item details': "'item_details':menu_candidates" in BROWSER,
    'browser contract emits icon text mode': "navigation_mode='icon_text'" in BROWSER,
    'browser contract emits icon size and side': "'icon_side':icon_side" in BROWSER and "'icon_size':icon_size" in BROWSER,
    'hybrid layout preserves item details': "layout['sourceNavigationItemDetails']" in HYBRID,
    'hybrid layout preserves presentation': "layout['sourceNavigationPresentation']" in HYBRID,
    'interactive preview consumes icon text': 'uiThemeSourceNavigation' in APP and 'ui-theme-preview-menu-icon' in APP,
    'wireframe enhancer consumes icon text': 'navigationPresentation' in ENHANCER and 'agentstudio-imported-nav-icon' in ENHANCER,
    'generated agent instruction covers icon text': 'sourceNavigationPresentation.mode가 icon_text' in WORKFLOW and "'아이콘 + 텍스트'" in WORKFLOW,
}
failed=[name for name,ok in checks.items() if not ok]
for name,ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit(f"v5.434 contract failed: {', '.join(failed)}")
print(f"v5.434 contract PASS {len(checks)}/{len(checks)}")
