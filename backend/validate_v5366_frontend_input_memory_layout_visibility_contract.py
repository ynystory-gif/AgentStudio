from pathlib import Path
APP=Path('frontend/src/App.jsx').read_text(encoding='utf-8')
ROUTES=Path('backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN=Path('backend/app/main.py').read_text(encoding='utf-8')
checks={
 'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
 'backend version': 'version="5.369"' in MAIN,
 'health version': '"version": "5.369"' in ROUTES,
 'isolated search component': 'DebouncedProjectSearchInput' in APP and 'setLocalValue' in APP,
 'deferred project search': 'useDeferredValue(projectSearch)' in APP,
 'memoized project filtering': 'useMemo(()=>projectList' in APP,
 'bounded jobs': 'ids.length<=80' in APP,
 'terminal scrollback cap': 'scrollback:1500' in APP,
 'resource cleanup': "'app_unmount'" in APP and 'term?.dispose?.()' in APP,
 'workspace UI layout button': APP.count('builder-layout-button') >= 2,
 'workspace UI layout card': APP.count('ui-layout-choice-card') >= 2,
 'workspace UI layout gallery': "workspaceTab==='DESIGN'&&<UILayoutTemplateGallery" in APP,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('FAIL v5.369: '+', '.join(failed))
print('PASS v5.369 Frontend Input / Memory / Layout Visibility contract')
