from pathlib import Path
import ast
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')

app = read('frontend/src/app/App.tsx')
main = read('backend/app/main.py')
routes = read('backend/app/api/routes.py')
models = read('backend/app/models/rag_entities.py')
database = read('backend/app/core/database.py')
designer = read('backend/app/services/database_schema_design.py')
setup_ui = read('frontend/src/features/database/AgentDatabaseSetup.tsx')
workflow = read('backend/app/services/agent_workflow.py')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.596'" in app
assert 'version="5.596"' in main
assert '"version": "5.596"' in routes
assert 'TableSpecificPrimaryKeyNamingPolicy' in routes
assert 'TablePkUiBuildFix' in routes

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

assert not re.search(r'ForeignKey\("rag_[a-z0-9_]+\.id"\)', models), 'legacy RAG FK target .id remains'

for table, pk in expected.items():
    assert f'"{table}": "{pk}"' in database
assert 'RENAME COLUMN "id" TO "{target_column}"' in database
assert '_migrate_rag_primary_key_column_names' in database

assert 'primary_key_column_name' in designer
assert 'Never generate a bare ``id`` PK for a new table.' in designer
assert 'ref_column == "id"' in designer
assert 'common_policy.id_prefixes' in designer
assert '기본 PK 컬럼은 단순 id를 사용하지 말고' in workflow
assert 'rag_chunks→chunks_id' in workflow

# v5.596 regression: display {table_name}_id literally without TSX treating table_name as an identifier.
assert "{'{table_name}_id'}" in setup_ui, 'safe literal {table_name}_id rendering missing'
assert not re.search(r'(?<![\'\"])\{table_name\}_id', setup_ui), 'raw {table_name}_id JSX expression would cause TS2304'

sys.path.insert(0, str(ROOT / 'backend'))
from app.core.table_naming_policy import primary_key_column_name
from app.services.database_schema_design import apply_common_table_policy, MODULE_REGISTRY

assert primary_key_column_name('rag_evaluation_cases') == 'evaluation_cases_id'
assert primary_key_column_name('rag_chunks') == 'chunks_id'
assert primary_key_column_name('app_users') == 'users_id'
assert primary_key_column_name('orders') == 'orders_id'
assert primary_key_column_name('acme_orders', prefixes=['acme_']) == 'orders_id'

sample = {
    'tables': [
        {'name': 'rag_chunks', 'columns': [
            {'name': 'id', 'type': 'BIGSERIAL', 'nullable': False, 'primary_key': True},
            {'name': 'content', 'type': 'TEXT'},
        ]},
        {'name': 'rag_embeddings', 'columns': [
            {'name': 'id', 'type': 'BIGSERIAL', 'nullable': False, 'primary_key': True},
            {'name': 'chunk_id', 'type': 'BIGINT', 'references': 'rag_chunks.id'},
        ]},
        {'name': 'orders', 'columns': [{'name': 'name', 'type': 'TEXT'}]},
    ]
}
normalized = apply_common_table_policy(sample)
by_name = {x['name']: x for x in normalized['tables']}
assert by_name['rag_chunks']['columns'][0]['name'] == 'chunks_id'
assert by_name['rag_embeddings']['columns'][0]['name'] == 'embeddings_id'
assert next(x for x in by_name['rag_embeddings']['columns'] if x['name'] == 'chunk_id')['references'] == 'rag_chunks.chunks_id'
assert by_name['orders']['columns'][0]['name'] == 'orders_id'

registry_tables = []
for module in MODULE_REGISTRY.values():
    registry_tables.extend(module.get('tables') or [])
registry_normalized = apply_common_table_policy({'tables': registry_tables})
for table in registry_normalized['tables']:
    pk_cols = [c for c in table.get('columns') or [] if c.get('primary_key')]
    assert pk_cols, f"missing PK: {table.get('name')}"
    assert all(c.get('name') != 'id' for c in pk_cols), f"bare id remains: {table.get('name')}"
    for col in table.get('columns') or []:
        ref = str(col.get('references') or '')
        assert not ref.endswith('.id'), f"legacy FK reference remains: {table.get('name')}.{col.get('name')} -> {ref}"

for rel in [
    'backend/app/core/table_naming_policy.py',
    'backend/app/core/database.py',
    'backend/app/models/rag_entities.py',
    'backend/app/services/database_schema_design.py',
]:
    ast.parse(read(rel), filename=rel)

print('[PASS] v5.596 table PK UI build fix + table-specific Primary Key naming contracts')
