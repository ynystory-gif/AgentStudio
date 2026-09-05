# v5.504 React Type Declaration Collision Fix Validation

## Root cause

v5.503 included `frontend/src/__temp_typecheck_shim__.d.ts`, a local offline-validation shim. On a real machine where React 19, `@types/react`, xterm, and `@xterm/addon-fit` are installed, that shim merged with/overrode package declarations. This caused the repeated `JSX.Element` -> `ReactNode` failures and the `FitAddon` -> `ITerminalAddon` failure shown by the real Windows build.

## Fix

1. Removed the temporary shim from source and distribution.
2. Added a contract that fails if local declarations override `react`, `@xterm/xterm`, or `@xterm/addon-fit`.
3. Narrowed settings renderer callback parameters from `LegacyValue` to `string` to match child component contracts.
4. Re-ran frontend/core/Codex/DB source-of-truth regression contracts.

## Validation result

PASS for v5.501 migration contract, v5.502 env DB contract, v5.504 core regression, v5.504 declaration-collision guard, frontend contracts, Codex protocol, and Python compilation.
