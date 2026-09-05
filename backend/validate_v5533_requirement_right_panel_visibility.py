from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
for token in [
 'scrollRequirementRightPanel',
 "scrollRequirementRightPanel('requirement-common-editor')",
 "scrollRequirementRightPanel('agent-tool-prompt-settings')",
 "scrollRequirementRightPanel('agent-database-settings')",
 'requirement-route-banner',
 "focused={requirementRouteFocus==='tool_prompt'}",
 'focusKey={requirementRouteFocus}',
]: assert token in app, token
# Common editor must render before the long requirement list.
assert app.find('id="requirement-common-editor"', app.find('requirement-collection-card active-design')) < app.find('className="requirement-value-list"', app.find('requirement-collection-card active-design'))
assert '.requirement-route-banner' in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.533'" in app
print('v5.533 requirement right-panel visibility: PASS')
