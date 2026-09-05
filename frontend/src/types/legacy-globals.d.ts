/**
 * Temporary compatibility types for the final JavaScript -> TypeScript migration.
 * Dynamic values are isolated here instead of spreading `any` throughout components.
 * New/edited feature contracts should use concrete interfaces in common.ts.
 */
type LegacyValue = any
type LegacyRecord = Record<string, LegacyValue>

interface Window { showSaveFilePicker?: (options?)=>Promise<LegacyValue> }
