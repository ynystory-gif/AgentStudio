from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
memo=(ROOT/'frontend/src/features/project/components/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
assert "workspaceTab==='CODE'&&codeRightPanelTab==='MEMO'?'memo-scroll-info-panel':''" in app
assert "panelMode === 'LIVE' ? 'live-mode' : 'memo-mode'" in memo
assert 'project-live-bottom-spacer' in memo
assert '.workspace-info-panel.memo-scroll-info-panel' in css
assert 'height:clamp(460px,58vh,760px)' in css
assert 'overflow-y:auto !important' in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.559'" in app
print('v5.559 memo live scroll: PASS')
