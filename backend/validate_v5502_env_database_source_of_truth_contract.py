from pathlib import Path

ROOT = Path(__file__).resolve().parent
config = (ROOT / "app/core/config.py").read_text(encoding="utf-8")
database = (ROOT / "app/core/database.py").read_text(encoding="utf-8")
settings_service = (ROOT / "app/services/settings_service.py").read_text(encoding="utf-8")

def require(cond, msg):
    if not cond:
        raise AssertionError(msg)

require("postgres:postgres@127.0.0.1" not in config, "hard-coded postgres/postgres fallback remains")
require('database_url: str = ""' in config, "DATABASE_URL must not have credential fallback")
require('langgraph_database_url: str = ""' in config, "LANGGRAPH_DATABASE_URL must not have credential fallback")
require('PROJECT_ENV_PATH = PROJECT_ROOT / ".env"' in config, "project root .env fallback missing")
require('BACKEND_ENV_PATH = BACKEND_ROOT / ".env"' in config, "backend .env override missing")
require('merged.update(_parse_env_file(PROJECT_ENV_PATH))' in config, "project .env merge missing")
require('merged.update(_parse_env_file(BACKEND_ENV_PATH))' in config, "backend .env priority merge missing")
require("DATABASE_URL이 설정되지 않았습니다" in database, "missing DATABASE_URL guard missing")
require('PROJECT_ENV_PATH = PROJECT_ROOT / ".env"' in settings_service, "settings service root .env fallback missing")
print("PASS v5.502 .env database source-of-truth contract")
