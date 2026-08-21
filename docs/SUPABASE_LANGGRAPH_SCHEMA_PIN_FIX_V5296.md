# v5.296 Supabase LangGraph Schema Pin Fix

## Problem

v5.295 correctly isolated AgentStudio SQLAlchemy tables in `theanova_agentstudio`, but
LangGraph Python's PostgreSQL checkpointer still uses unqualified table names. v5.295
passed `options=-csearch_path=...` in the PostgreSQL URL. On Supabase's PgBouncer session
endpoint this startup option can be accepted without LangGraph's `setup()` ultimately
creating/checking the tables in the intended schema.

Observed symptom:

- AgentStudio tables: valid in `theanova_agentstudio`
- LangGraph migration count: `0`
- Missing: `checkpoint_migrations`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`

## Fix

v5.296 opens the psycopg connection itself with the settings required by LangGraph:

- `autocommit=True`
- `prepare_threshold=0`
- `row_factory=dict_row`

Then, on that exact persistent connection, it executes:

```sql
SET search_path TO theanova_agentstudio, extensions, public;
```

It verifies `current_schema()` before constructing `AsyncPostgresSaver(conn)`. Both the
one-time `setup()` migration and the long-lived runtime checkpointer use this same
schema-pinned connection path.

## Safety

- Existing AgentStudio tables are not recreated or deleted.
- Existing `public.checkpoint_*` tables, if any were accidentally created by v5.295, are
  detected and reported but are not deleted automatically.
- Runtime provider switches to Supabase only after AgentStudio schema + LangGraph tables
  both validate successfully.
