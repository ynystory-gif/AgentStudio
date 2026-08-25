export type DatabaseProviderType =
  | 'postgresql'
  | 'supabase'
  | 'mssql'
  | 'oracle'
  | 'sqlite3'
  | 'redis'
  | 'firestore'
  | string

export interface DatabaseProfile {
  connection_id?: string
  name?: string
  db_type?: DatabaseProviderType
  host?: string
  port?: number | string
  database?: string
  schema_name?: string
  username?: string
  project_id?: string
  service_account_json?: string
  [key: string]: unknown
}

export interface DatabaseConnectionStatus {
  connected?: boolean
  profile?: DatabaseProfile
  error?: string
  [key: string]: unknown
}

export interface FirestoreCollectionItem {
  id?: string
  path?: string
}

export interface FirestoreCollectionsResult {
  project_id?: string
  database?: string
  collections?: FirestoreCollectionItem[]
  returned_count?: number
  limit?: number
  refreshed_at?: string
}

export interface FirestoreDocumentListItem {
  id?: string
  path?: string
  field_count?: number
  field_names?: string[]
  create_time?: string | null
  update_time?: string | null
}

export interface FirestoreDocumentsResult {
  collection?: string
  documents?: FirestoreDocumentListItem[]
  returned_count?: number
  limit?: number
  truncated?: boolean
  refreshed_at?: string
}

export interface FirestoreField {
  name?: string
  type?: string
  value?: unknown
}

export interface FirestoreSubcollection {
  id?: string
  path?: string
}

export interface FirestoreDocumentDetail {
  id?: string
  path?: string
  field_count?: number
  fields?: FirestoreField[]
  subcollections?: FirestoreSubcollection[]
  create_time?: string | null
  update_time?: string | null
  read_time?: string | null
  refreshed_at?: string
}

export interface FirestoreContextMenuState {
  x: number
  y: number
  nodeKind: 'collection' | 'document'
  path: string
  label?: string
}

export type RedisKeyType = 'string' | 'hash' | 'list' | 'set' | 'zset' | 'stream' | 'none' | 'unknown' | string

export interface RedisKeySummary {
  key?: string
  label?: string
  type?: RedisKeyType
  ttl?: number
  length?: number
  size_bytes?: number
}

export interface RedisBrowserResult {
  database?: string
  pattern?: string
  keys?: RedisKeySummary[]
  returned_count?: number
  total_keys?: number
  scan_complete?: boolean
  limit?: number
  refreshed_at?: string
  __ttl_observed_at_ms?: number
}

export interface RedisValueRow {
  field?: string
  value?: unknown
  index?: number
  member?: string
  score?: number
  id?: string
  fields?: Record<string, string>
}

export interface RedisKeyDetail extends RedisKeySummary {
  database?: string
  value?: unknown
  rows?: RedisValueRow[]
  truncated?: boolean
  max_items?: number
  refreshed_at?: string
  __ttl_observed_at_ms?: number
}

export interface RedisTreeNode {
  name: string
  path: string
  children: RedisTreeNode[]
  items: RedisKeySummary[]
}

export interface RedisContextMenuState {
  x: number
  y: number
  nodeKind: 'group' | 'key'
  prefix?: string
  key?: string
  keyType?: string
  label?: string
}

export interface SqlObjectColumn {
  name?: string
  data_type?: string
  nullable?: boolean
}

export interface SqlDatabaseObjectItem {
  name?: string
  schema?: string
  qualified_name?: string
  arguments?: string
  table?: string
  columns?: SqlObjectColumn[]
  [key: string]: unknown
}

export type SqlObjectCategory =
  | 'tables'
  | 'views'
  | 'procedures'
  | 'functions'
  | 'sequences'
  | 'triggers'
  | 'indexes'
  | 'packages'

export interface SqlObjectSchema {
  name?: string
  tables?: SqlDatabaseObjectItem[]
  views?: SqlDatabaseObjectItem[]
  procedures?: SqlDatabaseObjectItem[]
  functions?: SqlDatabaseObjectItem[]
  sequences?: SqlDatabaseObjectItem[]
  triggers?: SqlDatabaseObjectItem[]
  indexes?: SqlDatabaseObjectItem[]
  packages?: SqlDatabaseObjectItem[]
}

export interface SqlDatabaseObjectsResult {
  db_type?: string
  database?: string
  schemas?: SqlObjectSchema[]
  counts?: Partial<Record<SqlObjectCategory, number>>
  refreshed_at?: string
}

export interface SqlObjectContextMenuState {
  x: number
  y: number
  schemaName: string
  category: SqlObjectCategory
  item: SqlDatabaseObjectItem
}


export interface SqlSchemaContextMenuState {
  x: number
  y: number
  schemaName: string
}

export interface SqlDatabaseContextMenuState {
  x: number
  y: number
}

export interface SqlAdminPromptState {
  action: string
  title: string
  label: string
  placeholder: string
  value: string
  danger?: boolean
}

export interface DatabaseDiagramColumn {
  name: string
  data_type?: string
  nullable?: boolean
  primary_key?: boolean
  foreign_key?: boolean
}

export interface DatabaseDiagramTable {
  id: string
  schema: string
  name: string
  columns: DatabaseDiagramColumn[]
}

export interface DatabaseDiagramRelationship {
  name?: string
  from_table: string
  from_columns: string[]
  to_table: string
  to_columns: string[]
}

export interface DatabaseDiagramDocument {
  version: number
  kind: 'database_table_diagram' | 'database_schema_diagram'
  db_type?: string
  database?: string
  root_table: string
  schema_name?: string
  generated_at?: string
  tables: DatabaseDiagramTable[]
  relationships: DatabaseDiagramRelationship[]
}

export type SqlResultCell = unknown

export interface SqlExecutionResultSet {
  result_index: number
  statement_index: number
  sql?: string
  columns: string[]
  rows: SqlResultCell[][]
  row_count: number
  truncated?: boolean
}

export interface SqlStatementExecutionResult {
  index?: number
  sql?: string
  columns?: string[]
  row_count?: number
  affected_rows?: number
  truncated?: boolean
}

export interface SqlExecutionResult {
  ok?: boolean
  columns?: string[]
  rows?: SqlResultCell[][]
  row_count?: number
  affected_rows?: number
  truncated?: boolean
  elapsed_ms?: number
  message?: string
  db_type?: string
  statement_count?: number
  statement_results?: SqlStatementExecutionResult[]
  result_set_count?: number
  result_sets?: SqlExecutionResultSet[]
}

export interface SqlExecutionMessage {
  type?: 'success' | 'error' | 'warning' | 'info' | string
  text: string
  time: string
}
