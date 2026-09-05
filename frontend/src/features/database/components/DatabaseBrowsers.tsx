import React, { useSyncExternalStore } from 'react'
import type {
  DatabaseConnectionStatus,
  DatabaseProfile,
  FirestoreCollectionsResult,
  FirestoreContextMenuState,
  FirestoreDocumentDetail,
  FirestoreDocumentsResult,
  RedisBrowserResult,
  RedisContextMenuState,
  RedisKeyDetail,
  RedisTreeNode,
  SqlAdminPromptState,
  SqlDatabaseContextMenuState,
  SqlDatabaseObjectItem,
  SqlDatabaseObjectsResult,
  SqlObjectCategory,
  SqlObjectContextMenuState,
  SqlObjectSchema,
  SqlSchemaContextMenuState,
} from '../../../types/database'
import {
  buildRedisKeyTree,
  countRedisTreeKeys,
  firestoreValueText,
  formatRedisBytes,
  redisLiveTtl,
  redisTtlLabel,
} from '../../../utils/database'

let redisTtlClockNow = Date.now()
let redisTtlClockTimer: number | null = null
const redisTtlClockListeners = new Set<() => void>()

function subscribeRedisTtlClock(listener: () => void): () => void {
  redisTtlClockListeners.add(listener)
  if (redisTtlClockTimer === null && typeof window !== 'undefined') {
    redisTtlClockNow = Date.now()
    redisTtlClockTimer = window.setInterval(() => {
      redisTtlClockNow = Date.now()
      redisTtlClockListeners.forEach((current: LegacyValue) => current())
    }, 1000)
  }
  return () => {
    redisTtlClockListeners.delete(listener)
    if (redisTtlClockListeners.size === 0 && redisTtlClockTimer !== null && typeof window !== 'undefined') {
      window.clearInterval(redisTtlClockTimer)
      redisTtlClockTimer = null
    }
  }
}

const getRedisTtlClockSnapshot = () => redisTtlClockNow

function RedisActiveTtlCountdown({ ttl, observedAt }: { ttl: unknown; observedAt: unknown }) {
  const now = useSyncExternalStore(
    subscribeRedisTtlClock,
    getRedisTtlClockSnapshot,
    getRedisTtlClockSnapshot,
  )
  return redisTtlLabel(redisLiveTtl(ttl, observedAt, now))
}

export function RedisTtlCountdown({ ttl, observedAt }: { ttl: unknown; observedAt: unknown }) {
  const value = Number(ttl)
  if (!Number.isFinite(value) || value <= 0) return redisTtlLabel(value)
  return <RedisActiveTtlCountdown ttl={value} observedAt={observedAt} />
}

interface FirestoreNodePayload {
  kind: 'collection' | 'document'
  path: string
  label?: string
}

export interface FirestoreBrowserPanelProps {
  connected?: boolean
  profile: DatabaseProfile
  browser: FirestoreCollectionsResult | null
  browserBusy: boolean
  browserError: string
  collectionFilter: string
  documentFilter: string
  selectedCollection: string
  documents: FirestoreDocumentsResult | null
  documentsBusy: boolean
  selectedDocument: string
  documentDetail: FirestoreDocumentDetail | null
  documentDetailBusy: boolean
  setCollectionFilter: (value: string) => void
  setDocumentFilter: (value: string) => void
  loadCollections: (options?: { quiet?: boolean; preserveSelection?: boolean }) => unknown
  loadDocuments: (path: string, options?: { quiet?: boolean; preserveSelection?: boolean }) => unknown
  loadDocumentDetail: (path: string, options?: { quiet?: boolean }) => unknown
  openContextMenu: (event: React.MouseEvent<HTMLElement>, node: FirestoreNodePayload) => unknown
}

export function FirestoreBrowserPanel({
  connected,
  profile,
  browser,
  browserBusy,
  browserError,
  collectionFilter,
  documentFilter,
  selectedCollection,
  documents,
  documentsBusy,
  selectedDocument,
  documentDetail,
  documentDetailBusy,
  setCollectionFilter,
  setDocumentFilter,
  loadCollections,
  loadDocuments,
  loadDocumentDetail,
  openContextMenu,
}: FirestoreBrowserPanelProps) {
  if (!connected) {
    return <div className="sql-object-empty">Project ID와 인증 정보를 입력한 뒤 연결 / 테스트를 실행하세요.</div>
  }

  const collections = Array.isArray(browser?.collections) ? browser.collections : []
  const collectionNeedle = String(collectionFilter || '').trim().toLowerCase()
  const visibleCollections = collectionNeedle
    ? collections.filter((item: LegacyValue) => String(item?.id || '').toLowerCase().includes(collectionNeedle))
    : collections
  const documentRows = Array.isArray(documents?.documents) ? documents.documents : []
  const documentNeedle = String(documentFilter || '').trim().toLowerCase()
  const visibleDocuments = documentNeedle
    ? documentRows.filter((item: LegacyValue) => String(item?.id || '').toLowerCase().includes(documentNeedle))
    : documentRows
  const detail = documentDetail

  return <div className="firestore-browser-shell">
    <div className="firestore-browser-toolbar">
      <div className="firestore-filter-box">
        <span>Collection</span>
        <input value={collectionFilter} onChange={(e: LegacyValue) => setCollectionFilter(e.target.value)} placeholder="컬렉션 검색" />
      </div>
      <div className="firestore-filter-box">
        <span>Document</span>
        <input value={documentFilter} onChange={(e: LegacyValue) => setDocumentFilter(e.target.value)} placeholder="문서 ID 검색" />
      </div>
    </div>
    <div className="firestore-browser-summary">
      <strong>Collections: {visibleCollections.length}</strong>
      <span>{browser?.project_id || profile.project_id || '-'} · {browser?.database || profile.database || '(default)'}</span>
      <button type="button" onClick={() => loadCollections({ preserveSelection: true })} disabled={browserBusy}>{browserBusy ? '조회 중...' : '↻ 새로고침'}</button>
    </div>
    {browserError && <div className="sql-object-error">{browserError}</div>}
    <div className="firestore-browser-main">
      <div className="firestore-browser-top">
        <div className="firestore-collection-pane">
          <div className="firestore-pane-head"><strong>Collections</strong><small>{visibleCollections.length}</small></div>
          <div className="firestore-pane-scroll">
            {browserBusy && !browser
              ? <div className="sql-object-empty">Collection을 읽고 있습니다...</div>
              : visibleCollections.length
                ? visibleCollections.map((item: LegacyValue) => {
                    const path = String(item?.path || item?.id || '')
                    const active = selectedCollection === path
                    return <button
                      type="button"
                      key={`fs-col:${path}`}
                      className={`firestore-tree-row collection ${active ? 'active' : ''}`}
                      onClick={() => loadDocuments(path, { preserveSelection: false })}
                      onContextMenu={(event: LegacyValue) => openContextMenu(event, { kind: 'collection', path, label: item.id })}
                      title={`${path} · 우클릭: Firestore Python 코드 생성`}
                    >
                      <span>▱</span><code>{item.id}</code>
                    </button>
                  })
                : <div className="sql-object-empty">표시할 Collection이 없습니다.</div>}
          </div>
        </div>
        <div className="firestore-document-pane">
          <div className="firestore-pane-head">
            <strong>Documents</strong>
            <small>{selectedCollection || '-'} · {visibleDocuments.length}</small>
            {selectedCollection && <button type="button" onClick={() => loadDocuments(selectedCollection)} disabled={documentsBusy}>↻</button>}
          </div>
          <div className="firestore-pane-scroll">
            {documentsBusy && !documents
              ? <div className="sql-object-empty">Document를 읽고 있습니다...</div>
              : !selectedCollection
                ? <div className="sql-object-empty">왼쪽 Collection을 선택하세요.</div>
                : visibleDocuments.length
                  ? visibleDocuments.map((item: LegacyValue) => {
                      const path = String(item?.path || '')
                      const active = selectedDocument === path
                      return <button
                        type="button"
                        key={`fs-doc:${path}`}
                        className={`firestore-tree-row document ${active ? 'active' : ''}`}
                        onClick={() => loadDocumentDetail(path)}
                        onContextMenu={(event: LegacyValue) => openContextMenu(event, { kind: 'document', path, label: item.id })}
                        title={`${path} · 우클릭: Firestore 연결/조회/등록/수정/삭제 Python 코드 생성`}
                      >
                        <span>◇</span><code>{item.id}</code><small>{item.field_count ?? 0} fields</small>
                      </button>
                    })
                  : <div className="sql-object-empty">표시할 Document가 없습니다.</div>}
          </div>
          {documents?.truncated && <div className="firestore-truncated">최대 {documents.limit || 500}개 문서까지만 표시합니다.</div>}
        </div>
      </div>
      <div className="firestore-detail-pane">
        {documentDetailBusy
          ? <div className="sql-object-empty">Document 필드를 읽고 있습니다...</div>
          : !detail
            ? <div className="sql-object-empty">Document를 선택하면 Field와 Value가 표시됩니다.</div>
            : <>
                <div className="firestore-detail-head">
                  <div><strong>{detail.id}</strong><small>{detail.path}</small></div>
                  <button type="button" onClick={() => loadDocumentDetail(String(detail.path || ''))} disabled={documentDetailBusy}>↻</button>
                </div>
                <div className="firestore-detail-meta">
                  <span>Fields <strong>{detail.field_count ?? 0}</strong></span>
                  {detail.update_time && <span>Updated <strong>{String(detail.update_time).replace('T', ' ')}</strong></span>}
                </div>
                <div className="firestore-detail-content">
                  {(detail.fields || []).length
                    ? <div className="firestore-field-grid">
                        <div className="firestore-field-grid-head"><span>Field</span><span>Type</span><span>Value</span></div>
                        {(detail.fields || []).map((field: LegacyValue, index: LegacyValue) => <div className="firestore-field-row" key={`${field.name}-${index}`}>
                          <div className="firestore-field-cell name"><code>{field.name}</code></div>
                          <div className="firestore-field-cell type"><span className={`firestore-field-type ${String(field.type || '').toLowerCase()}`}>{field.type || '-'}</span></div>
                          <div className="firestore-field-cell value"><pre>{firestoreValueText(field.value)}</pre></div>
                        </div>)}
                      </div>
                    : <div className="sql-object-empty">이 Document에는 표시할 Field가 없습니다.</div>}
                  {(detail.subcollections || []).length > 0 && <div className="firestore-subcollections"><strong>Subcollections</strong>{(detail.subcollections || []).map((item: LegacyValue) => <span key={item.path}>{item.id}</span>)}</div>}
                </div>
                {detail.refreshed_at && <div className="redis-detail-refreshed">Last refresh: {detail.refreshed_at.replace('T', ' ')}</div>}
              </>}
      </div>
    </div>
  </div>
}

interface RedisNodePayload {
  kind: 'group' | 'key'
  prefix?: string
  key?: string
  keyType?: string
  label?: string
}

export interface RedisBrowserPanelProps {
  connected?: boolean
  profile: DatabaseProfile
  browser: RedisBrowserResult | null
  browserBusy: boolean
  browserError: string
  keyFilter: string
  typeFilter: string
  selectedKey: string
  keyDetail: RedisKeyDetail | null
  keyDetailBusy: boolean
  keyExpanded: Record<string, boolean>
  setKeyFilter: (value: string) => void
  setTypeFilter: (value: string) => void
  toggleKeyGroup: (path: string) => void
  loadKeys: (options?: { quiet?: boolean; preserveSelection?: boolean }) => unknown
  loadKeyDetail: (key: string, options?: { quiet?: boolean }) => unknown
  openContextMenu: (event: React.MouseEvent<HTMLElement>, node: RedisNodePayload) => unknown
}

export function RedisBrowserPanel({
  connected,
  profile,
  browser,
  browserBusy,
  browserError,
  keyFilter,
  typeFilter,
  selectedKey,
  keyDetail,
  keyDetailBusy,
  keyExpanded,
  setKeyFilter,
  setTypeFilter,
  toggleKeyGroup,
  loadKeys,
  loadKeyDetail,
  openContextMenu,
}: RedisBrowserPanelProps) {
  if (!connected) {
    return <div className="sql-object-empty">Host/Port/DB index와 필요한 인증 정보를 입력한 뒤 연결 / 테스트를 실행하세요.</div>
  }

  const allKeys = Array.isArray(browser?.keys) ? browser.keys : []
  const visibleKeys = typeFilter === 'all' ? allKeys : allKeys.filter((item: LegacyValue) => String(item?.type || '').toLowerCase() === typeFilter)
  const tree = buildRedisKeyTree(visibleKeys)
  const detail = keyDetail
  const detailType = String(detail?.type || '').toLowerCase()

  const renderTreeNodes = (node: RedisTreeNode | null | undefined, level: LegacyValue = 0): React.ReactNode => {
    if (!node) return null
    return <>
      {(node.children || []).map((child: LegacyValue) => {
        const open = keyExpanded[child.path] !== false
        const descendantCount = countRedisTreeKeys(child)
        return <div className="redis-tree-group" key={`redis-group:${child.path}`}>
          <button
            type="button"
            className="redis-tree-row group"
            style={{ paddingLeft: `${8 + level * 14}px` }}
            onClick={() => toggleKeyGroup(child.path)}
            onContextMenu={(event: LegacyValue) => openContextMenu(event, { kind: 'group', prefix: child.path, label: child.path })}
            title={`${child.path} · 우클릭: Redis Python 코드 생성`}
          >
            <span className="redis-tree-caret">{open ? '⌄' : '›'}</span>
            <span className="redis-tree-folder">▱</span>
            <strong>{child.name}</strong>
            <em>{descendantCount || ''}</em>
          </button>
          {open && renderTreeNodes(child, level + 1)}
        </div>
      })}
      {(node.items || []).map((item: LegacyValue) => {
        const type = String(item?.type || 'unknown').toLowerCase()
        const active = selectedKey === item.key
        const fullKey = String(item?.key || '')
        const parentPrefix = fullKey.includes(':') ? fullKey.split(':').slice(0, -1).join(':') : ''
        return <button
          type="button"
          key={`redis-key:${item.key}`}
          className={`redis-tree-row key ${active ? 'active' : ''}`}
          style={{ paddingLeft: `${24 + level * 14}px` }}
          onClick={() => loadKeyDetail(fullKey)}
          onContextMenu={(event: LegacyValue) => openContextMenu(event, { kind: 'key', key: fullKey, keyType: type, prefix: parentPrefix, label: fullKey })}
          title={`${item.key} · 우클릭: 연결/조회/등록/수정/삭제 Python 코드 생성`}
        >
          <span className={`redis-type-badge ${type}`}>{type.toUpperCase()}</span>
          <code>{item.label || item.key}</code>
          <small><RedisTtlCountdown ttl={item.ttl} observedAt={browser?.__ttl_observed_at_ms} /></small>
        </button>
      })}
    </>
  }

  return <div className="redis-browser-shell">
    <div className="redis-browser-toolbar">
      <select value={typeFilter} onChange={(e: LegacyValue) => setTypeFilter(e.target.value)} title="Redis Key 타입 필터">
        <option value="all">All Key Types</option>
        <option value="string">STRING</option>
        <option value="hash">HASH</option>
        <option value="list">LIST</option>
        <option value="set">SET</option>
        <option value="zset">ZSET</option>
        <option value="stream">STREAM</option>
      </select>
      <div className="redis-key-search">
        <input
          value={keyFilter}
          onChange={(e: LegacyValue) => setKeyFilter(e.target.value)}
          onKeyDown={(e: LegacyValue) => { if (e.key === 'Enter') loadKeys({ preserveSelection: false }) }}
          placeholder="Filter by Key Name or Pattern"
        />
        <button type="button" onClick={() => loadKeys({ preserveSelection: false })} disabled={browserBusy}>⌕</button>
      </div>
    </div>
    <div className="redis-browser-summary">
      <strong>Results: {visibleKeys.length}</strong>
      <span>Total keys {browser?.total_keys ?? '-'} · DB {browser?.database ?? profile.database ?? '0'}</span>
      <button type="button" onClick={() => loadKeys()} disabled={browserBusy}>{browserBusy ? '조회 중...' : '↻ 새로고침'}</button>
    </div>
    {browserError && <div className="sql-object-error">{browserError}</div>}
    <div className="redis-browser-main">
      <div className="redis-key-pane">
        {browserBusy && !browser
          ? <div className="sql-object-empty">Redis Key를 읽고 있습니다...</div>
          : visibleKeys.length
            ? <div className="redis-key-tree">{renderTreeNodes(tree)}</div>
            : <div className="sql-object-empty">조건에 맞는 Redis Key가 없습니다.</div>}
      </div>
      <div className="redis-detail-pane">
        {keyDetailBusy
          ? <div className="sql-object-empty">Key 상세 값을 읽고 있습니다...</div>
          : !detail
            ? <div className="sql-object-empty">왼쪽 Key를 선택하면 값과 TTL 정보가 표시됩니다.</div>
            : <>
                <div className="redis-detail-head">
                  <div className="redis-detail-title">
                    <span className={`redis-type-badge large ${detailType}`}>{detailType.toUpperCase()}</span>
                    <strong title={detail.key}>{detail.key}</strong>
                  </div>
                  <button type="button" onClick={() => loadKeyDetail(String(detail.key || ''))} disabled={keyDetailBusy}>↻</button>
                </div>
                <div className="redis-detail-meta">
                  <span>Key Size: <strong>{formatRedisBytes(detail.size_bytes)}</strong></span>
                  <span>Length: <strong>{detail.length ?? '-'}</strong></span>
                  <span>TTL: <strong><RedisTtlCountdown ttl={detail.ttl} observedAt={detail.__ttl_observed_at_ms} /></strong></span>
                </div>
                <div className="redis-detail-content">
                  {detailType === 'string'
                    ? <pre className="redis-string-value">{String(detail.value ?? '')}</pre>
                    : detailType === 'hash'
                      ? <table className="redis-value-table"><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>{(detail.rows || []).map((row: LegacyValue, index: LegacyValue) => <tr key={`${row.field}-${index}`}><td>{row.field}</td><td>{String(row.value ?? '')}</td></tr>)}</tbody></table>
                      : ['list', 'set'].includes(detailType)
                        ? <table className="redis-value-table"><thead><tr><th>Index</th><th>Element</th></tr></thead><tbody>{(detail.rows || []).map((row: LegacyValue, index: LegacyValue) => <tr key={`${row.index}-${index}`}><td>{row.index}</td><td>{String(row.value ?? '')}</td></tr>)}</tbody></table>
                        : detailType === 'zset'
                          ? <table className="redis-value-table"><thead><tr><th>Index</th><th>Member</th><th>Score</th></tr></thead><tbody>{(detail.rows || []).map((row: LegacyValue, index: LegacyValue) => <tr key={`${row.member}-${index}`}><td>{row.index}</td><td>{row.member}</td><td>{row.score}</td></tr>)}</tbody></table>
                          : detailType === 'stream'
                            ? <table className="redis-value-table"><thead><tr><th>ID</th><th>Fields</th></tr></thead><tbody>{(detail.rows || []).map((row: LegacyValue, index: LegacyValue) => <tr key={`${row.id}-${index}`}><td>{row.id}</td><td><code>{JSON.stringify(row.fields, null, 2)}</code></td></tr>)}</tbody></table>
                            : <pre className="redis-string-value">{String(detail.value ?? '')}</pre>}
                  {detail.truncated && <div className="redis-detail-truncated">표시 성능을 위해 일부 데이터만 보여줍니다. 최대 {detail.max_items || 500}개 항목</div>}
                </div>
                {detail.refreshed_at && <div className="redis-detail-refreshed">Last refresh: {detail.refreshed_at.replace('T', ' ')}</div>}
              </>}
      </div>
    </div>
  </div>
}

const SQL_CATEGORIES: ReadonlyArray<readonly [SqlObjectCategory, string, string]> = [
  ['tables', '테이블', '▦'],
  ['views', '뷰', '◫'],
  ['procedures', '프로시저', '⚙'],
  ['functions', '함수', 'ƒ'],
  ['sequences', '시퀀스', '≋'],
  ['triggers', '트리거', '⚡'],
  ['indexes', '인덱스', '⌗'],
  ['packages', '패키지', '▣'],
]

export interface SqlObjectTreePanelProps {
  connected?: boolean
  profile: DatabaseProfile
  connectionStatus: DatabaseConnectionStatus | null
  dbObjects: SqlDatabaseObjectsResult | null
  busy: boolean
  error: string
  expanded: Record<string, boolean>
  actionBusy: string
  toggleObject: (key: string) => void
  openObject: (schemaName: string, category: SqlObjectCategory, item: SqlDatabaseObjectItem) => unknown
  openObjectContextMenu: (event: React.MouseEvent<HTMLElement>, schemaName: string, category: SqlObjectCategory, item: SqlDatabaseObjectItem) => unknown
  openSchemaContextMenu: (event: React.MouseEvent<HTMLElement>, schemaName: string) => unknown
  openDatabaseContextMenu: (event: React.MouseEvent<HTMLElement>) => unknown
}

export function SqlObjectTreePanel({
  connected,
  profile,
  connectionStatus,
  dbObjects,
  busy,
  error,
  expanded,
  actionBusy,
  toggleObject,
  openObject,
  openObjectContextMenu,
  openSchemaContextMenu,
  openDatabaseContextMenu,
}: SqlObjectTreePanelProps) {
  if (!connected) return <div className="sql-object-empty">DB에 연결하면 개발 객체 목록이 표시됩니다.</div>
  if (busy && !dbObjects) return <div className="sql-object-empty">DB 객체를 읽고 있습니다...</div>
  if (error) return <div className="sql-object-error">{error}</div>
  if (!dbObjects?.schemas?.length) return <div className="sql-object-empty">표시할 DB 객체가 없습니다.</div>

  return <div className="sql-object-tree">
    <button
      type="button"
      className="sql-database-root-row"
      onContextMenu={openDatabaseContextMenu}
      title="데이터베이스 우클릭: PostgreSQL 세션 / Lock 관리 SQL 생성"
    >
      <span className="sql-database-root-icon">🗄</span>
      <strong>{dbObjects?.database || connectionStatus?.profile?.database || profile.database || 'Database'}</strong>
      <small>{String(dbObjects?.db_type || profile.db_type || '').toUpperCase()}</small>
      <em>우클릭 메뉴</em>
    </button>
    {dbObjects.schemas.map((schema: SqlObjectSchema, schemaIndex: LegacyValue) => {
      const schemaName = String(schema.name || `schema-${schemaIndex}`)
      const schemaKey = `schema:${schemaName}`
      const schemaOpen = !!expanded[schemaKey]
      const categories = SQL_CATEGORIES.filter(([key]: LegacyValue) => (schema[key as keyof SqlObjectSchema] || []).length)
      const schemaCount = categories.reduce((sum: LegacyValue, [key]: LegacyValue) => sum + (schema[key as keyof SqlObjectSchema]?.length || 0), 0)
      return <div className="sql-object-schema" key={schemaName}>
        <button type="button" className="sql-object-tree-row schema" onClick={() => toggleObject(schemaKey)} onContextMenu={(event: LegacyValue) => openSchemaContextMenu(event, schemaName)} title={`${schemaName} · 우클릭: 스키마 전체 다이어그램 보기`}>
          <span className="tree-caret">{schemaOpen ? '−' : '+'}</span>
          <span className="tree-icon">◈</span>
          <strong>{schemaName}</strong>
          <em>{schemaCount}</em>
        </button>
        {schemaOpen && <div className="sql-object-schema-body">
          {categories.map(([category, label, icon]: LegacyValue) => {
            const categoryKey = `category:${schemaName}:${category}`
            const categoryOpen = !!expanded[categoryKey]
            const items = (schema[category as keyof SqlObjectSchema] || []) as SqlDatabaseObjectItem[]
            return <div className="sql-object-category" key={category}>
              <button type="button" className="sql-object-tree-row category" onClick={() => toggleObject(categoryKey)}>
                <span className="tree-caret">{categoryOpen ? '−' : '+'}</span>
                <span className="tree-icon">{icon}</span>
                <span>{label}</span>
                <em>{items.length}</em>
              </button>
              {categoryOpen && <div className="sql-object-items">
                {items.map((item: LegacyValue, index: LegacyValue) => {
                  const itemName = String(item.name || '')
                  const itemKey = `item:${schemaName}:${category}:${itemName}:${index}`
                  const hasColumns = Array.isArray(item.columns) && item.columns.length > 0
                  const itemOpen = !!expanded[itemKey]
                  return <div className="sql-object-item" key={itemKey}>
                    <button
                      type="button"
                      className="sql-object-tree-row item"
                      onClick={() => hasColumns && toggleObject(itemKey)}
                      onDoubleClick={(event: LegacyValue) => {
                        event.preventDefault()
                        event.stopPropagation()
                        openObject(schemaName, category, item)
                      }}
                      onContextMenu={(event: LegacyValue) => openObjectContextMenu(event, schemaName, category, item)}
                      title={`${String(item.qualified_name || itemName)} · 더블클릭하여 ${category === 'tables' ? '전체 컬럼 SELECT 조회 · 우클릭: DDL/ALTER/SELECT/INSERT/UPDATE/DELETE 생성' : '수정용 임시 SQL 열기'}`}
                      disabled={actionBusy === `${schemaName}:${category}:${itemName}`}
                    >
                      <span className={`tree-caret ${hasColumns ? '' : 'empty'}`}>{hasColumns ? (itemOpen ? '−' : '+') : ''}</span>
                      <code>{itemName}</code>
                      {item.arguments && <small>({String(item.arguments)})</small>}
                      {item.table && <small>→ {String(item.table)}</small>}
                    </button>
                    {hasColumns && itemOpen && <div className="sql-object-columns">
                      {(item.columns || []).map((column: LegacyValue, columnIndex: LegacyValue) => <div className="sql-object-column" key={`${column.name}-${columnIndex}`}>
                        <span>◇</span>
                        <code>{column.name}</code>
                        <small>{column.data_type}{column.nullable ? ' · NULL' : ''}</small>
                      </div>)}
                    </div>}
                  </div>
                })}
              </div>}
            </div>
          })}
        </div>}
      </div>
    })}
  </div>
}

interface ContextMenuProps {
  firestoreContextMenu: FirestoreContextMenuState | null
  firestoreScriptBusy: string
  createFirestorePythonScript: (action: string) => unknown
  redisContextMenu: RedisContextMenuState | null
  redisScriptBusy: string
  createRedisPythonScript: (action: string) => unknown
  sqlObjectContextMenu: SqlObjectContextMenuState | null
  sqlSchemaContextMenu: SqlSchemaContextMenuState | null
  sqlObjectActionBusy: string
  createSqlTableDiagram: (schemaName: string, item: SqlDatabaseObjectItem) => unknown
  createSqlSchemaDiagram: (schemaName: string) => unknown
  createSqlTableScript: (schemaName: string, item: SqlDatabaseObjectItem) => unknown
  createSqlTableAlterScript: (schemaName: string, item: SqlDatabaseObjectItem) => unknown
  createSqlTableDmlScript: (schemaName: string, item: SqlDatabaseObjectItem, action: string) => unknown
  sqlDatabaseContextMenu: SqlDatabaseContextMenuState | null
  dbObjects: SqlDatabaseObjectsResult | null
  profile: DatabaseProfile
  createPostgresqlAdminScript: (action: string, value?: string) => unknown
  openSqlAdminPrompt: (action: string) => unknown
  sqlAdminPrompt: SqlAdminPromptState | null
  setSqlAdminPrompt: React.Dispatch<React.SetStateAction<SqlAdminPromptState | null>>
  submitSqlAdminPrompt: () => unknown
}

export function DatabaseBrowserContextMenus({
  firestoreContextMenu,
  firestoreScriptBusy,
  createFirestorePythonScript,
  redisContextMenu,
  redisScriptBusy,
  createRedisPythonScript,
  sqlObjectContextMenu,
  sqlSchemaContextMenu,
  sqlObjectActionBusy,
  createSqlTableDiagram,
  createSqlSchemaDiagram,
  createSqlTableScript,
  createSqlTableAlterScript,
  createSqlTableDmlScript,
  sqlDatabaseContextMenu,
  dbObjects,
  profile,
  createPostgresqlAdminScript,
  openSqlAdminPrompt,
  sqlAdminPrompt,
  setSqlAdminPrompt,
  submitSqlAdminPrompt,
}: ContextMenuProps) {
  return <>
    {firestoreContextMenu && <div
      className="sql-object-context-menu firestore-context-menu"
      style={{ left: firestoreContextMenu.x, top: firestoreContextMenu.y }}
      onMouseDown={(event: LegacyValue) => event.stopPropagation()}
    >
      <div className="sql-context-menu-title">
        <strong>{firestoreContextMenu.label || 'Firestore'}</strong>
        <small>{firestoreContextMenu.nodeKind === 'document' ? 'Firestore Document' : 'Firestore Collection'} · {firestoreContextMenu.path || '-'}</small>
      </div>
      {([
        ['connection', '⛓', 'Google Cloud Firestore 연결코드', '현재 Project/Database/Service Account 경로 기반 연결 코드'],
        ['list', '☷', '리스트 조회', firestoreContextMenu.nodeKind === 'document' ? 'Document Fields / Subcollection 목록 조회' : 'Collection의 Document ID 목록 조회'],
        ['read', '⌕', '조회', firestoreContextMenu.nodeKind === 'document' ? '선택 Document 전체 데이터 조회' : 'Collection 문서 데이터 조회'],
        ['create', '＋', '등록', firestoreContextMenu.nodeKind === 'document' ? '선택 Document에 새 Field 병합 예제' : '새 Document 등록 예제'],
        ['update', '✎', '수정', firestoreContextMenu.nodeKind === 'document' ? '선택 Document Field 수정 예제' : 'Document ID 지정 수정 예제'],
        ['delete', '🗑', '삭제', '삭제 확인 가드가 포함된 안전한 삭제 예제'],
      ] as const).map(([action, icon, title, description]: LegacyValue) => <button
        type="button"
        key={action}
        className={action === 'delete' ? 'firestore-menu-danger' : ''}
        onClick={() => createFirestorePythonScript(action)}
        disabled={!!firestoreScriptBusy}
      >
        <span>{icon}</span>
        <div><strong>{title}</strong><small>{description}</small></div>
      </button>)}
      <div className="firestore-context-note">임시 `.py` 파일만 생성하며 자동 실행하지 않습니다. Service Account Private Key 내용은 파일에 복사하지 않습니다.</div>
    </div>}

    {redisContextMenu && <div
      className="sql-object-context-menu redis-context-menu"
      style={{ left: redisContextMenu.x, top: redisContextMenu.y }}
      onMouseDown={(event: LegacyValue) => event.stopPropagation()}
    >
      <div className="sql-context-menu-title">
        <strong>{redisContextMenu.label || 'Redis'}</strong>
        <small>{redisContextMenu.nodeKind === 'group' ? 'Redis Key 그룹' : 'Redis Key'}{redisContextMenu.keyType ? ` · ${redisContextMenu.keyType.toUpperCase()}` : ''}</small>
      </div>
      {([
        ['connection', '⛓', 'Redis 연결코드', '현재 Host/Port/DB/User 기반 redis-py 연결 코드'],
        ['list', '☷', '리스트 조회', '선택 노드 범위 Key 또는 LIST 요소 조회'],
        ['read', '⌕', '조회', 'Key 타입에 맞는 조회 명령 생성'],
        ['create', '＋', '등록', 'Key 타입에 맞는 등록 예제'],
        ['update', '✎', '수정', 'Key 타입에 맞는 수정 예제'],
        ['delete', '🗑', '삭제', '삭제 확인 가드가 포함된 안전한 삭제 예제'],
      ] as const).map(([action, icon, title, description]: LegacyValue) => <button
        type="button"
        key={action}
        className={action === 'delete' ? 'redis-menu-danger' : ''}
        onClick={() => createRedisPythonScript(action)}
        disabled={!!redisScriptBusy}
      >
        <span>{icon}</span>
        <div><strong>{title}</strong><small>{description}</small></div>
      </button>)}
      <div className="redis-context-note">임시 `.py` 파일만 생성하며 자동 실행하지 않습니다. 저장된 비밀번호는 파일에 평문으로 넣지 않습니다.</div>
    </div>}

    {sqlSchemaContextMenu && <div
      className="sql-object-context-menu sql-schema-context-menu"
      style={{ left: sqlSchemaContextMenu.x, top: sqlSchemaContextMenu.y }}
      onMouseDown={(event: LegacyValue) => event.stopPropagation()}
    >
      <div className="sql-context-menu-title">
        <strong>{sqlSchemaContextMenu.schemaName}</strong>
        <small>Schema · PostgreSQL ERD</small>
      </div>
      {['postgresql', 'supabase'].includes(String(dbObjects?.db_type || profile.db_type || '').toLowerCase())
        ? <button type="button" onClick={() => createSqlSchemaDiagram(sqlSchemaContextMenu.schemaName)} disabled={!!sqlObjectActionBusy}>
            <span>▦</span><div><strong>전체 다이어그램 보기</strong><small>스키마의 모든 테이블 + 내부 FK 관계를 임시 ERD 탭으로 열기 · PNG 내보내기</small></div>
          </button>
        : <div className="sql-context-menu-disabled-note">스키마 전체 다이어그램은 PostgreSQL / Supabase PostgreSQL 연결에서 지원합니다.</div>}
    </div>}

    {sqlObjectContextMenu && <div
      className="sql-object-context-menu"
      style={{ left: sqlObjectContextMenu.x, top: sqlObjectContextMenu.y }}
      onMouseDown={(event: LegacyValue) => event.stopPropagation()}
    >
      {['postgresql', 'supabase'].includes(String(dbObjects?.db_type || profile.db_type || '').toLowerCase()) && <button type="button" onClick={() => createSqlTableDiagram(sqlObjectContextMenu.schemaName, sqlObjectContextMenu.item)} disabled={!!sqlObjectActionBusy}>
        <span>▦</span><div><strong>다이어그램 보기</strong><small>선택 테이블 + 직접 FK 관계를 임시 ERD 탭으로 열기 · PNG 내보내기</small></div>
      </button>}
      <button type="button" onClick={() => createSqlTableScript(sqlObjectContextMenu.schemaName, sqlObjectContextMenu.item)} disabled={!!sqlObjectActionBusy}>
        <span>📜</span><div><strong>테이블 스크립트 보기</strong><small>CREATE TABLE DDL을 임시 SQL로 열기</small></div>
      </button>
      <button type="button" onClick={() => createSqlTableAlterScript(sqlObjectContextMenu.schemaName, sqlObjectContextMenu.item)} disabled={!!sqlObjectActionBusy}>
        <span>🛠</span><div><strong>테이블 수정 스크립트 보기</strong><small>ALTER TABLE 템플릿을 임시 SQL로 열기</small></div>
      </button>
      <div className="sql-context-menu-section">DML 스크립트 생성</div>
      {([
        ['select', '🔎', 'SELECT 생성', '현재 컬럼 기준 조회 SQL'],
        ['insert', '＋', 'INSERT 생성', '현재 컬럼 기준 입력 SQL'],
        ['update', '✎', 'UPDATE 생성', 'PK 기반 수정 SQL'],
        ['delete', '🗑', 'DELETE 생성', 'PK 기반 삭제 SQL'],
      ] as const).map(([action, icon, title, description]: LegacyValue) => <button
        type="button"
        key={action}
        onClick={() => createSqlTableDmlScript(sqlObjectContextMenu.schemaName, sqlObjectContextMenu.item, action)}
        disabled={!!sqlObjectActionBusy}
      >
        <span>{icon}</span><div><strong>{title}</strong><small>{description}</small></div>
      </button>)}
    </div>}

    {sqlDatabaseContextMenu && <div
      className="sql-object-context-menu sql-database-context-menu"
      style={{ left: sqlDatabaseContextMenu.x, top: sqlDatabaseContextMenu.y }}
      onMouseDown={(event: LegacyValue) => event.stopPropagation()}
    >
      <div className="sql-context-menu-title">
        <strong>{dbObjects?.database || profile.database || 'Database'}</strong>
        <small>{String(dbObjects?.db_type || profile.db_type || '').toUpperCase()} · 세션 / Lock 관리</small>
      </div>
      {String(dbObjects?.db_type || profile.db_type || '').toLowerCase() !== 'postgresql'
        ? <div className="sql-context-menu-disabled-note">현재 메뉴는 PostgreSQL 연결에서 지원합니다.</div>
        : <>
            <button type="button" onClick={() => createPostgresqlAdminScript('sessions')} disabled={!!sqlObjectActionBusy}><span>◉</span><div><strong>현재 실행 중인 세션 보기</strong><small>pg_stat_activity 조회</small></div></button>
            <button type="button" onClick={() => createPostgresqlAdminScript('locks')} disabled={!!sqlObjectActionBusy}><span>🔒</span><div><strong>실제 Lock 목록 보기</strong><small>pg_locks + pg_stat_activity</small></div></button>
            <button type="button" onClick={() => createPostgresqlAdminScript('blocking')} disabled={!!sqlObjectActionBusy}><span>⇄</span><div><strong>누가 누구를 막고 있는지 보기</strong><small>pg_blocking_pids 기반</small></div></button>
            <button type="button" onClick={() => openSqlAdminPrompt('table_locks')} disabled={!!sqlObjectActionBusy}><span>▦</span><div><strong>특정 테이블 Lock만 보기</strong><small>테이블명을 입력해 SQL 생성</small></div></button>
            <button type="button" onClick={() => createPostgresqlAdminScript('backend_pid')} disabled={!!sqlObjectActionBusy}><span>#</span><div><strong>현재 내 DBeaver 세션의 PID 보기</strong><small>실행 위치의 pg_backend_pid()</small></div></button>
            <div className="sql-context-menu-section danger">세션 제어 SQL 생성</div>
            <button type="button" onClick={() => openSqlAdminPrompt('cancel_backend')} disabled={!!sqlObjectActionBusy}><span>■</span><div><strong>쿼리만 중지하고 DB 접속 유지</strong><small>PID 입력 → pg_cancel_backend</small></div></button>
            <button type="button" onClick={() => openSqlAdminPrompt('terminate_backend')} disabled={!!sqlObjectActionBusy}><span>⛔</span><div><strong>DB 연결 자체를 강제로 종료</strong><small>PID 입력 → pg_terminate_backend</small></div></button>
            <button type="button" onClick={() => openSqlAdminPrompt('terminate_others')} disabled={!!sqlObjectActionBusy}><span>⚠</span><div><strong>다른 세션만 종료 처리</strong><small>현재 세션 제외 · 상태 조건 입력</small></div></button>
          </>}
    </div>}

    {sqlAdminPrompt && <div className="sql-admin-prompt-backdrop" onMouseDown={() => setSqlAdminPrompt(null)}>
      <div className={`sql-admin-prompt ${sqlAdminPrompt.danger ? 'danger' : ''}`} onMouseDown={(event: LegacyValue) => event.stopPropagation()}>
        <div className="sql-admin-prompt-head">
          <div><strong>{sqlAdminPrompt.title}</strong><small>입력한 값을 반영한 SQL 임시 파일만 생성합니다. 자동 실행되지 않습니다.</small></div>
          <button type="button" onClick={() => setSqlAdminPrompt(null)}>×</button>
        </div>
        <label>
          <span>{sqlAdminPrompt.label}</span>
          <input
            autoFocus
            value={sqlAdminPrompt.value}
            placeholder={sqlAdminPrompt.placeholder}
            onChange={(event: LegacyValue) => setSqlAdminPrompt((prev: LegacyValue) => prev ? ({ ...prev, value: event.target.value }) : prev)}
            onKeyDown={(event: LegacyValue) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                submitSqlAdminPrompt()
              }
              if (event.key === 'Escape') setSqlAdminPrompt(null)
            }}
          />
        </label>
        {sqlAdminPrompt.danger && <div className="sql-admin-prompt-warning">⚠ 생성된 세션 취소/종료 SQL은 실행 전에 PID와 조건을 반드시 다시 확인하세요.</div>}
        <div className="sql-admin-prompt-actions">
          <button type="button" onClick={() => setSqlAdminPrompt(null)}>취소</button>
          <button type="button" className="primary" onClick={() => submitSqlAdminPrompt()} disabled={!String(sqlAdminPrompt.value ?? '').trim()}>SQL 임시파일 생성</button>
        </div>
      </div>
    </div>}
  </>
}
