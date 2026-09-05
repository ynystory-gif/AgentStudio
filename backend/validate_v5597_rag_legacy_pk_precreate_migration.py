from pathlib import Path
import ast
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')

def function_block(source: str, name: str) -> str:
    marker = f'async def {name}('
    start = source.index(marker)
    next_def = source.find('\nasync def ', start + len(marker))
    if next_def < 0:
        next_def = source.find('\ndef ', start + len(marker))
    return source[start: next_def if next_def >= 0 else len(source)]

app = read('frontend/src/app/App.tsx')
main = read('backend/app/main.py')
routes = read('backend/app/api/routes.py')
models = read('backend/app/models/rag_entities.py')
database = read('backend/app/core/database.py')
runtime_service = read('backend/app/services/database_runtime_service.py')
designer = read('backend/app/services/database_schema_design.py')
setup_ui = read('frontend/src/features/database/AgentDatabaseSetup.tsx')
workflow = read('backend/app/services/agent_workflow.py')
auth_service = read('backend/app/services/auth_service.py')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.597'" in app
assert 'version="5.597"' in main
assert '"version": "5.597"' in routes
assert 'TableSpecificPrimaryKeyNamingPolicy' in routes
assert 'TablePkUiBuildFix' in routes
assert 'RagLegacyPkPreCreateMigrationFix' in routes

expected = {
    'rag_studio_settings': 'studio_settings_id',
    'rag_collections': 'collections_id',
    'rag_sources': 'sources_id',
    'rag_collection_sources': 'collection_sources_id',
    'rag_documents': 'documents_id',
    'rag_chunks': 'chunks_id',
    'rag_embeddings': 'embeddings_id',
    'rag_index_jobs': 'index_jobs_id',
    'rag_retrieval_settings': 'retrieval_settings_id',
    'rag_search_logs': 'search_logs_id',
    'rag_agent_tools': 'agent_tools_id',
    'rag_workflow_bindings': 'workflow_bindings_id',
    'rag_agent_test_logs': 'agent_test_logs_id',
    'rag_intelligence_settings': 'intelligence_settings_id',
    'rag_recommendation_runs': 'recommendation_runs_id',
    'rag_source_operation_settings': 'source_operation_settings_id',
    'rag_sync_jobs': 'sync_jobs_id',
    'rag_document_versions': 'document_versions_id',
    'rag_document_security': 'document_security_id',
    'rag_access_rules': 'access_rules_id',
    'rag_search_audit_logs': 'search_audit_logs_id',
    'rag_evaluation_cases': 'evaluation_cases_id',
    'rag_evaluation_runs': 'evaluation_runs_id',
}

for table, pk in expected.items():
    marker = f'__tablename__ = "{table}"'
    assert marker in models, table
    start = models.index(marker)
    end = models.find('\nclass ', start + 1)
    block = models[start:end if end >= 0 else len(models)]
    assert f'mapped_column("{pk}", Integer, primary_key=True, autoincrement=True)' in block, (table, pk)
    assert f'"{table}": "{pk}"' in database

assert 'ForeignKey("rag_sources.sources_id")' in models
assert not re.search(r'ForeignKey\("rag_[a-z0-9_]+\.id"\)', models), 'legacy RAG FK target .id remains'
assert 'RENAME COLUMN "id" TO "{target_column}"' in database
assert 'prepare_rag_primary_key_compatibility_for_create_all' in database

# Critical v5.597 regression: legacy PK rename MUST happen before create_all.
for func in ('init_db', 'ensure_runtime_metadata_tables'):
    block = function_block(database, func)
    pre = block.index('prepare_rag_primary_key_compatibility_for_create_all')
    create = block.index('Base.metadata.create_all')
    assert pre < create, f'{func}: legacy RAG PK rename must happen before create_all'

# Supabase initialize/provision path must also pre-migrate before metadata creation.
service_pre = runtime_service.index('prepare_rag_primary_key_compatibility_for_create_all(', runtime_service.index('# v5.597:'))
service_create = runtime_service.index('Base.metadata.create_all', service_pre)
assert service_pre < service_create

# Startup must still apply the saved provider after local bootstrap; this avoids the
# observed auth cascade where a schema bootstrap failure left SessionLocal on local DB.
life = function_block(main, 'lifespan')
assert life.index('await init_db()') < life.index('await apply_saved_database_provider()')
assert '[AUTH] 로그인 계정 없음' in auth_service

# Preserve global DB naming policy and the prior TSX literal fix.
assert 'primary_key_column_name' in designer
assert 'Never generate a bare ``id`` PK for a new table.' in designer
assert 'common_policy.id_prefixes' in designer
assert '기본 PK 컬럼은 단순 id를 사용하지 말고' in workflow
assert "{'{table_name}_id'}" in setup_ui
assert not re.search(r'(?<![\'\"])\{table_name\}_id', setup_ui)

sys.path.insert(0, str(ROOT / 'backend'))
from app.core.table_naming_policy import primary_key_column_name
from app.services.database_schema_design import apply_common_table_policy

assert primary_key_column_name('rag_evaluation_cases') == 'evaluation_cases_id'
assert primary_key_column_name('rag_sources') == 'sources_id'
assert primary_key_column_name('app_users') == 'users_id'
assert primary_key_column_name('orders') == 'orders_id'

sample = {
    'tables': [
        {'name': 'rag_sources', 'columns': [
            {'name': 'id', 'type': 'BIGSERIAL', 'nullable': False, 'primary_key': True},
            {'name': 'name', 'type': 'TEXT'},
        ]},
        {'name': 'rag_sync_jobs', 'columns': [
            {'name': 'id', 'type': 'BIGSERIAL', 'nullable': False, 'primary_key': True},
            {'name': 'source_id', 'type': 'BIGINT', 'references': 'rag_sources.id'},
        ]},
    ]
}
normalized = apply_common_table_policy(sample)
by_name = {x['name']: x for x in normalized['tables']}
assert by_name['rag_sources']['columns'][0]['name'] == 'sources_id'
assert by_name['rag_sync_jobs']['columns'][0]['name'] == 'sync_jobs_id'
assert next(x for x in by_name['rag_sync_jobs']['columns'] if x['name'] == 'source_id')['references'] == 'rag_sources.sources_id'

for rel in [
    'backend/app/core/table_naming_policy.py',
    'backend/app/core/database.py',
    'backend/app/models/rag_entities.py',
    'backend/app/services/database_runtime_service.py',
    'backend/app/services/database_schema_design.py',
    'backend/app/main.py',
]:
    ast.parse(read(rel), filename=rel)

print('[PASS] v5.597 legacy RAG PK pre-create migration order + auth-provider cascade prevention contracts')
