from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/generated_database_provision_service.py').read_text(encoding='utf-8')
README = (ROOT / 'README_V5_482.md').read_text(encoding='utf-8')

passed = 0
failed = 0

def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f'[PASS] {name}')
    else:
        failed += 1
        print(f'[FAIL] {name}')

check('frontend version 5.482', "AGENTSTUDIO_FRONTEND_VERSION='5.482'" in APP)
check('backend version 5.482', 'version="5.482"' in MAIN)
check('health version 5.482', '"version": "5.482"' in ROUTES)
check('codex client version 5.482', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.482"' in CODEX)
check('health build marker', '+AttachmentSummaryFileOpen+ManualDatabaseResourceCreate+Global13pxTextFloor' in ROUTES)

check('attachment summary accepts file-open callback', 'onOpenFile=null' in APP)
check('attachment summary preserves project relative path', 'project_relative_path:String(item?.project_relative_path||item?.relative_path||\'\')' in APP)
check('attachment source summary keeps project relative path', "project_relative_path:String(item?.project_relative_path||'')" in APP)
check('attachment chip renders button', '클릭하여 파일 열기' in APP and 'onClick={()=>onOpenFile(item)}' in APP)
check('attachment open helper exists', 'const openAttachmentSummaryFile=async(file)=>' in APP)
check('attachment helper derives path under project root', 'sourcePath.toLowerCase().startsWith(`${normalizedRoot.toLowerCase()}/`)' in APP)
check('all attachment summary surfaces wire open callback', APP.count('onOpenFile={openAttachmentSummaryFile}') >= 3)
check('attachment button hover style', '.attachment-ai-summary-files button:hover' in CSS)

check('postgres schema button exists', 'PostgreSQL 스키마 생성' in APP)
check('firestore database button exists', 'Firestore Database 생성' in APP)
check('manual create state is tracked', 'agentDatabaseCreateBusy' in APP and 'agentDatabaseCreateResult' in APP)
check('manual create asks confirmation', 'PostgreSQL 스키마를 생성하시겠습니까?' in APP and 'Google Cloud Firestore Database를 생성하시겠습니까?' in APP)
check('connection-only disables resource create', APP.count("setup.mode==='CONNECTION_ONLY'") >= 3)
check('postgres schema endpoint exists', '@router.post("/agent-database/postgresql/create-schema")' in ROUTES)
check('firestore database endpoint exists', '@router.post("/agent-database/firestore/create-database")' in ROUTES)
check('postgres schema service is limited to schema create', 'def create_postgresql_schema_resource' in SERVICE and 'CREATE SCHEMA IF NOT EXISTS' in SERVICE)
check('firestore create uses official admin REST host', 'https://firestore.googleapis.com/v1/projects/' in SERVICE)
check('firestore create requires location', 'Region / Location을 입력하세요' in SERVICE)
check('firestore create handles already-existing database', 'already_exists' in SERVICE and 'status_code == 409' in SERVICE)
check('firestore create polls long-running operation', 'operation_name' in SERVICE and 'payload.get("done")' in SERVICE)
check('resource create visual style exists', '.agent-db-provider-actions button.resource-create' in CSS)

# Product-wide authored text-size floor: explicit px font sizes and React numeric fontSize.
small_font_hits: list[str] = []
font_size_pattern = re.compile(r'font-size\s*:\s*([0-9.]+)px', re.I)
font_shorthand_pattern = re.compile(r'\bfont\s*:\s*[^;{}]*?\b([0-9.]+)px\b', re.I)
font_size_js_pattern = re.compile(r'fontSize\s*:\s*([0-9.]+)')
for path in (ROOT / 'frontend').rglob('*'):
    if 'node_modules' in path.parts or path.suffix.lower() not in {'.css', '.js', '.jsx', '.ts', '.tsx', '.html'}:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    for pattern in (font_size_pattern, font_shorthand_pattern, font_size_js_pattern):
        for match in pattern.finditer(text):
            if float(match.group(1)) < 13:
                small_font_hits.append(f'{path.relative_to(ROOT)}:{match.group(0)}')
check('no explicit frontend font size below 13px', not small_font_hits)
check('13px readability token documented in css', '--agentstudio-min-text-size:13px' in CSS)
check('release README documents three requested changes', 'PostgreSQL Schema' in README and 'Firestore Database' in README and '최소 13px' in README)

print(f'\nTOTAL: {passed} PASS / {failed} FAIL')
if small_font_hits:
    print('Below-13px hits:')
    for item in small_font_hits[:30]:
        print(' -', item)
raise SystemExit(1 if failed else 0)
