import type { ReactNode } from 'react'
import { ReportSection } from '../reports/ReportComponents'
import type {
  ArchitectureListItem,
  GeneratedAgentArchitectureReport,
} from '../../types/report'

function safeArchitectureText(value: unknown, fallback = ''): string {
  const text = String(value ?? '').replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim()
  if (!text) return fallback
  const lower = text.toLowerCase()
  const rawStateMarkers = [
    'original_request',
    'user_answers',
    'confirmed_requirements',
    'latest_analysis',
    'attachment_summary',
    'assistant:',
    'user:',
  ]
  if (rawStateMarkers.some(marker => lower.includes(marker)) || (text.match(/[{}\[\]]/g)?.length || 0) > 10) {
    return fallback
  }
  return text.length > 220 ? `${text.slice(0, 220)}…` : text
}

function normalizeArchitectureList(
  value: ArchitectureListItem | ArchitectureListItem[] | null | undefined,
): ArchitectureListItem[] {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (value === null || value === undefined || value === '') return []
  return [value]
}

interface ArchitectureListProps {
  items?: ArchitectureListItem | ArchitectureListItem[] | null
  empty?: string
}

function ArchitectureList({ items = [], empty = '정보가 없습니다.' }: ArchitectureListProps) {
  const rows = normalizeArchitectureList(items)
  if (!rows.length) return <div className="report-empty-mini">{empty}</div>
  return <div className="architecture-chip-list">
    {rows.map((item, index) => {
      const rawLabel = typeof item === 'string'
        ? item
        : (item.label || item.name || item.component || item.title || item.path || '')
      const rawDetail = typeof item === 'string'
        ? ''
        : (item.description || item.purpose || item.reason || item.type || '')
      const label = safeArchitectureText(rawLabel, `구조 항목 ${index + 1}`)
      const detail = safeArchitectureText(rawDetail)
      return <div className="architecture-chip-card" key={index}>
        <strong>{label}</strong>
        {detail && <small>{detail}</small>}
      </div>
    })}
  </div>
}

interface ArchitectureNodeProps {
  title: ReactNode
  subtitle?: ReactNode
  tone?: string
}

function ArchitectureNode({ title, subtitle = '', tone = 'default' }: ArchitectureNodeProps) {
  return <div className={`architecture-node ${tone}`}>
    <strong>{title}</strong>
    {subtitle && <small>{subtitle}</small>}
  </div>
}

interface ArchitectureArrowProps {
  label?: ReactNode
}

function ArchitectureArrow({ label = '' }: ArchitectureArrowProps) {
  return <div className="architecture-arrow">
    <span />
    <b>→</b>
    <span />
    {label && <small>{label}</small>}
  </div>
}

export interface GeneratedAgentArchitecturePanelProps {
  report?: GeneratedAgentArchitectureReport | null
}

export function GeneratedAgentArchitecturePanel({ report }: GeneratedAgentArchitecturePanelProps) {
  const architecture = report?.architecture || {}
  const components = normalizeArchitectureList(architecture.components)
  const interfaces = normalizeArchitectureList(architecture.interfaces)
  const persistence = normalizeArchitectureList(architecture.persistence)
  const security = normalizeArchitectureList(architecture.security)
  const stateRows = normalizeArchitectureList(architecture.state)
  const componentTitles = components.slice(0, 4).map((item, index) => typeof item === 'string'
    ? item
    : (item.label || item.name || item.component || `구성요소 ${index + 1}`))
  const centerTitle = componentTitles[0] || 'AI Agent Core'
  const rightTitle = componentTitles[1] || 'Action / Tool Executor'
  const leftTitle = componentTitles[2] || 'User Input / Interface'
  const memoryTitle = componentTitles[3] || 'Memory / State'

  return <div className="architecture-panel">
    <div className="architecture-panel-head">
      <div>
        <small>TARGET AGENT ARCHITECTURE</small>
        <strong>신규 에이전트 아키텍처</strong>
      </div>
      <span>{safeArchitectureText(report?.requirementSpec?.goal, '확정된 요구사항을 기반으로 구성 요소를 시각화합니다.')}</span>
    </div>

    <div className="architecture-canvas generated-agent">
      <div className="architecture-top-stack">
        <ArchitectureNode title="User / Client" subtitle="요청 · 입력 · 승인" tone="soft" />
        <div className="architecture-vertical-arrow">↓</div>
        <ArchitectureNode title={leftTitle} subtitle="입력 채널 / 외부 인터페이스" tone="blue" />
      </div>

      <div className="architecture-stage-board">
        <div className="architecture-stage-row">
          <ArchitectureNode title={leftTitle} subtitle="Perception / Input" tone="soft" />
          <ArchitectureArrow label="context" />
          <ArchitectureNode title={centerTitle} subtitle="Planning / LLM / Cognition" tone="accent" />
          <ArchitectureArrow label="execute" />
          <ArchitectureNode title={rightTitle} subtitle="Action / Tool / MCP" tone="purple" />
        </div>

        <div className="architecture-feedback-loop">
          <div className="architecture-feedback-bubble">
            <strong>State / Feedback Loop</strong>
            <small>{stateRows.length ? `${stateRows.length}개 상태 항목` : '실행 상태와 결과를 다시 Agent로 피드백'}</small>
          </div>
        </div>

        <div className="architecture-side-band">
          <ArchitectureNode title={memoryTitle} subtitle="Memory / Persistence" tone="soft" />
          <ArchitectureNode title="Policy / Security" subtitle={security.length ? `${security.length}개 보안 규칙` : '권한 · Secret · Guardrail'} tone="soft" />
        </div>
      </div>
    </div>

    <div className="architecture-detail-grid">
      <ReportSection icon="⬢" title="구성 요소" subtitle="Components">
        <ArchitectureList items={components} />
      </ReportSection>
      <ReportSection icon="⇄" title="인터페이스" subtitle="Interfaces">
        <ArchitectureList items={interfaces} />
      </ReportSection>
      <ReportSection icon="💾" title="영속성" subtitle="Persistence">
        <ArchitectureList items={persistence} />
      </ReportSection>
      <ReportSection icon="🔐" title="보안" subtitle="Security">
        <ArchitectureList items={security} />
      </ReportSection>
    </div>
  </div>
}

export function AgentStudioArchitecturePanel() {
  return <div className="architecture-panel">
    <div className="architecture-panel-head">
      <div>
        <small>THEANOVA AGENTSTUDIO PLATFORM</small>
        <strong>에이전트 스튜디오 아키텍처</strong>
      </div>
      <span>React UI · FastAPI Backend · Agent Orchestrator · MCP / Tool / DB / LLM 구조</span>
    </div>

    <div className="architecture-canvas agentstudio-platform">
      <div className="architecture-top-stack studio">
        <ArchitectureNode title="User" subtitle="요구사항 · 코드 수정 · 실행" tone="soft" />
        <div className="architecture-vertical-arrow">↕</div>
        <ArchitectureNode title="THEANOVA AgentStudio" subtitle="React Workspace" tone="blue" />
      </div>

      <div className="architecture-stage-board studio-board">
        <div className="architecture-stage-row studio-main-row">
          <ArchitectureNode title="Frontend UI" subtitle="Workspace / Report / Notebook / SQL" tone="soft" />
          <ArchitectureArrow />
          <ArchitectureNode title="FastAPI Backend" subtitle="API / Jobs / Runtime" tone="accent" />
          <ArchitectureArrow />
          <ArchitectureNode title="Agent Orchestrator" subtitle="Workflow / Planning / Recovery" tone="purple" />
        </div>

        <div className="architecture-matrix-grid">
          <div className="architecture-mini-group">
            <strong>LLM Layer</strong>
            <div>
              <span>OpenAI</span>
              <span>Ollama</span>
              <span>LangChain / LangGraph</span>
            </div>
          </div>
          <div className="architecture-mini-group">
            <strong>Execution Layer</strong>
            <div>
              <span>MCP Server / Client</span>
              <span>Local Tools</span>
              <span>Python / Terminal / SQL</span>
            </div>
          </div>
          <div className="architecture-mini-group">
            <strong>Persistence</strong>
            <div>
              <span>PostgreSQL</span>
              <span>MSSQL / Oracle / SQLite</span>
              <span>Project State / Reports</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div className="architecture-detail-grid two-column">
      <ReportSection icon="◈" title="주요 계층" subtitle="Core Layers">
        <ArchitectureList items={[
          'Frontend UI (React)',
          'Backend API (FastAPI)',
          'Agent Orchestrator / Workflow Engine',
          'LLM Routing / MCP / Local Tool Execution',
          'Project State / Report / Usage Tracking',
        ]} />
      </ReportSection>
      <ReportSection icon="☰" title="핵심 역할" subtitle="Responsibilities">
        <ArchitectureList items={[
          '요구사항 수집 → 설계 → 코드 생성 → 실행 → 테스트 → 복구',
          'MCP / Tool 분석 및 Registry 등록',
          '프로젝트 파일, Notebook, SQL Workspace 통합 관리',
          'LLM 사용량 / 비용 / 분석 리포트 시각화',
          '다중 DB 연결 프로필과 로컬 런타임 운영',
        ]} />
      </ReportSection>
    </div>
  </div>
}


export function AsBuiltAgentArchitecturePanel({ report }: GeneratedAgentArchitecturePanelProps) {
  const architecture = report?.asBuiltArchitecture || {}
  const components = normalizeArchitectureList(architecture.components)
  const interfaces = normalizeArchitectureList(architecture.interfaces)
  const persistence = normalizeArchitectureList(architecture.persistence)
  const security = normalizeArchitectureList(architecture.security)
  const stateRows = normalizeArchitectureList(architecture.state)
  const provider = architecture.analysis_provider || 'deterministic'
  const sourceFiles = Number(architecture.scan?.source_file_count || 0)

  return <div className="architecture-panel as-built-architecture-panel">
    <div className="architecture-panel-head">
      <div>
        <small>AS-BUILT ARCHITECTURE</small>
        <strong>실제 생성 Agent 아키텍처</strong>
      </div>
      <span>생성된 프로젝트 파일 {sourceFiles}개를 실제 증거로 재분석 · {provider}</span>
    </div>

    <div className="architecture-canvas generated-agent as-built">
      <div className="architecture-stage-board">
        <div className="architecture-stage-row">
          <ArchitectureNode title="Generated Source" subtitle={`${sourceFiles} source files`} tone="soft" />
          <ArchitectureArrow label="static scan" />
          <ArchitectureNode title="As-Built Analyzer" subtitle="파일 · 클래스 · 함수 · Framework 증거" tone="accent" />
          <ArchitectureArrow label="evidence" />
          <ArchitectureNode title={`${components.length} Components`} subtitle="실제 구현 구조" tone="purple" />
        </div>
        <div className="architecture-side-band">
          <ArchitectureNode title={`${stateRows.length} State`} subtitle="LangGraph / Runtime State" tone="soft" />
          <ArchitectureNode title={`${interfaces.length} Interfaces`} subtitle="API / UI / MCP / Realtime" tone="soft" />
        </div>
      </div>
    </div>

    <div className="architecture-detail-grid">
      <ReportSection icon="⬢" title="실제 구성 요소" subtitle="Implemented Components">
        <ArchitectureList items={components} empty="아직 실제 구현 증거가 없습니다." />
      </ReportSection>
      <ReportSection icon="⇄" title="실제 인터페이스" subtitle="Detected Interfaces">
        <ArchitectureList items={interfaces} />
      </ReportSection>
      <ReportSection icon="💾" title="실제 영속성" subtitle="Detected Persistence">
        <ArchitectureList items={persistence} />
      </ReportSection>
      <ReportSection icon="🔐" title="실제 보안 / 상태" subtitle="Security & State">
        <ArchitectureList items={[...security, ...stateRows]} />
      </ReportSection>
    </div>
  </div>
}

export function ArchitectureConformancePanel({ report }: GeneratedAgentArchitecturePanelProps) {
  const conformance = report?.architectureConformance || {}
  const mismatches = conformance.mismatches || []
  const score = Number(conformance.score ?? 0)
  const passed = Boolean(conformance.ok)

  return <div className="architecture-panel architecture-conformance-panel">
    <div className="architecture-panel-head">
      <div>
        <small>DESIGN ↔ AS-BUILT CONFORMANCE GATE</small>
        <strong>설계 / 실제 아키텍처 일치 검증</strong>
      </div>
      <span>기준 {Number(conformance.threshold ?? 85)}점 · 자동 보정 {Number(conformance.repair_iteration ?? 0)}/2회</span>
    </div>

    <div className={`architecture-conformance-score ${passed ? 'pass' : 'fail'}`}>
      <div>
        <strong>{score.toFixed(1)}</strong>
        <span>/ 100</span>
      </div>
      <div>
        <b>{passed ? 'PASS · 설계와 실제 구현이 일치합니다.' : 'CHECK · 설계와 실제 구현 차이가 있습니다.'}</b>
        <small>분석 Provider: {conformance.analysis_provider || '정적 분석'}</small>
      </div>
      <div className="architecture-conformance-counts">
        <span>Critical <b>{Number(conformance.critical_count || 0)}</b></span>
        <span>Warning <b>{Number(conformance.warning_count || 0)}</b></span>
      </div>
    </div>

    <ReportSection icon="≠" title="설계와 실제 차이" subtitle="Mismatches">
      {!mismatches.length
        ? <div className="report-empty-mini">차이가 없습니다. Design Architecture 계약을 충족했습니다.</div>
        : <div className="architecture-mismatch-list">
          {mismatches.map((item, index) => <div className={`architecture-mismatch-row ${item.severity || 'warning'}`} key={`${item.type || 'mismatch'}-${index}`}>
            <span>{item.severity === 'critical' ? '●' : '△'}</span>
            <div>
              <strong>{item.expected || item.path || item.category || item.type || 'Architecture mismatch'}</strong>
              <small>{item.type || 'mismatch'} · {item.severity || 'warning'}</small>
            </div>
          </div>)}
        </div>}
    </ReportSection>
  </div>
}
