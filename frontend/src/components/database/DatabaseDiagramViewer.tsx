import React, { useMemo, useRef, useState } from 'react'
import type {
  DatabaseDiagramDocument,
  DatabaseDiagramRelationship,
  DatabaseDiagramTable,
} from '../../types/database'

interface DatabaseDiagramViewerProps {
  value: string
  filePath?: string
}

interface PositionedTable extends DatabaseDiagramTable {
  x: number
  y: number
  width: number
  height: number
}

const TABLE_WIDTH = 280
const HEADER_HEIGHT = 38
const ROW_HEIGHT = 24
const TABLE_GAP = 34
const LEFT_X = 36
const ROOT_X = 382
const RIGHT_X = 728
const PADDING_Y = 38

function parseDiagram(value: string): DatabaseDiagramDocument {
  const parsed = JSON.parse(String(value || '{}')) as DatabaseDiagramDocument
  if (!['database_table_diagram', 'database_schema_diagram'].includes(String(parsed?.kind || '')) || !Array.isArray(parsed.tables)) {
    throw new Error('AgentStudio DB 다이어그램 형식이 아닙니다.')
  }
  return parsed
}

function tableHeight(table: DatabaseDiagramTable): number {
  return HEADER_HEIGHT + Math.max(1, table.columns?.length || 0) * ROW_HEIGHT
}

function stackTables(tables: DatabaseDiagramTable[], x: number): PositionedTable[] {
  let y = PADDING_Y
  return tables.map(table => {
    const height = tableHeight(table)
    const positioned = { ...table, x, y, width: TABLE_WIDTH, height }
    y += height + TABLE_GAP
    return positioned
  })
}

function buildSchemaLayout(document: DatabaseDiagramDocument) {
  const tables = [...document.tables].sort((a, b) => a.name.localeCompare(b.name))
  if (!tables.length) return { tables: [] as PositionedTable[], width: 1044, height: 420 }
  const count = tables.length
  const columnCount = Math.min(8, Math.max(2, Math.ceil(Math.sqrt(count))))
  const columnGap = 72
  const paddingX = 36
  const columnHeights = Array.from({ length: columnCount }, () => PADDING_Y)
  const positioned: PositionedTable[] = []
  for (const table of tables) {
    let columnIndex = 0
    for (let index = 1; index < columnHeights.length; index += 1) {
      if (columnHeights[index]! < columnHeights[columnIndex]!) columnIndex = index
    }
    const height = tableHeight(table)
    const x = paddingX + columnIndex * (TABLE_WIDTH + columnGap)
    const y = columnHeights[columnIndex]!
    positioned.push({ ...table, x, y, width: TABLE_WIDTH, height })
    columnHeights[columnIndex] = y + height + TABLE_GAP
  }
  const width = paddingX * 2 + columnCount * TABLE_WIDTH + Math.max(0, columnCount - 1) * columnGap
  const height = Math.max(420, ...columnHeights) + PADDING_Y
  return { tables: positioned, width, height }
}

function buildLayout(document: DatabaseDiagramDocument) {
  if (document.kind === 'database_schema_diagram') return buildSchemaLayout(document)
  const root = document.tables.find(table => table.id === document.root_table) || document.tables[0]
  if (!root) return { tables: [] as PositionedTable[], width: 1044, height: 420 }

  const leftIds = new Set<string>()
  const rightIds = new Set<string>()
  for (const relation of document.relationships || []) {
    if (relation.to_table === root.id && relation.from_table !== root.id) leftIds.add(relation.from_table)
    if (relation.from_table === root.id && relation.to_table !== root.id) rightIds.add(relation.to_table)
  }

  const others = document.tables.filter(table => table.id !== root.id)
  const left = others.filter(table => leftIds.has(table.id))
  const right = others.filter(table => rightIds.has(table.id) && !leftIds.has(table.id))
  const unassigned = others.filter(table => !leftIds.has(table.id) && !rightIds.has(table.id))
  unassigned.forEach((table, index) => (index % 2 ? right : left).push(table))

  const leftPositioned = stackTables(left, LEFT_X)
  const rightPositioned = stackTables(right, RIGHT_X)
  const leftHeight = leftPositioned.length ? leftPositioned.at(-1)!.y + leftPositioned.at(-1)!.height : PADDING_Y
  const rightHeight = rightPositioned.length ? rightPositioned.at(-1)!.y + rightPositioned.at(-1)!.height : PADDING_Y
  const rootHeight = tableHeight(root)
  const contentHeight = Math.max(leftHeight, rightHeight, rootHeight + PADDING_Y * 2)
  const rootY = Math.max(PADDING_Y, Math.round((contentHeight - rootHeight) / 2))
  const rootPositioned: PositionedTable = { ...root, x: ROOT_X, y: rootY, width: TABLE_WIDTH, height: rootHeight }
  const tables = [...leftPositioned, rootPositioned, ...rightPositioned]
  const maxBottom = Math.max(...tables.map(table => table.y + table.height), 320)
  return { tables, width: 1044, height: maxBottom + PADDING_Y }
}

function columnAnchor(table: PositionedTable, columnName: string | undefined, side: 'left' | 'right') {
  const columnIndex = Math.max(0, table.columns.findIndex(column => column.name === columnName))
  const x = side === 'left' ? table.x : table.x + table.width
  const y = table.y + HEADER_HEIGHT + (columnIndex + 0.5) * ROW_HEIGHT
  return { x, y }
}

function relationshipPath(
  relationship: DatabaseDiagramRelationship,
  tableMap: Map<string, PositionedTable>,
): { d: string; labelX: number; labelY: number } | null {
  const source = tableMap.get(relationship.from_table)
  const target = tableMap.get(relationship.to_table)
  if (!source || !target) return null

  if (source.id === target.id) {
    const start = columnAnchor(source, relationship.from_columns?.[0], 'right')
    const end = columnAnchor(target, relationship.to_columns?.[0], 'right')
    const loopX = source.x + source.width + 56
    return {
      d: `M ${start.x} ${start.y} L ${loopX} ${start.y} L ${loopX} ${end.y + 24} L ${end.x} ${end.y + 24} L ${end.x} ${end.y}`,
      labelX: loopX + 4,
      labelY: Math.min(start.y, end.y) + 18,
    }
  }

  if (source.x === target.x) {
    const useRight = source.y <= target.y
    const side = useRight ? 'right' : 'left'
    const start = columnAnchor(source, relationship.from_columns?.[0], side)
    const end = columnAnchor(target, relationship.to_columns?.[0], side)
    const routeX = useRight ? source.x + source.width + 24 : source.x - 24
    return {
      d: `M ${start.x} ${start.y} L ${routeX} ${start.y} L ${routeX} ${end.y} L ${end.x} ${end.y}`,
      labelX: useRight ? routeX + 4 : routeX - 4,
      labelY: Math.round((start.y + end.y) / 2) - 5,
    }
  }

  const sourceOnLeft = source.x < target.x
  const start = columnAnchor(source, relationship.from_columns?.[0], sourceOnLeft ? 'right' : 'left')
  const end = columnAnchor(target, relationship.to_columns?.[0], sourceOnLeft ? 'left' : 'right')
  const midX = Math.round((start.x + end.x) / 2)
  return {
    d: `M ${start.x} ${start.y} L ${midX} ${start.y} L ${midX} ${end.y} L ${end.x} ${end.y}`,
    labelX: midX + 5,
    labelY: Math.round((start.y + end.y) / 2) - 5,
  }
}

function safePngName(document: DatabaseDiagramDocument): string {
  const sourceName = document.kind === 'database_schema_diagram' ? `schema_${document.schema_name || 'diagram'}` : document.root_table
  const base = String(sourceName || 'database_diagram').replace(/[^a-zA-Z0-9._-]+/g, '_')
  return `${base || 'database_diagram'}.png`
}

export function DatabaseDiagramViewer({ value, filePath = '' }: DatabaseDiagramViewerProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const dragRef = useRef({ active: false, startX: 0, startY: 0, scrollLeft: 0, scrollTop: 0 })
  const [zoom, setZoom] = useState(1)
  const [exportBusy, setExportBusy] = useState(false)
  const [message, setMessage] = useState('')
  const parsed = useMemo(() => {
    try {
      return { document: parseDiagram(value), error: '' }
    } catch (error) {
      return { document: null, error: String(error instanceof Error ? error.message : error) }
    }
  }, [value])

  const layout = useMemo(() => parsed.document ? buildLayout(parsed.document) : { tables: [], width: 1044, height: 420 }, [parsed.document])
  const tableMap = useMemo(() => new Map(layout.tables.map(table => [table.id, table])), [layout.tables])

  const exportPng = async () => {
    if (!svgRef.current || !parsed.document || exportBusy) return
    setExportBusy(true)
    setMessage('PNG 생성 중…')
    try {
      const serializer = new XMLSerializer()
      const clone = svgRef.current.cloneNode(true) as SVGSVGElement
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
      clone.setAttribute('width', String(layout.width))
      clone.setAttribute('height', String(layout.height))
      clone.style.transform = 'none'
      clone.style.transformOrigin = '0 0'
      const svgText = serializer.serializeToString(clone)
      const blob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      try {
        const image = new Image()
        await new Promise<void>((resolve, reject) => {
          image.onload = () => resolve()
          image.onerror = () => reject(new Error('SVG를 PNG로 변환하지 못했습니다.'))
          image.src = url
        })
        const scale = 2
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(1, Math.round(layout.width * scale))
        canvas.height = Math.max(1, Math.round(layout.height * scale))
        const ctx = canvas.getContext('2d')
        if (!ctx) throw new Error('Canvas를 초기화하지 못했습니다.')
        ctx.scale(scale, scale)
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, layout.width, layout.height)
        ctx.drawImage(image, 0, 0, layout.width, layout.height)
        const pngBlob = await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob(result => result ? resolve(result) : reject(new Error('PNG Blob 생성에 실패했습니다.')), 'image/png')
        })
        const pngUrl = URL.createObjectURL(pngBlob)
        try {
          const anchor = document.createElement('a')
          anchor.href = pngUrl
          anchor.download = safePngName(parsed.document)
          document.body.appendChild(anchor)
          anchor.click()
          anchor.remove()
        } finally {
          URL.revokeObjectURL(pngUrl)
        }
        setMessage('PNG 내보내기 완료')
      } finally {
        URL.revokeObjectURL(url)
      }
    } catch (error) {
      setMessage(`PNG 내보내기 실패: ${String(error instanceof Error ? error.message : error)}`)
    } finally {
      setExportBusy(false)
    }
  }

  if (parsed.error || !parsed.document) {
    return <div className="database-diagram-error">
      <strong>DB 다이어그램을 열 수 없습니다.</strong>
      <p>{parsed.error || '다이어그램 데이터가 없습니다.'}</p>
      <code>{filePath}</code>
    </div>
  }

  const diagram = parsed.document
  const isSchemaDiagram = diagram.kind === 'database_schema_diagram'
  const diagramTitle = isSchemaDiagram ? `${diagram.schema_name || 'Schema'} 전체 다이어그램` : diagram.root_table
  return <div className="database-diagram-viewer">
    <div className="database-diagram-toolbar">
      <div>
        <strong>{diagramTitle}</strong>
        <span>{String(diagram.db_type || '').toUpperCase()} · {diagram.database || '-'} · 테이블 {diagram.tables.length}개 · 관계 {diagram.relationships.length}개</span>
      </div>
      <div className="database-diagram-actions">
        {message && <small>{message}</small>}
        <div className="database-diagram-zoom" aria-label="다이어그램 확대 축소">
          <button type="button" onClick={() => setZoom(value => Math.max(0.5, Math.round((value - 0.1) * 10) / 10))}>−</button>
          <button type="button" className="zoom-value" onClick={() => setZoom(1)} title="100%로 복원">{Math.round(zoom * 100)}%</button>
          <button type="button" onClick={() => setZoom(value => Math.min(2, Math.round((value + 0.1) * 10) / 10))}>＋</button>
        </div>
        <button type="button" onClick={exportPng} disabled={exportBusy}>{exportBusy ? 'PNG 생성 중…' : 'PNG 내보내기'}</button>
      </div>
    </div>
    <div
      ref={scrollRef}
      className="database-diagram-canvas-scroll"
      onMouseDown={(event: React.MouseEvent<HTMLDivElement>) => {
        if (event.button !== 0 || !scrollRef.current) return
        dragRef.current = {
          active: true,
          startX: event.clientX,
          startY: event.clientY,
          scrollLeft: scrollRef.current.scrollLeft,
          scrollTop: scrollRef.current.scrollTop,
        }
        event.currentTarget.classList.add('dragging')
      }}
      onMouseMove={(event: React.MouseEvent<HTMLDivElement>) => {
        if (!dragRef.current.active || !scrollRef.current) return
        scrollRef.current.scrollLeft = dragRef.current.scrollLeft - (event.clientX - dragRef.current.startX)
        scrollRef.current.scrollTop = dragRef.current.scrollTop - (event.clientY - dragRef.current.startY)
      }}
      onMouseUp={(event: React.MouseEvent<HTMLDivElement>) => { dragRef.current.active = false; event.currentTarget.classList.remove('dragging') }}
      onMouseLeave={(event: React.MouseEvent<HTMLDivElement>) => { dragRef.current.active = false; event.currentTarget.classList.remove('dragging') }}
    >
      <div className="database-diagram-zoom-stage" style={{ width: layout.width * zoom, height: layout.height * zoom }}>
      <svg
        ref={svgRef}
        className="database-diagram-svg"
        width={layout.width}
        height={layout.height}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-label={`${diagramTitle} ERD 다이어그램`}
        style={{ transform: `scale(${zoom})`, transformOrigin: '0 0' }}
      >
        <rect x="0" y="0" width={layout.width} height={layout.height} fill="#ffffff" />
        <defs>
          <marker id="agentstudio-diagram-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
            <path d="M 0 0 L 8 4 L 0 8 z" fill="#6b8194" />
          </marker>
        </defs>
        {(diagram.relationships || []).map((relationship, index) => {
          const route = relationshipPath(relationship, tableMap)
          if (!route) return null
          return <g key={`${relationship.name || 'fk'}-${index}`}>
            <path d={route.d} fill="none" stroke="#6b8194" strokeWidth="1.5" markerEnd="url(#agentstudio-diagram-arrow)" />
            {relationship.name && <text x={route.labelX} y={route.labelY} fontSize="10" fill="#647583">{relationship.name}</text>}
          </g>
        })}
        {layout.tables.map(table => {
          const root = !isSchemaDiagram && table.id === diagram.root_table
          return <g key={table.id}>
            <rect x={table.x} y={table.y} width={table.width} height={table.height} rx="2" fill="#ffffff" stroke={root ? '#2679b8' : '#8ba5b8'} strokeWidth={root ? 2 : 1.2} />
            <rect x={table.x} y={table.y} width={table.width} height={HEADER_HEIGHT} rx="2" fill={root ? '#dceefb' : '#edf4f8'} stroke={root ? '#2679b8' : '#8ba5b8'} strokeWidth={root ? 2 : 1.2} />
            <text x={table.x + 12} y={table.y + 24} fontSize="14" fontWeight="700" fill="#102535">{table.name}</text>
            <text x={table.x + table.width - 10} y={table.y + 24} textAnchor="end" fontSize="9" fill="#60798c">{table.schema}</text>
            {(table.columns || []).map((column, index) => {
              const rowY = table.y + HEADER_HEIGHT + index * ROW_HEIGHT
              const badges = [column.primary_key ? 'PK' : '', column.foreign_key ? 'FK' : ''].filter(Boolean).join('/')
              return <g key={`${table.id}:${column.name}:${index}`}>
                {index > 0 && <line x1={table.x} y1={rowY} x2={table.x + table.width} y2={rowY} stroke="#d7e0e6" strokeWidth="1" />}
                <text x={table.x + 10} y={rowY + 16} fontSize="11" fontWeight={column.primary_key ? '700' : '400'} fill="#173144">{column.name}</text>
                {badges && <text x={table.x + 155} y={rowY + 16} fontSize="9" fontWeight="700" fill={column.primary_key ? '#bd5f1d' : '#356f9d'}>{badges}</text>}
                <text x={table.x + table.width - 10} y={rowY + 16} textAnchor="end" fontSize="9.5" fill="#5f7180">{column.data_type || ''}{column.nullable ? ' ?' : ''}</text>
              </g>
            })}
            {(!table.columns || table.columns.length === 0) && <text x={table.x + 10} y={table.y + HEADER_HEIGHT + 16} fontSize="10" fill="#778895">컬럼 메타데이터 없음</text>}
          </g>
        })}
      </svg>
      </div>
    </div>
    <div className="database-diagram-footer">{isSchemaDiagram ? '선택 스키마의 모든 테이블과 스키마 내부 Foreign Key 관계를 표시합니다.' : '선택 테이블과 직접 연결된 Foreign Key 관계만 표시합니다.'} 빈 영역을 드래그해 이동하고, 상단 −/＋로 확대·축소할 수 있습니다. 이 임시 다이어그램은 DB를 변경하지 않습니다.</div>
  </div>
}
