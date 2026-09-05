from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
for token in ['interactiveRequirementId','getRequirementInteractiveChoices','beginInteractiveRequirementEdit','applyInteractiveRequirementChoice','applyInteractiveRequirementValue','requirement-choice-panel','onClick={()=>beginInteractiveRequirementEdit(item)}']:
    assert token in app, token
assert "activeRequirementEditId&&input.trim()" in app
assert "requirement-value-row:hover" in css
assert ".requirement-choice-grid" in css
assert "AGENTSTUDIO_FRONTEND_VERSION='5.530'" in app
print('v5.530 Interactive Requirement Editor: PASS')
