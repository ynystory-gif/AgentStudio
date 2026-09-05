from pathlib import Path
import sys, re
ROOT=Path(__file__).resolve().parents[1]
routes=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')

# Schema/source regression for the exact HTTP 422 null failure.
for field in ['workflow_definition','report','coding_style_report','llm_usage_summary','db_erd','ui_layout']:
    assert f'{field}: dict | None = None' in routes, field
assert 'if not isinstance(data.get(dict_key), dict):' in routes
assert 'data[dict_key] = {}' in routes
assert "ui_layout:uiLayoutConfig||confirmedInterviewRequirements?.ui_layout||{}" in app

# Directly test the actual PPT builder for every supported downloadable deck/scope.
sys.path.insert(0,str(ROOT/'backend'))
from app.services.presentation_export_service import build_agentstudio_presentation

base={
    'project_name':'PPT Test',
    'project_root':'',
    'generated_at':'',
    'workflow_request':'',
    'workflow_definition':{},
    'report':{},
    'coding_style_report':{},
    'llm_usage_summary':{},
    'db_erd':{},
    'ui_layout':{},
}
cases=[
    ('AGENT','ALL'),
    ('AGENT','WORKFLOW'),
    ('AGENT','RUN'),
    ('AGENT','REPORT'),
    ('AGENT','ARCHITECTURE'),
    ('AGENT','DB_ERD'),
    ('STUDIO','ALL'),
]
for deck_type,scope in cases:
    payload=dict(base,deck_type=deck_type,scope=scope)
    content,filename=build_agentstudio_presentation(payload,'5.570')
    assert content[:2]==b'PK', (deck_type,scope,'not-pptx')
    assert len(content)>1000, (deck_type,scope,len(content))
    assert filename.lower().endswith('.pptx'), (deck_type,scope,filename)
    print(f'{deck_type}:{scope} PASS bytes={len(content)}')

print('v5.570 PPT all scopes + null-safe payload: PASS')
