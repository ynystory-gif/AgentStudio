from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
CODEX=(ROOT/'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
SERVICE=(ROOT/'backend/app/services/generated_database_provision_service.py').read_text(encoding='utf-8')

checks={
 'version sync': "AGENTSTUDIO_FRONTEND_VERSION='5.459'" in APP and 'version="5.459"' in MAIN and '"version": "5.459"' in ROUTES and 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.459"' in CODEX,
 'separate database stage': "['08','DB 설정',databaseSetupSummary]" in APP and "builderSummaryTab==='DATABASE'" in APP,
 'five db decisions': all(x in APP for x in ['지금 DB 설정','연결 정보만 사용','DB 없이 Agent 생성','DB 설정 건너뛰기','Agent Editor에서 나중에 설정']),
 'three providers multi select': all(x in APP for x in ['PostgreSQL 사용','Google Cloud Firestore 사용','Redis 사용']),
 'use vs provision separated': APP.count('auto_provision')>15 and 'Agent 생성 시 DB 구조 자동 생성' in APP and 'Agent 생성 시 Firestore 구조 자동 구성' in APP and 'Agent 생성 시 Redis 초기 구조 구성' in APP,
 'postgres fields': all(x in APP for x in ['Database Name','Schema','Username','Password','SSL 사용','pgvector 사용','기존 DB / Schema 사용']),
 'firestore fields': all(x in APP for x in ['Google Cloud Project ID','Firestore Database ID','Credential / Service Account JSON','Region / Location','Emulator 사용','기존 Firestore Database 사용']),
 'redis fields': all(x in APP for x in ['Database Number','Key Prefix','TLS 사용','기존 Redis 사용']),
 'per provider connection analyze': '연결 테스트' in APP and '기존 구조 분석' in APP and '@router.post("/agent-database/analyze-existing")' in ROUTES,
 'resource plan preview': 'DB Resource Plan / DB 생성 계획 Preview' in APP and '@router.post("/agent-database/resource-plan")' in ROUTES,
 'user approval gate': '실제 DB 구조를 생성하기 전에 DB Resource Plan을 확인하고 사용자 승인을 완료해 주세요.' in APP and 'DB Resource Plan 사용자 승인이 필요합니다.' in SERVICE,
 'selective provision': '실제 구조 생성 포함' in APP and '전체 DB 생성 제외' in APP and 'include_in_provision' in SERVICE,
 'adapter architecture': all(x in SERVICE for x in ['class DatabaseProvisionPlan','class PostgreSQLProvision','class FirestoreProvision','class RedisProvision']),
 'postgres provision resources': all(x in SERVICE for x in ['CREATE DATABASE','CREATE SCHEMA IF NOT EXISTS','CREATE EXTENSION IF NOT EXISTS vector','cur.execute(ddl)']),
 'firestore provision language': 'Firestore DB 구조 구성 완료' in SERVICE and '__agentstudio_schema__' in SERVICE,
 'redis policy': all(x in SERVICE for x in ['SESSION:{{session_id}}','CACHE:{{hash}}','LOCK:{{resource}}','QUEUE:{{name}}','agentstudio:schema']),
 'failure retry skip': '재시도' in APP and '해당 DB만 Skip' in APP and 'Rollback 가능 여부' in APP,
 'secret policy': all(x in APP+SERVICE for x in ['POSTGRES_PASSWORD','REDIS_PASSWORD','GOOGLE_APPLICATION_CREDENTIALS']) and 'type="password"' in APP,
 'editor reuse': 'Agent Editor · Database 구성' in APP and 'DB 변경 영향 / Migration Plan' in APP,
 'resource plan persisted safe': 'database_resource_plan.generated.json' in SERVICE and 'database_resource_plan: dict = {}' in ROUTES,
 'styling': '.agent-db-resource-plan{' in CSS and '.agent-db-provision-result{' in CSS,
}
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit('v5.459 contract failed: '+', '.join(failed))
print(f'v5.459 contracts: {len(checks)}/{len(checks)} PASS')

sys.path.insert(0,str(ROOT/'backend'))
from app.services.generated_database_provision_service import build_database_resource_plan, validate_agent_database_setup
setup={
 'mode':'CONFIGURE',
 'postgresql':{'enabled':True,'use_in_agent':True,'auto_provision':True,'host':'localhost','port':5432,'database':'agentdb','schema':'agent','user':'postgres','pgvector':True,'role':''},
 'firestore':{'enabled':True,'use_in_agent':True,'auto_provision':True,'project_id':'demo','database_id':'(default)','initial_collections':'sessions,events','role':''},
 'redis':{'enabled':True,'use_in_agent':True,'auto_provision':True,'host':'localhost','port':6379,'db':0,'key_prefix':'AG_','role':''},
}
plan={'enabled':True,'schema_name':'agent','tables':[{'name':'documents','columns':[],'indexes':[['id']]},{'name':'document_chunks','columns':[{'name':'embedding','type':'VECTOR'}],'indexes':[]}], 'ddl':'SELECT 1;'}
validation=validate_agent_database_setup(setup)
assert validation['valid'] and len(validation['providers'])==3 and len(validation['provision_providers'])==3
resource=build_database_resource_plan(plan,setup)
assert resource['requires_approval'] and len(resource['providers'])==3 and not resource['approved']
assert any(x['provider']=='firestore' and len(x['resources']['collections'])>=2 for x in resource['providers'])
assert any(x['provider']=='redis' and len(x['resources']['key_patterns'])>=4 for x in resource['providers'])
connection_only={**setup,'mode':'CONNECTION_ONLY'}
validation2=validate_agent_database_setup(connection_only)
assert validation2['valid'] and validation2['provision_providers']==[]
no_db={'mode':'NO_DB'}
assert validate_agent_database_setup(no_db)['valid']
print('v5.459 service plan tests: PASS')
