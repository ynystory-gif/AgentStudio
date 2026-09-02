from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')

checks = []
def require(name: str, cond: bool):
    checks.append((name, bool(cond)))
    if not cond:
        raise AssertionError(name)

schema = read('backend/app/services/learning_relational_schema_service.py')
internal = read('backend/app/services/learning_internal_call_filter_bridge.py')
job = read('backend/app/services/learning_finetune_job_service.py')
ready = read('backend/app/services/learning_finetune_readiness_bridge.py')
db_runtime = read('backend/app/services/database_runtime_service.py')
main = read('backend/app/main.py')
app = read('frontend/src/App.jsx')
codex = read('backend/app/services/codex_app_server_service.py')
routes = read('backend/app/api/routes.py')

require('schema cache', '_LEARNING_SCHEMA_READY' in schema)
require('process migration lock', '_LEARNING_SCHEMA_MIGRATION_LOCK = asyncio.Lock()' in schema)
require('read-only guard', 'async def assert_learning_relational_schema_ready()' in schema)
require('read-only inspection', 'information_schema.columns' in schema and 'pg_indexes' in schema)
require('migration advisory lock', 'pg_advisory_xact_lock' in schema)
require('migration lock timeout', "SET LOCAL lock_timeout = '5s'" in schema)
require('migration statement timeout', "SET LOCAL statement_timeout = '60s'" in schema)
require('actual DDL still lifecycle-owned', 'ALTER TABLE {qschema}.\\"llm_learning_datasets\\"' in schema)
require('fine-tune capability uses read-only guard', 'await assert_learning_relational_schema_ready()' in ready and 'ensure_learning_relational_schema' not in ready)
require('fine-tune job rows use read-only guard', 'await assert_learning_relational_schema_ready()' in job and 'ensure_learning_relational_schema' not in job)
require('misjudgment runtime sync uses read-only guard', 'relational = await assert_learning_relational_schema_ready()' in internal)
require('startup owns migration', 'learning_schema = await ensure_learning_relational_schema()' in main)
require('runtime provider switch owns migration', db_runtime.count('await _prepare_learning_schema_after_runtime_rebind()') >= 2)
require('frontend version', "AGENTSTUDIO_FRONTEND_VERSION='5.446'" in app)
require('backend version', 'version="5.446"' in main and '"version": "5.446"' in routes)
require('codex version', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.446"' in codex)
require('build trace', 'LearningSchemaDeadlockGuard' in routes)

print(f'v5.446 contracts: {len(checks)}/{len(checks)} PASS')
