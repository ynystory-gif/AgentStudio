from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


main_py = text(BACKEND / 'app/main.py')
routes_py = text(BACKEND / 'app/api/routes.py')
models_py = text(BACKEND / 'app/models/account_setting_entities.py')
service_py = text(BACKEND / 'app/services/account_setting_service.py')
account_api_py = text(BACKEND / 'app/api/account_settings_routes.py')
rag_routes_py = text(BACKEND / 'app/api/rag_routes.py')
sql_service_py = text(BACKEND / 'app/services/sql_workspace_service.py')
database_py = text(BACKEND / 'app/core/database.py')
app_tsx = text(FRONTEND / 'src/app/App.tsx')
db_tsx = text(FRONTEND / 'src/features/database/AgentDatabaseSetup.tsx')
rag_tsx = text(FRONTEND / 'src/features/rag/components/RagStudio.tsx')
rag_api_ts = text(FRONTEND / 'src/features/rag/ragApi.ts')
history_tsx = text(FRONTEND / 'src/features/history/ProjectHistoryPanel.tsx')
history_css = text(FRONTEND / 'src/features/history/projectHistory.css')
styles_css = text(FRONTEND / 'src/styles.css')
rag_css = text(FRONTEND / 'src/features/rag/ragStudio.css')

# Version contract.
require('version="5.599"' in main_py, 'Backend FastAPI version is not 5.599')
require("AGENTSTUDIO_FRONTEND_VERSION='5.599'" in app_tsx, 'Frontend version is not 5.599')
require('"version": "5.599"' in routes_py and 'AccountProjectSettingsDbHistory' in routes_py, 'Health/build marker is missing')

# New DB entities and table-name PK policy.
expected_pks = {
    'account_database_profiles': 'account_database_profiles_id',
    'account_setting_profiles': 'account_setting_profiles_id',
    'account_project_settings': 'account_project_settings_id',
    'project_setting_histories': 'project_setting_histories_id',
}
for table_name, pk_name in expected_pks.items():
    require(f'__tablename__ = "{table_name}"' in models_py, f'Model table missing: {table_name}')
    require(re.search(rf'\b{re.escape(pk_name)}\b[^\n]*primary_key=True[^\n]*autoincrement=True', models_py) is not None,
            f'Table-specific autoincrement PK missing: {table_name}.{pk_name}')
require(re.search(r'^\s*id\s*:', models_py, re.M) is None, 'New account/project setting models must not define bare id PK')
require('import app.models.account_setting_entities' in database_py, 'New settings models are not registered before create_all')

# Secret policy: account DB metadata table must not define credential material.
model_lower = models_py.lower()
for forbidden in ('password:', 'private_key:', 'token:', 'api_key:', '_password_dpapi:'):
    require(forbidden not in model_lower, f'Secret field leaked into AccountDatabaseProfile model: {forbidden}')
for secret_key in ("'password'", "'_password_dpapi'", "'private_key'", "'token'", "'api_key'"):
    require(secret_key in service_py, f'Secret scrubbing rule missing: {secret_key}')
require('WINDOWS_DPAPI' in service_py, 'Credential storage contract must preserve Windows DPAPI semantics')

# Account/project settings APIs.
for endpoint in (
    "@router.get('/database-profiles')", "@router.post('/database-profiles')",
    "@router.get('/project')", "@router.put('/project')",
    "@router.get('/history')", "@router.get('/history/{history_id}')",
):
    require(endpoint in account_api_py, f'Account settings API missing: {endpoint}')
require('app.include_router(account_settings_router, prefix="/api")' in main_py, 'Account settings router is not mounted')

# SQL workspace: account list + project binding + account profile apply.
require('account_connections' in routes_py, 'SQL workspace status does not expose account DB profiles')
require('CODE_EDITOR_DB' in routes_py, 'SQL workspace project DB binding is missing')
require('/sql/account-profile/apply' in routes_py, 'Account DB profile apply endpoint is missing')
require('_password_dpapi' in sql_service_py, 'SQL workspace DPAPI credential reuse path is missing')

# Manual design save syncs normalized project setting groups; no autosave is introduced here.
require('sync_account_design_snapshot' in routes_py, 'Manual Agent Design save is not synchronized to project settings')
for group in ('REQUIREMENTS', 'RUNTIME', 'DATABASE', 'DATABASE_RESOURCE_PLAN', 'UI_LAYOUT', 'TOOL_PROMPT', 'PROMPT_TOOL_STUDIO', 'DEVELOPMENT_STAGE', 'CODING_STYLE'):
    require(group in service_py, f'Design setting group missing: {group}')

# RAG changes write history and project settings.
require('append_project_history' in rag_routes_py, 'RAG routes do not write project history')
for marker in ('RAG_KNOWLEDGE', 'RAG_RETRIEVAL', 'RAG_INTELLIGENCE', 'RAG_OPERATION', 'RAG_SECURITY', 'RAG_EVALUATION'):
    require(marker in rag_routes_py, f'RAG history category missing: {marker}')
require('RAG_DATABASE_PROFILE' in rag_tsx, 'RAG project DB account binding is missing')
require('loadAccountProjectSettings' in rag_api_ts and 'saveAccountProjectSetting' in rag_api_ts, 'RAG account/project API client missing')

# UI: History is immediately to the right of RAG Studio in the design-center tab strip.
rag_button = app_tsx.find("changeDesignCenterTab('RAG')")
history_button = app_tsx.find("changeDesignCenterTab('HISTORY')")
require(rag_button >= 0 and history_button > rag_button, 'History tab must appear after RAG Studio')
between = app_tsx[rag_button:history_button]
require('changeDesignCenterTab(' not in between[between.find(')>RAG Studio</button>') + 1:] if ')>RAG Studio</button>' in between else True,
        'Another design-center tab appears between RAG Studio and History')
require('>이력 정보</button>' in app_tsx, 'History Info tab label missing')
require('ProjectHistoryPanel' in app_tsx, 'History panel is not rendered')
for marker in ('변경 전', '변경 후', '/account-settings/history', 'setFilter'):
    require(marker in history_tsx, f'History detail UI missing: {marker}')

# UI: account DB list is exposed in all three requested locations.
require('계정 저장 DB 연결' in app_tsx and '/sql/account-profile/apply' in app_tsx, 'Code Editor account DB list/apply UI missing')
require('계정 저장 DB 설정' in db_tsx and '/account-settings/project' in db_tsx, 'Agent Database account DB list UI missing')
require('계정 저장 DB 설정 선택' in rag_tsx, 'RAG Studio account DB list UI missing')

# New UI must respect 13px text floor.
for css_name, css in (('history', history_css), ('styles', styles_css), ('rag', rag_css)):
    for match in re.finditer(r'font-size\s*:\s*([0-9.]+)px', css):
        require(float(match.group(1)) >= 13.0, f'{css_name} CSS contains font-size below 13px: {match.group(0)}')

print('[PASS] v5.599 account/project settings DB + account DB list + project history contracts')
