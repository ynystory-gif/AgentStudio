from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
for token in [
 'routeRequirementToEditor',
 'openRequirementEditor',
 'requirement-common-editor',
 "setBuilderSummaryTab('RUNTIME')",
 "setBuilderSummaryTab('TOOL_PROMPT')",
 "setBuilderSummaryTab('DATABASE')",
 'setUiLayoutGalleryOpen(true)',
 "focusKey={requirementRouteFocus}",
 "focused={requirementRouteFocus==='tool_prompt'}",
 "onClick={()=>routeRequirementToEditor(item)}",
]:
    assert token in app, token
for token in ['requirement-route-focus','.requirement-common-choice-grid','@keyframes requirement-route-pulse']:
    assert token in css, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.533'" in app
assert 'version="5.533"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.533"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.533 requirement navigation hub: PASS')
