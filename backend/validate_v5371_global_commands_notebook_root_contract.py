from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
OVER=(ROOT/'frontend/src/components/global/GlobalStudioOverlays.jsx').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
PS1=(ROOT/'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8-sig')
checks={
 'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.371'" in APP,
 'backend version': 'version="5.371"' in MAIN,
 'health version': '"version": "5.371"' in ROUTES,
 'launcher version': '$FallbackAgentStudioVersion = "5.371"' in PS1,
 'command palette import': 'GlobalCommandPalette' in APP and 'components/global/GlobalStudioOverlays' in APP,
 'ctrl k': "toLowerCase()==='k'" in APP and 'setCommandPaletteOpen(true)' in APP,
 'agent work center': 'AgentWorkCenterPanel' in APP and 'Agent 작업 센터' in APP,
 'help center': 'HelpCenterPanel' in APP and 'AgentStudio 사용 방법' in APP,
 'command count': OVER.count("id:") >= 7 or APP.count("category:") >= 20,
 'notebook root resolver': "editorFileRootRef.current?.[normalizedPath]" in APP and "fileTreeRootRef.current" in APP,
 'notebook no direct active root': "const normalizedPath=normalizeProjectRelativePath(filePath||selectedEditorFileRef.current||selected||'')\n    const workspaceRoot=activeWorkspaceRoot" not in APP,
 'styles': '.command-palette' in CSS and '.agent-work-center' in CSS and '.help-center-panel' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.371 contract: '+', '.join(failed))
print('PASS v5.371 Global Command Palette + Agent Work Center + Help Center + Notebook Root contract')
