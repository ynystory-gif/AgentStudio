# v5.303 RuntimeInfo Import Regression Fix

- Restores `runtimeInfo` import from `src/api.ts` in `App.jsx`.
- Fixes blank System and IDE pages caused by `ReferenceError: runtimeInfo is not defined`.
- Adds `frontend/validate_frontend_contracts.cjs` so `npm run typecheck` and `npm run build` fail before bundling if critical API functions are used without the matching `./api` import.
- Keeps the v5.301 NotebookEditor TypeScript migration and the v5.302 SYSTEM_ADMIN UTF-8 BOM self-heal fix.
