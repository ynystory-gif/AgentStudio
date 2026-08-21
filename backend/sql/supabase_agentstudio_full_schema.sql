-- ============================================================
-- THEANOVA AgentStudio - Supabase PostgreSQL Full Schema
-- v5.284 SupabaseIdempotentSchemaProvisioningFix
--
-- Supabase SQL Editor에서 실행할 수 있는 전체 초기 스키마입니다.
-- AgentStudio ORM 테이블 + pgvector를 멱등 방식으로 준비합니다.
-- LangGraph Checkpointer는 설치된 Python 패키지의 AsyncPostgresSaver.setup()이
-- authoritative migration source이므로 이 SQL에서 수동 정의하지 않습니다.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- AgentStudio core tables
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    root_path VARCHAR(1000) NOT NULL UNIQUE,
    cache_path VARCHAR(1000) NOT NULL DEFAULT '',
    temp_path VARCHAR(1000) NOT NULL DEFAULT '',
    output_path VARCHAR(1000) NOT NULL DEFAULT '',
    venv_path VARCHAR(1000) NOT NULL DEFAULT '',
    models_path VARCHAR(1000) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP NULL,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES projects(id),
    thread_id VARCHAR(100) NOT NULL DEFAULT 'default',
    role VARCHAR(30) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS requirements (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES projects(id),
    key VARCHAR(150) NOT NULL,
    value TEXT NOT NULL,
    confirmed BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    transport VARCHAR(50) NOT NULL DEFAULT 'streamable_http',
    endpoint VARCHAR(1000) NOT NULL DEFAULT '',
    command VARCHAR(1000) NOT NULL DEFAULT '',
    args JSON NOT NULL DEFAULT '[]'::json,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    trust_level VARCHAR(30) NOT NULL DEFAULT 'UNTRUSTED',
    allow_read_without_prompt BOOLEAN NOT NULL DEFAULT FALSE,
    allow_write_without_prompt BOOLEAN NOT NULL DEFAULT FALSE,
    last_status VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    protocol_version VARCHAR(50) NOT NULL DEFAULT '',
    supports_tool_list_changed BOOLEAN NOT NULL DEFAULT FALSE,
    discovered_at TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_registry (
    id SERIAL PRIMARY KEY,
    mcp_server_id INTEGER NULL REFERENCES mcp_servers(id),
    provider VARCHAR(200) NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category VARCHAR(100) NOT NULL DEFAULT 'UNKNOWN',
    subcategory VARCHAR(100) NOT NULL DEFAULT 'UNKNOWN',
    capability VARCHAR(200) NOT NULL DEFAULT 'unknown',
    risk_level INTEGER NOT NULL DEFAULT 0,
    requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    input_schema JSON NOT NULL DEFAULT '{}'::json,
    annotations JSON NOT NULL DEFAULT '{}'::json,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mcp_tool UNIQUE (mcp_server_id, name)
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    summary TEXT NOT NULL,
    payload JSON NOT NULL DEFAULT '{}'::json,
    risk_level INTEGER NOT NULL DEFAULT 0,
    server_trust_level VARCHAR(30) NOT NULL DEFAULT 'UNTRUSTED',
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memory_records (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES projects(id),
    memory_type VARCHAR(30) NOT NULL,
    key VARCHAR(250) NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSON NOT NULL DEFAULT '{}'::json,
    embedding vector NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_file_index (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES projects(id),
    path VARCHAR(1200) NOT NULL,
    language VARCHAR(50) NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    symbols JSON NOT NULL DEFAULT '[]'::json,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_project_file UNIQUE (project_id, path)
);

CREATE TABLE IF NOT EXISTS evaluation_records (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES projects(id),
    metric VARCHAR(100) NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    details JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_records (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES projects(id),
    provider VARCHAR(100) NOT NULL,
    model VARCHAR(150) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(64) PRIMARY KEY,
    kind VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    result JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agentstudio_machines (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL UNIQUE,
    host_name VARCHAR(255) NOT NULL DEFAULT '',
    os_name VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL DEFAULT '',
    key VARCHAR(150) NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_app_settings_pc_name_key UNIQUE (pc_name, key)
);

CREATE INDEX IF NOT EXISTS ix_app_settings_key ON app_settings(key);
CREATE INDEX IF NOT EXISTS ix_app_settings_pc_name ON app_settings(pc_name);
CREATE INDEX IF NOT EXISTS ix_agentstudio_machines_pc_name ON agentstudio_machines(pc_name);

CREATE TABLE IF NOT EXISTS project_analyses (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    project_root VARCHAR(1200) NOT NULL,
    project_name VARCHAR(300) NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    tech_stack JSON NOT NULL DEFAULT '[]'::json,
    entry_points JSON NOT NULL DEFAULT '[]'::json,
    major_files JSON NOT NULL DEFAULT '[]'::json,
    mcp_tools JSON NOT NULL DEFAULT '[]'::json,
    structure JSON NOT NULL DEFAULT '{}'::json,
    raw_analysis JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Compatibility upgrades for existing AgentStudio databases
-- ------------------------------------------------------------

ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS cache_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS temp_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS output_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS venv_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS models_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMP NULL;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE IF EXISTS app_settings
    ADD COLUMN IF NOT EXISTS pc_name VARCHAR(255) NOT NULL DEFAULT '';

-- Older AgentStudio builds could have UNIQUE(key). Remove only that legacy one-column
-- unique constraint so shared DB settings can use (pc_name, key) instead.
DO $$
DECLARE r RECORD;
BEGIN
  IF to_regclass('public.app_settings') IS NOT NULL THEN
    FOR r IN
      SELECT c.conname
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
      JOIN pg_namespace n ON n.oid = t.relnamespace
      WHERE n.nspname = current_schema()
        AND t.relname = 'app_settings'
        AND c.contype = 'u'
        AND array_length(c.conkey, 1) = 1
        AND EXISTS (
          SELECT 1
          FROM unnest(c.conkey) AS k(attnum)
          JOIN pg_attribute a
            ON a.attrelid = c.conrelid AND a.attnum = k.attnum
          WHERE a.attname = 'key'
        )
    LOOP
      EXECUTE format('ALTER TABLE app_settings DROP CONSTRAINT %I', r.conname);
    END LOOP;
  END IF;
END $$;

DROP INDEX IF EXISTS ix_app_settings_key;
CREATE INDEX IF NOT EXISTS ix_app_settings_key ON app_settings(key);
CREATE INDEX IF NOT EXISTS ix_app_settings_pc_name ON app_settings(pc_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_app_settings_pc_name_key ON app_settings(pc_name, key);
CREATE INDEX IF NOT EXISTS ix_agentstudio_machines_pc_name ON agentstudio_machines(pc_name);

COMMIT;

-- ============================================================
-- LangGraph PostgreSQL Checkpointer
-- ============================================================
-- checkpoint_migrations / checkpoints / checkpoint_blobs / checkpoint_writes는
-- 수동 SQL로 고정하지 않습니다. AgentStudio가 Supabase 스키마 준비 직후 현재 설치된
-- langgraph-checkpoint-postgres의 AsyncPostgresSaver.setup()을 실행하여 공식 migration을
-- 적용하고, 네 필수 테이블과 migration 기록을 다시 검증합니다.
--
-- 따라서 이 파일은 여러 번 실행해도 기존 데이터를 DROP/TRUNCATE/DELETE하지 않으며,
-- LangGraph 패키지 버전이 바뀌어도 수동 테이블 정의와 충돌하지 않습니다.
-- ============================================================
