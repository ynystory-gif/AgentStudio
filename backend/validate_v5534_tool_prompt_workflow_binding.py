from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
css=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
for token in [
 'recommended_tools_auto_apply',
 'workflow_binding_enabled',
 'prompt_modules',
 'tool_profiles',
 'Request Analyzer',
 'Intent Classification',
 'Structured Extraction',
 'Answer Generation',
 'Result Validation',
 'Project File Search',
 'File Reader',
 'Tool Registry',
 'Prompt Registry',
 'Workflow 연결',
 '★ 추천 Tool 적용',
 'Prompt Nodes:',
 'Tool Nodes:',
]:
    assert token in app, token
for token in ['.tool-prompt-registry-section','.tool-prompt-workflow-map','.tool-profile-row']:
    assert token in css, token
assert "AGENTSTUDIO_FRONTEND_VERSION='5.534'" in app
assert 'version="5.534"' in (ROOT/'backend/app/main.py').read_text(encoding='utf-8')
assert '"version": "5.534"' in (ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
print('v5.534 Tool/Prompt Workflow Binding: PASS')
