# v5.306 Frontend TypeScript Terminal / WebSocket Migration

## Scope

This phase migrates the terminal presentation and terminal WebSocket contract boundary out of `App.jsx` while preserving the existing PowerShell/xterm session lifecycle and command execution behavior.

## Migrated

- Multi-terminal tabs, rename/close/restart controls and active terminal toolbar
- Terminal error detail panel
- Project terminal / `.venv` status strip
- xterm container presentation and completion popup
- Typed terminal session, process, error and completion contracts
- Typed WebSocket server message parsing and client message serialization
- Unicode/Hangul/CJK terminal cell-width and previous/next character helpers

## Preserved in App.jsx

- xterm instance lifecycle and FitAddon orchestration
- Backend PowerShell session creation/reconnect
- keyboard input/history/selection handling
- Ctrl+C interrupt semantics and prompt-based busy reset
- terminal completion API orchestration
- current System/Runtime and MCP/Agent logic

## Regression boundary

The terminal component receives callbacks for every lifecycle operation. It does not own or recreate the persistent PowerShell session, xterm instance or WebSocket connection.

## Next phase

Migrate System / Settings / Runtime UI to TypeScript while keeping the database-provider switch and Supabase runtime safety checks intact.
