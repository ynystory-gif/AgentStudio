import type { ReactNode } from 'react'
import { ReportSection } from '../reports/ReportComponents'
import type {
  ArchitectureListItem,
  GeneratedAgentArchitectureReport,
} from '../../types/report'

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
      const label = typeof item === 'string'
        ? item
        : (item.label || item.name || item.component || item.title || item.path || JSON.stringify(item))
      const detail = typeof item === 'string'
        ? ''
        : (item.description || item.purpose || item.reason || item.type || '')
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
      <span>{report?.requirementSpec?.goal || '확정된 요구사항을 기반으로 구성 요소를 시각화합니다.'}</span>
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
