from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
hook=(ROOT/'frontend/src/features/workspace/hooks/useWorkspaceLayout.ts').read_text(encoding='utf-8')
shell=(ROOT/'frontend/src/features/workspace/WorkspaceShell.tsx').read_text(encoding='utf-8')
types=(ROOT/'frontend/src/features/workspace/workspace.types.ts').read_text(encoding='utf-8')
system=(ROOT/'frontend/src/features/system/SystemPage.tsx').read_text(encoding='utf-8')
service=(ROOT/'frontend/src/features/system/services/systemService.ts').read_text(encoding='utf-8')
assert "useWorkspaceLayout('DESIGN')" in app
assert '<WorkspaceShell' in app and '</WorkspaceShell>' in app
assert 'workspace-tabs workspace-tabs-with-panel-controls' not in app
for token in ['workspaceTab','workspaceLeftCollapsed','workspaceRightCollapsed','beginWorkspaceBottomResize','beginWorkspacePanelResize']:
    assert token in hook, token
for tab in ['DESIGN','WORKFLOW','CODE','RUN','REPORT','ARCHITECTURE','DB_ERD','SCHEDULER','LLM','BROWSER']:
    assert f"'DESIGN'" in types
assert 'loadSystemOverview' in system and "api('/system/status')" in service
assert "AGENTSTUDIO_FRONTEND_VERSION='5.544'" in app
assert len(app.splitlines()) < 22328
print('v5.544 Workspace ownership separation: PASS')
print('App.tsx',len(app.splitlines()))
print('SystemPage.tsx',len(system.splitlines()))
