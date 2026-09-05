from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
WF=(ROOT/'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
SEL=(ROOT/'backend/app/services/coding_rule_selector.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
REG=json.loads((ROOT/'backend/app/data/coding_style/rules.json').read_text(encoding='utf-8'))
keys=['staged_data_flow','validate_key_results','safe_resource_management','external_io_validation','preserve_source_metadata','normalize_external_data','prefer_lazy_loading','avoid_global_warning_suppression']
assert "AGENTSTUDIO_FRONTEND_VERSION='5.491'" in APP
assert 'version="5.491"' in MAIN and '"version": "5.491"' in ROUTES
assert all(f'{k}:true' in APP and f'"{k}": True' in WF for k in keys)
assert all(x in APP for x in ['데이터 · 안정성','외부 · 운영'])
assert REG.get('version')=='1.9'
ids={r.get('id') for r in REG.get('rules') or []}
assert all(f'CS-{n}' in ids for n in range(154,163))
assert all(x in SEL for x in ['data_pipeline','document_loader','pymupdf','easyocr'])
assert 'source, page/pdf_page, id, date, tags' in WF
print('v5.491 document-driven coding style contract: ALL PASS')
