import React, { useMemo, useState } from 'react'
import { DatabaseDiagramViewer } from './DatabaseDiagramViewer'

export interface DbErdDatabase {
  id?: string
  engine?: string
  label?: string
  kind?: 'relational' | 'vector' | 'key-value' | 'document' | string
  source?: string
  table_count?: number
  relationship_count?: number
  key_count?: number
  collection_count?: number
  message?: string
  policy?: string
  diagram?: Record<string, unknown>
  keys?: Array<Record<string, unknown>>
  collections?: Array<Record<string, unknown>>
}

export interface DbErdReport {
  ok?: boolean
  scope?: string
  generated_at?: string
  project_root?: string
  databases?: DbErdDatabase[]
  summary?: {
    database_count?: number
    table_count?: number
    relationship_count?: number
    redis_key_count?: number
    collection_count?: number
  }
  notes?: string[]
}

function safeText(value: unknown, fallback = '-') {
  const text = String(value ?? '').trim()
  return text || fallback
}

function databaseTone(kind: string) {
  if (kind === 'vector') return 'vector'
  if (kind === 'key-value') return 'redis'
  if (kind === 'document') return 'document'
  return 'sql'
}

function RedisLogicalModel({ database }: { database: DbErdDatabase }) {
  const keys = Array.isArray(database.keys) ? database.keys : []
  return <div className="db-erd-logical-grid redis">
    {keys.length ? keys.map((item, index) => <div className="db-erd-logical-card" key={`${safeText(item.key, 'key')}:${index}`}>
      <div className="db-erd-logical-icon">R</div>
      <div className="db-erd-logical-copy">
        <strong>{safeText(item.key, 'redis:key')}</strong>
        <span>{safeText(item.purpose, 'Redis Key')}</span>
        <small>TTL · {safeText(item.ttl, '미지정')} · {safeText(item.data_type, 'key')}</small>
      </div>
    </div>) : <div className="db-erd-empty-inline">Redis 사용은 감지했지만 정적 Key Pattern을 아직 찾지 못했습니다.</div>}
  </div>
}

function DocumentLogicalModel({ database }: { database: DbErdDatabase }) {
  const collections = Array.isArray(database.collections) ? database.collections : []
  return <div className="db-erd-logical-grid document">
    {collections.length ? collections.map((item, index) => <div className="db-erd-logical-card" key={`${safeText(item.name, 'collection')}:${index}`}>
      <div className="db-erd-logical-icon">C</div>
      <div className="db-erd-logical-copy">
        <strong>{safeText(item.name, 'collection')}</strong>
        <span>{safeText(item.purpose, 'Document Collection')}</span>
      </div>
    </div>) : <div className="db-erd-empty-inline">Document DB 사용은 감지했지만 Collection 구조를 아직 찾지 못했습니다.</div>}
  </div>
}

export interface DatabaseErdPanelProps {
  report: DbErdReport | null
  loading?: boolean
  error?: string
  onRefresh?: () => void
}

export function DatabaseErdPanel({ report, loading, error, onRefresh }: DatabaseErdPanelProps) {
  const databases = Array.isArray(report?.databases) ? report!.databases! : []
  const [selectedId, setSelectedId] = useState('')
  const active = useMemo(() => {
    if (!databases.length) return null
    return databases.find(item => String(item.id || item.engine || '') === selectedId) || databases[0]
  }, [databases, selectedId])

  return <div className="db-erd-panel-shell">
    <div className="db-erd-panel-toolbar">
      <div>
        <strong>DB별 ERD / Data Model</strong>
        <span>관계형 DB · pgvector · Redis · Document DB를 각각 분리하여 표시합니다.</span>
      </div>
      <button type="button" onClick={onRefresh} disabled={loading}>{loading ? '분석 중...' : '↻ 다시 분석'}</button>
    </div>

    {error && <div className="db-erd-panel-error">{error}</div>}
    {!error && loading && !report && <div className="db-erd-panel-empty">프로젝트 DB Schema와 Key Model을 분석하고 있습니다...</div>}
    {!loading && !databases.length && <div className="db-erd-panel-empty">
      <strong>표시할 DB ERD가 없습니다.</strong>
      <span>DB 설계, CREATE TABLE, Redis Key, pgvector VECTOR 컬럼 또는 Firestore Collection이 생성되면 자동으로 표시됩니다.</span>
    </div>}

    {databases.length > 0 && <>
      <div className="db-erd-database-tabs">
        {databases.map(item => {
          const id = String(item.id || item.engine || item.label || '')
          const kind = String(item.kind || 'relational')
          const count = kind === 'key-value'
            ? Number(item.key_count || 0)
            : kind === 'document'
              ? Number(item.collection_count || 0)
              : Number(item.table_count || 0)
          return <button
            type="button"
            key={id}
            className={`${active === item ? 'active' : ''} ${databaseTone(kind)}`}
            onClick={() => setSelectedId(id)}
          >
            <span className="db-erd-tab-icon">{kind === 'vector' ? 'V' : kind === 'key-value' ? 'R' : kind === 'document' ? 'C' : 'DB'}</span>
            <span><strong>{safeText(item.label || item.engine, 'Database')}</strong><small>{count}{kind === 'key-value' ? ' keys' : kind === 'document' ? ' collections' : ' tables'}</small></span>
          </button>
        })}
      </div>

      {active && <section className={`db-erd-database-section ${databaseTone(String(active.kind || 'relational'))}`}>
        <div className="db-erd-database-head">
          <div>
            <span className="db-erd-engine-mark">{String(active.kind || 'relational') === 'vector' ? 'VECTOR' : String(active.kind || 'relational') === 'key-value' ? 'REDIS' : String(active.kind || 'relational') === 'document' ? 'DOC' : 'SQL'}</span>
            <div><strong>{safeText(active.label || active.engine, 'Database')}</strong><small>{safeText(active.source, 'PROJECT INFERENCE')}</small></div>
          </div>
          <div className="db-erd-head-metrics">
            {['relational', 'vector'].includes(String(active.kind || 'relational')) && <>
              <span>Tables <b>{Number(active.table_count || 0)}</b></span>
              <span>Relations <b>{Number(active.relationship_count || 0)}</b></span>
            </>}
            {String(active.kind) === 'key-value' && <span>Keys <b>{Number(active.key_count || 0)}</b></span>}
            {String(active.kind) === 'document' && <span>Collections <b>{Number(active.collection_count || 0)}</b></span>}
          </div>
        </div>
        {active.message && <div className="db-erd-database-message">{active.message}</div>}
        {['relational', 'vector'].includes(String(active.kind || 'relational'))
          ? <div className="db-erd-diagram-host">
              <DatabaseDiagramViewer value={JSON.stringify(active.diagram || { version: 1, kind: 'database_schema_diagram', root_table: '', tables: [], relationships: [] })} />
            </div>
          : String(active.kind) === 'key-value'
            ? <RedisLogicalModel database={active} />
            : <DocumentLogicalModel database={active} />}
      </section>}
    </>}

    {(report?.notes || []).length > 0 && <div className="db-erd-notes">{(report?.notes || []).map((note, index) => <span key={index}>{note}</span>)}</div>}
  </div>
}
