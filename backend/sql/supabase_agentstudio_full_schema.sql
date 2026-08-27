-- ============================================================
-- THEANOVA AgentStudio - Supabase PostgreSQL Full Schema
-- v5.389 FrontendThemeImportRecovery
--
-- Target layout:
--   theanova_agentstudio : AgentStudio ORM + LangGraph Checkpointer
--   extensions           : pgvector(vector)
--   public               : AgentStudio가 소유하지 않는 일반 사용자 데이터
--
-- 이 SQL은 AgentStudio ORM 스키마를 멱등 방식으로 준비합니다.
-- LangGraph Checkpointer 테이블은 AgentStudio Backend가 같은
-- theanova_agentstudio search_path에서 AsyncPostgresSaver.setup()을 실행해 생성합니다.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS theanova_agentstudio;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

DO $$
DECLARE vector_schema TEXT;
BEGIN
  SELECT n.nspname INTO vector_schema
  FROM pg_extension e
  JOIN pg_namespace n ON n.oid = e.extnamespace
  WHERE e.extname = 'vector';

  IF vector_schema IS DISTINCT FROM 'extensions' THEN
    RAISE EXCEPTION 'pgvector(vector)는 extensions 스키마에 있어야 합니다. 현재 스키마=%', vector_schema;
  END IF;
END $$;

SET LOCAL search_path TO theanova_agentstudio, extensions, public;

-- ------------------------------------------------------------
-- AgentStudio core tables
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS theanova_agentstudio.projects (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL DEFAULT '',
    name VARCHAR(200) NOT NULL,
    root_path VARCHAR(1000) NOT NULL,
    cache_path VARCHAR(1000) NOT NULL DEFAULT '',
    temp_path VARCHAR(1000) NOT NULL DEFAULT '',
    output_path VARCHAR(1000) NOT NULL DEFAULT '',
    venv_path VARCHAR(1000) NOT NULL DEFAULT '',
    models_path VARCHAR(1000) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP NULL,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_projects_pc_name_root_path UNIQUE (pc_name, root_path)
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.conversation_messages (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES theanova_agentstudio.projects(id),
    thread_id VARCHAR(100) NOT NULL DEFAULT 'default',
    role VARCHAR(30) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.requirements (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES theanova_agentstudio.projects(id),
    key VARCHAR(150) NOT NULL,
    value TEXT NOT NULL,
    confirmed BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.mcp_servers (
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

CREATE TABLE IF NOT EXISTS theanova_agentstudio.tool_registry (
    id SERIAL PRIMARY KEY,
    mcp_server_id INTEGER NULL REFERENCES theanova_agentstudio.mcp_servers(id),
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

CREATE TABLE IF NOT EXISTS theanova_agentstudio.approval_requests (
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

CREATE TABLE IF NOT EXISTS theanova_agentstudio.memory_records (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES theanova_agentstudio.projects(id),
    memory_type VARCHAR(30) NOT NULL,
    key VARCHAR(250) NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSON NOT NULL DEFAULT '{}'::json,
    embedding extensions.vector NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.project_file_index (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES theanova_agentstudio.projects(id),
    path VARCHAR(1200) NOT NULL,
    language VARCHAR(50) NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    symbols JSON NOT NULL DEFAULT '[]'::json,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_project_file UNIQUE (project_id, path)
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.evaluation_records (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES theanova_agentstudio.projects(id),
    metric VARCHAR(100) NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    details JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.usage_records (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NULL REFERENCES theanova_agentstudio.projects(id),
    provider VARCHAR(100) NOT NULL,
    model VARCHAR(150) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.jobs (
    id VARCHAR(64) PRIMARY KEY,
    kind VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    result JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.agentstudio_machines (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL UNIQUE,
    host_name VARCHAR(255) NOT NULL DEFAULT '',
    os_name VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.app_settings (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL DEFAULT '',
    key VARCHAR(150) NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_app_settings_pc_name_key UNIQUE (pc_name, key)
);

CREATE INDEX IF NOT EXISTS ix_app_settings_key
    ON theanova_agentstudio.app_settings(key);
CREATE INDEX IF NOT EXISTS ix_app_settings_pc_name
    ON theanova_agentstudio.app_settings(pc_name);
CREATE INDEX IF NOT EXISTS ix_agentstudio_machines_pc_name
    ON theanova_agentstudio.agentstudio_machines(pc_name);
CREATE INDEX IF NOT EXISTS ix_projects_pc_name
    ON theanova_agentstudio.projects(pc_name);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.project_analyses (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES theanova_agentstudio.projects(id),
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
-- Compatibility upgrades for existing AgentStudio schema
-- ------------------------------------------------------------

ALTER TABLE IF EXISTS theanova_agentstudio.projects
    ADD COLUMN IF NOT EXISTS pc_name VARCHAR(255) NOT NULL DEFAULT '';

-- v5.308: root_path used to be globally UNIQUE. Shared Supabase must allow the
-- same local path on different PCs, so uniqueness is now (pc_name, root_path).
DO $$
DECLARE r RECORD;
BEGIN
  IF to_regclass('theanova_agentstudio.projects') IS NOT NULL THEN
    FOR r IN
      SELECT c.conname
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
      JOIN pg_namespace n ON n.oid = t.relnamespace
      WHERE n.nspname = 'theanova_agentstudio'
        AND t.relname = 'projects'
        AND c.contype = 'u'
        AND array_length(c.conkey, 1) = 1
        AND EXISTS (
          SELECT 1
          FROM unnest(c.conkey) AS k(attnum)
          JOIN pg_attribute a
            ON a.attrelid = c.conrelid AND a.attnum = k.attnum
          WHERE a.attname = 'root_path'
        )
    LOOP
      EXECUTE format(
        'ALTER TABLE %I.%I DROP CONSTRAINT %I',
        'theanova_agentstudio', 'projects', r.conname
      );
    END LOOP;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_projects_pc_name
    ON theanova_agentstudio.projects(pc_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_pc_name_root_path
    ON theanova_agentstudio.projects(pc_name, root_path);

ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS cache_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS temp_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS output_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS venv_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS models_path VARCHAR(1000) NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMP NULL;
ALTER TABLE IF EXISTS theanova_agentstudio.projects ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE IF EXISTS theanova_agentstudio.app_settings
    ADD COLUMN IF NOT EXISTS pc_name VARCHAR(255) NOT NULL DEFAULT '';

DO $$
DECLARE r RECORD;
BEGIN
  IF to_regclass('theanova_agentstudio.app_settings') IS NOT NULL THEN
    FOR r IN
      SELECT c.conname
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
      JOIN pg_namespace n ON n.oid = t.relnamespace
      WHERE n.nspname = 'theanova_agentstudio'
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
      EXECUTE format(
        'ALTER TABLE %I.%I DROP CONSTRAINT %I',
        'theanova_agentstudio', 'app_settings', r.conname
      );
    END LOOP;
  END IF;
END $$;

DROP INDEX IF EXISTS theanova_agentstudio.ix_app_settings_key;
CREATE INDEX IF NOT EXISTS ix_app_settings_key ON theanova_agentstudio.app_settings(key);
CREATE INDEX IF NOT EXISTS ix_app_settings_pc_name ON theanova_agentstudio.app_settings(pc_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_app_settings_pc_name_key ON theanova_agentstudio.app_settings(pc_name, key);
CREATE INDEX IF NOT EXISTS ix_agentstudio_machines_pc_name ON theanova_agentstudio.agentstudio_machines(pc_name);

-- ------------------------------------------------------------
-- v5.385+ Agent Design Project / v5.386+ Imported Theme tables
-- Fresh Supabase installs include them here; v5.389 runtime also self-heals
-- existing schemas with SQLAlchemy create_all(checkfirst).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS theanova_agentstudio.agent_design_projects (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL DEFAULT '',
    name VARCHAR(300) NOT NULL DEFAULT '',
    project_root VARCHAR(1200) NOT NULL DEFAULT '',
    status VARCHAR(50) NOT NULL DEFAULT 'INTERVIEWING',
    progress INTEGER NOT NULL DEFAULT 0,
    current_stage VARCHAR(100) NOT NULL DEFAULT 'REQUIREMENTS',
    current_question TEXT NOT NULL DEFAULT '',
    langgraph_thread_id VARCHAR(160) NOT NULL DEFAULT '',
    snapshot JSON NOT NULL DEFAULT '{}'::json,
    feature_registry JSON NOT NULL DEFAULT '[]'::json,
    version_no INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS ix_agent_design_projects_pc_name ON theanova_agentstudio.agent_design_projects(pc_name);
CREATE INDEX IF NOT EXISTS ix_agent_design_projects_status ON theanova_agentstudio.agent_design_projects(status);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.agent_design_project_versions (
    id SERIAL PRIMARY KEY,
    design_project_id INTEGER NOT NULL REFERENCES theanova_agentstudio.agent_design_projects(id),
    version_no INTEGER NOT NULL DEFAULT 1,
    label VARCHAR(300) NOT NULL DEFAULT '',
    snapshot JSON NOT NULL DEFAULT '{}'::json,
    feature_registry JSON NOT NULL DEFAULT '[]'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_agent_design_project_versions_design_project_id ON theanova_agentstudio.agent_design_project_versions(design_project_id);

CREATE TABLE IF NOT EXISTS theanova_agentstudio.ui_themes (
    id SERIAL PRIMARY KEY,
    pc_name VARCHAR(255) NOT NULL DEFAULT '',
    name VARCHAR(300) NOT NULL DEFAULT '',
    theme_type VARCHAR(40) NOT NULL DEFAULT 'IMPORTED',
    source_type VARCHAR(40) NOT NULL DEFAULT 'CUSTOM',
    source_url VARCHAR(2000) NOT NULL DEFAULT '',
    source_label VARCHAR(1000) NOT NULL DEFAULT '',
    scope VARCHAR(40) NOT NULL DEFAULT 'GLOBAL',
    tokens JSON NOT NULL DEFAULT '{}'::json,
    component_rules JSON NOT NULL DEFAULT '{}'::json,
    layout_rules JSON NOT NULL DEFAULT '{}'::json,
    preview_colors JSON NOT NULL DEFAULT '[]'::json,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ui_themes_pc_name ON theanova_agentstudio.ui_themes(pc_name);
CREATE INDEX IF NOT EXISTS ix_ui_themes_theme_type ON theanova_agentstudio.ui_themes(theme_type);
CREATE INDEX IF NOT EXISTS ix_ui_themes_scope ON theanova_agentstudio.ui_themes(scope);

COMMIT;

-- ============================================================
-- LangGraph PostgreSQL Checkpointer
-- ============================================================
-- checkpoint_migrations / checkpoints / checkpoint_blobs / checkpoint_writes는
-- 수동 정의하지 않습니다. v5.297 Backend가 SUPABASE_DB_SCHEMA=theanova_agentstudio를
-- PostgreSQL search_path에 적용한 뒤 현재 설치된 langgraph-checkpoint-postgres의
-- AsyncPostgresSaver.setup()을 실행합니다.
--
-- Python LangGraph Checkpointer는 현재 explicit schema 옵션 대신 unqualified SQL을
-- 사용하므로 AgentStudio는 저장 URL을 변경하지 않고 연결 시 search_path를 주입합니다.
-- Supabase에서는 direct/session pooler 연결을 권장하며 transaction pooler(일반적으로 6543)는
-- session search_path 보장이 약할 수 있으므로 LangGraph runtime 연결에는 권장하지 않습니다.
-- ============================================================
