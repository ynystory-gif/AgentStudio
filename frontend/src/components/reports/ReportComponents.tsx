import type { ReactNode } from 'react'
import type { KeyValueItem, WorkflowSummary } from '../../types/report'

export interface MetricCardProps {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode
  tone?: string
  icon?: ReactNode
}

export function MetricCard({ label, value, sub = '', tone = 'default', icon = '◆' }: MetricCardProps) {
  return <div className={`metric-card ${tone}`}>
    <div className="metric-icon">{icon}</div>
    <div className="metric-copy">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  </div>
}

export interface StatusBadgeProps {
  status?: unknown
}

export function StatusBadge({ status = '' }: StatusBadgeProps) {
  const value = String(status || 'UNKNOWN')
  const normalized = value.toUpperCase()
  const tone =
    normalized.includes('COMPLETED') || normalized.includes('PASSED') || normalized.includes('SUCCESS')
      ? 'success'
      : normalized.includes('FAILED') || normalized.includes('ERROR') || normalized.includes('REJECTED')
        ? 'danger'
        : normalized.includes('APPROV') || normalized.includes('WAIT')
          ? 'warning'
          : 'info'

  return <span className={`status-badge ${tone}`}>{value}</span>
}

export interface ReportSectionProps {
  icon?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  children: ReactNode
  className?: string
}

export function ReportSection({ icon = '◆', title, subtitle = '', children, className = '' }: ReportSectionProps) {
  return <section className={`report-section ${className}`}>
    <header>
      <span className="report-section-icon">{icon}</span>
      <div>
        <strong>{title}</strong>
        {subtitle && <small>{subtitle}</small>}
      </div>
    </header>
    <div className="report-section-body">{children}</div>
  </section>
}

export interface KeyValueGridProps {
  items?: KeyValueItem[]
}

export function KeyValueGrid({ items = [] }: KeyValueGridProps) {
  return <div className="kv-grid">
    {items.map((item, index) => <div className="kv-item" key={index}>
      <span>{item.label}</span>
      <strong>{item.value ?? '-'}</strong>
    </div>)}
  </div>
}

export interface FileChangeListProps {
  created?: string[]
  modified?: string[]
}

export function FileChangeList({ created = [], modified = [] }: FileChangeListProps) {
  const rows = [
    ...created.map(path => ({ path, type: 'CREATED' as const })),
    ...modified.map(path => ({ path, type: 'MODIFIED' as const })),
  ]

  if (!rows.length) {
    return <div className="report-empty-mini">생성/수정된 파일 정보가 아직 없습니다.</div>
  }

  return <div className="file-change-list">
    {rows.map((row, index) => <div className="file-change-row" key={`${row.path}-${index}`}>
      <span className={`file-change-type ${row.type.toLowerCase()}`}>{row.type}</span>
      <code>{row.path}</code>
    </div>)}
  </div>
}

export interface WorkflowMiniMapProps {
  workflow?: WorkflowSummary | null
}

export function WorkflowMiniMap({ workflow }: WorkflowMiniMapProps) {
  const steps = workflow?.steps || []
  if (!steps.length) {
    return <div className="report-empty-mini">대상 Agent Workflow 정보가 없습니다.</div>
  }

  return <div className="workflow-mini-map">
    {steps.map((step, index) => {
      const label = typeof step === 'string'
        ? step
        : (step.label || step.name || step.title || `Step ${index + 1}`)
      return <div className="workflow-mini-step" key={index}>
        <span>{String(index + 1).padStart(2, '0')}</span>
        <strong>{label}</strong>
        {index < steps.length - 1 && <b>→</b>}
      </div>
    })}
  </div>
}
