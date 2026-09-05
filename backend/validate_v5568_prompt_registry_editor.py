from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
for token in ['default_prompt_text','ai_recommended_prompt_text','custom_prompt_text','AI 추천 Prompt 생성','effective_prompt_text']:
    assert token in app, token
assert '/workflow/prompt-module/recommend' in app
assert '@router.post("/workflow/prompt-module/recommend")' in routes
assert 'class PromptModuleRecommendRequest(BaseModel):' in routes
assert "AGENTSTUDIO_FRONTEND_VERSION='5.568'" in app
print('v5.568 Prompt Registry editor: PASS')
