from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "backend/app/services/generated_database_provision_service.py").read_text(encoding="utf-8")

checks = {
    "version sync": "AGENTSTUDIO_FRONTEND_VERSION='5.458'" in APP and 'version="5.458"' in MAIN and '"version": "5.458"' in ROUTES and 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.458"' in CODEX,
    "new agent db panel": "DB 연결 · 자동 생성 설정" in APP and "AgentDatabaseSetupPanel" in APP,
    "explicit skip": "이번 생성에서는 DB 연결 설정 스킵" in APP and "mode:'PENDING'" in APP,
    "three providers": all(token in APP for token in ["PostgreSQL", "Google Cloud Firestore", "Redis"]),
    "postgres fields": all(token in APP for token in ["Schema", "SSL Mode", "AGENT_POSTGRES_PASSWORD"]),
    "firestore fields": all(token in APP for token in ["Project ID", "Service Account JSON 경로", "초기 Collection", "GOOGLE_APPLICATION_CREDENTIALS"]),
    "redis fields": all(token in APP for token in ["DB Index", "Key Prefix", "AGENT_REDIS_PASSWORD"]),
    "connection test endpoint": '@router.post("/agent-database/test")' in ROUTES and "test_agent_database_setup" in ROUTES,
    "project create carries setup": "database_setup: dict = {}" in ROUTES and "database_setup:agentDatabaseSetup" in APP,
    "postgres ddl provision": "cur.execute(ddl)" in SERVICE and "CREATE SCHEMA IF NOT EXISTS" in SERVICE,
    "firestore collection provision": "__agentstudio_schema__" in SERVICE and "batch.commit()" in SERVICE,
    "redis keyspace provision": 'agentstudio:schema' in SERVICE and "client.hset" in SERVICE,
    "secrets not in safe config": "password_env" in SERVICE and "credentials_env" in SERVICE and '"password":' not in SERVICE.split("def sanitize_agent_database_setup",1)[1].split("def validate_agent_database_setup",1)[0],
    "runtime config generated": "database_runtime.generated.json" in SERVICE,
    "create response provision status": '"database_provision": database_provision' in ROUTES,
    "db setup styling": ".agent-db-setup-card{" in CSS and ".agent-db-provider-list{" in CSS,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.458 contract failed: " + ", ".join(failed))
print(f"v5.458 contracts: {len(checks)}/{len(checks)} PASS")
