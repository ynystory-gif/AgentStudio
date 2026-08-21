# v5.304 Frontend TypeScript Common / Report / Architecture / LLM Migration

## Scope

This phase removes presentation-only UI blocks from the legacy `App.jsx` without changing workspace orchestration or backend behavior.

## Extracted TypeScript modules

- `frontend/src/components/common/CommonUi.tsx`
- `frontend/src/components/reports/ReportComponents.tsx`
- `frontend/src/components/architecture/ArchitecturePanels.tsx`
- `frontend/src/components/llm/LlmCatalogPanel.tsx`
- `frontend/src/types/report.ts`

## Regression boundary

DB Browser, Redis, Firestore, Supabase, Terminal, System/Settings, MCP and the main IDE state machine remain in `App.jsx`. Existing CSS class names and rendered DOM structure are preserved for the extracted panels.

## Validation

The extracted TS/TSX modules are checked with strict TypeScript settings and `noUncheckedIndexedAccess`. The legacy `App.jsx` API import contract check remains part of `npm run typecheck` and `npm run build`.
