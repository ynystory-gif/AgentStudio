# v5.305 Frontend TypeScript Database Browser Migration

## Scope

This phase migrates the SQL Workspace browser rendering layer from `App.jsx` to typed React components while preserving the existing database connection/runtime orchestration.

## Migrated

- SQL Object Explorer for PostgreSQL/Supabase/MSSQL/Oracle/SQLite
- Firestore Collection / Document / Field browser
- Redis key tree, detail browser and live TTL countdown
- Firestore / Redis scratch-code context menus
- SQL table DDL/DML context menu
- PostgreSQL session/lock context menu and admin prompt
- Shared database response/profile/browser types
- Redis/Firestore formatting and tree helpers

## Compatibility boundary

Connection profile persistence, DPAPI credential storage, backend API calls, connection lifecycle and project workspace state remain in `App.jsx` for this phase. Terminal, System/Runtime and MCP/Agent UI are untouched.

## Next phase

The next TypeScript phase should migrate the terminal UI/WebSocket state boundary after runtime verification of this DB browser extraction.
