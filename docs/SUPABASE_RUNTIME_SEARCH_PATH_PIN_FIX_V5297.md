# v5.297 Supabase Runtime Search Path Pin Fix

## Symptom

Supabase schema provisioning and LangGraph migrations succeeded, but clicking **Supabase PostgreSQL 사용 적용** failed with:

```text
PostgreSQL search_path 적용 실패: 기대=theanova_agentstudio, 실제=public
```

LangGraph was already fixed in v5.296 because it pins `search_path` on the exact psycopg connection. SQLAlchemy Runtime ORM still depended on the PostgreSQL startup `options=-csearch_path=...` setting. On Supabase Session Pooler this could connect successfully while `current_schema()` remained `public`.

## Fix

The AgentStudio SQLAlchemy engine now registers a pool `checkout` hook. Every checked-out DBAPI connection executes:

```sql
SET search_path TO theanova_agentstudio, extensions, public;
```

The statement is executed with DBAPI autocommit temporarily enabled so a later rollback cannot undo the session-level setting. `schema_translate_map` remains active, so ORM tables are still explicitly mapped into `theanova_agentstudio`.

This means both Runtime ORM and LangGraph now pin the schema on the exact connection they actually use.

## Safety

- Existing `theanova_agentstudio` tables are not dropped.
- Existing LangGraph migrations are reused; migration 10 does not need to be recreated.
- Failure still rolls Runtime DB and LangGraph back to local PostgreSQL.
- Supabase transaction pooler port 6543 remains rejected for this persistent Runtime configuration.
