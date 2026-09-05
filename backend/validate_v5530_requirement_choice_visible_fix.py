from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
for token in ['requirement_edit_choices:choices','getPendingRequirementEdit','pendingEdit?.index===i','applyInteractiveRequirementChoice(choice,m.requirement_edit_prompt)','activeRequirementEditId&&input.trim()','requirement-choice-panel inline']:
    assert token in app, token
assert app.count('{interactiveRequirementId&&<div className="requirement-choice-panel">')==0
assert '.requirement-choice-panel.inline' in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.531'" in app
print('v5.531 requirement choice visibility: PASS')
