from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
assert 'LLMTask.ANALYSIS' not in routes
assert 'model_for_task(LLMTask.REQUIREMENTS_ANALYSIS)' in routes
for token in ['promptEditingId','tool-prompt-list-item','tool-prompt-edit-form','AI 추천 Prompt 생성']:
    assert token in app, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.569'" in app
print('v5.569 Prompt Registry list UI + LLMTask fix: PASS')
