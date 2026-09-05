import {
  KeyValueGrid,
  MetricCard,
  ReportSection,
  StatusBadge,
} from '../reports/ReportComponents'
import type {
  LlmCatalogData,
  LlmHistoryData,
  LlmHistoryItem,
  LlmRouteItem,
} from '../../types/report'

interface LlmRouteCardProps {
  item: LlmRouteItem
  index: number
}

function LlmRouteCard({ item, index }: LlmRouteCardProps) {
  const request = item.request || {}
  return <details className="llm-route-card" open={false}>
    <summary>
      <div>
        <strong>{item.label || item.task || `LLM Route ${index + 1}`}</strong>
        <small>{item.task || ''}</small>
      </div>
      <div className="llm-route-summary">
        <span>{item.group || '-'}</span>
        <b>{item.provider || '-'} · {item.model || '-'}</b>
      </div>
    </summary>

    <div className="llm-route-body">
      <KeyValueGrid items={[
        { label: 'Provider', value: item.provider || '-' },
        { label: 'Model', value: item.model || '-' },
        { label: 'Method', value: request.method || 'POST' },
        { label: 'Endpoint', value: request.endpoint || '-' },
      ]} />

      <div className="llm-request-code-block">
        <div>
          <strong>Headers</strong>
          <pre>{JSON.stringify(request.headers || {}, null, 2)}</pre>
        </div>
        <div>
          <strong>JSON Body 예시</strong>
          <pre>{JSON.stringify(request.body || {}, null, 2)}</pre>
        </div>
      </div>

      {Array.isArray(item.notes) && item.notes.length > 0 && <div className="llm-route-notes">
        {item.notes.map((note: LegacyValue, noteIndex: LegacyValue) => <span key={noteIndex}>{note}</span>)}
      </div>}
    </div>
  </details>
}

interface LlmHistoryCardProps {
  item: LlmHistoryItem
  index: number
}

function LlmHistoryCard({ item, index }: LlmHistoryCardProps) {
  const usage = item.usage || {}
  const success = String(item.status || '').toLowerCase() === 'success'
  const timestamp = item.timestamp
    ? new Date(item.timestamp).toLocaleString('ko-KR')
    : '-'
  const tokens = Number(usage.total_tokens || 0).toLocaleString('ko-KR')
  const cost = Number(usage.cost_usd || 0)

  return <details className={`llm-history-card ${success ? 'success' : 'error'}`} open={index === 0}>
    <summary>
      <div className="llm-history-title">
        <span className={`llm-history-status ${success ? 'success' : 'error'}`}>{success ? 'SUCCESS' : 'ERROR'}</span>
        <div>
          <strong>{item.task || 'LLM 호출'}</strong>
          <small>{timestamp} · {item.operation || 'operation 미지정'}</small>
        </div>
      </div>
      <div className="llm-route-summary">
        <span>{tokens} tokens · {Number(item.elapsed_ms || 0).toLocaleString('ko-KR')} ms</span>
        <b>{item.provider || '-'} · {item.model || '-'}{cost > 0 ? ` · $${cost.toFixed(cost < 0.01 ? 6 : 4)}` : ''}</b>
      </div>
    </summary>

    <div className="llm-route-body">
      <KeyValueGrid items={[
        { label: '호출 ID', value: item.id || '-' },
        { label: 'Project', value: item.project_root || '-' },
        { label: 'Thread', value: item.thread_id || '-' },
        { label: 'Operation', value: item.operation || '-' },
        { label: 'Provider', value: item.provider || '-' },
        { label: 'Model', value: item.model || '-' },
        { label: 'Input Tokens', value: Number(usage.input_tokens || 0).toLocaleString('ko-KR') },
        { label: 'Output Tokens', value: Number(usage.output_tokens || 0).toLocaleString('ko-KR') },
      ]} />

      <div className="llm-history-payload-grid">
        <div className="llm-history-payload request">
          <strong>실제 요청</strong>
          <small>LangChain 호출 직전 입력 · Secret 자동 마스킹</small>
          <pre>{JSON.stringify(item.request || {}, null, 2)}</pre>
        </div>
        <div className={`llm-history-payload ${success ? 'response' : 'error'}`}>
          <strong>{success ? '실제 응답' : '오류 결과'}</strong>
          <small>{success ? 'LLM 반환 content / metadata / usage' : '실패한 호출의 예외 정보'}</small>
          <pre>{JSON.stringify(success ? (item.response || {}) : (item.error || {}), null, 2)}</pre>
        </div>
      </div>
    </div>
  </details>
}

export interface LlmCatalogPanelProps {
  catalog?: LlmCatalogData | null
  history?: LlmHistoryData | null
  loading?: boolean
  error?: string
  onRefresh?: () => void
}

export function LlmCatalogPanel({
  catalog,
  history,
  loading = false,
  error = '',
  onRefresh,
}: LlmCatalogPanelProps) {
  const items = Array.isArray(catalog?.items) ? catalog.items : []
  const defaults = catalog?.defaults || {}
  const historyItems = Array.isArray(history?.items) ? history.items : []
  const successCount = historyItems.filter((item: LegacyValue) => String(item.status || '').toLowerCase() === 'success').length
  const errorCount = historyItems.length - successCount

  return <div className="analysis-report-dashboard llm-catalog-dashboard">
    <div className="dashboard-hero report llm-hero">
      <div>
        <span className="dashboard-eyebrow">LLM REQUEST / RESPONSE HISTORY</span>
        <h2>LLM 리스트</h2>
        <p>실제 LLM 요청과 응답을 최근 10일 동안 보관하고, 작업별 라우팅/요청 형식도 함께 확인합니다.</p>
      </div>
      <div className="report-hero-actions">
        <button type="button" onClick={onRefresh} disabled={loading}>{loading ? '조회 중...' : '↻ LLM 기록 새로고침'}</button>
        <StatusBadge status={loading ? 'LOADING' : historyItems.length ? 'READY' : 'EMPTY'} />
      </div>
    </div>

    <div className="metric-grid report-metrics">
      <MetricCard label="최근 10일 호출" value={`${Number(history?.total_count ?? historyItems.length).toLocaleString('ko-KR')}개`} sub={`화면 ${historyItems.length}개 · 성공 ${successCount} · 실패 ${errorCount}`} icon="◷" tone="info" />
      <MetricCard label="보관 기간" value={`${history?.retention_days || 10}일`} sub="기간 경과 시 자동 삭제" icon="▣" tone="default" />
      <MetricCard label="요구사항 모델" value={defaults.openai_model || '-'} sub={defaults.requirements_llm_provider || '-'} icon="✦" tone="success" />
      <MetricCard label="로컬 모델" value={defaults.ollama_model || '-'} sub={defaults.ollama_base_url || '-'} icon="◎" tone="warning" />
    </div>

    <div className="report-layout llm-catalog-layout">
      <ReportSection icon="↔" title="실제 LLM 요청 / 응답 기록" subtitle={`최근 ${history?.retention_days || 10}일 · 최신순`} className="span-2">
        {error && <div className="report-empty-mini">{error}</div>}
        {!error && !historyItems.length && !loading && <div className="report-empty-mini">
          아직 저장된 실제 LLM 호출이 없습니다. v5.243 이후 실행되는 LLM 요청부터 이곳에 요청과 결과가 함께 저장됩니다.
        </div>}
        <div className="llm-history-list">
          {historyItems.map((item: LegacyValue, index: LegacyValue) => <LlmHistoryCard key={item.id || `${String(item.timestamp)}-${index}`} item={item} index={index} />)}
        </div>
        {history?.truncated && <div className="report-empty-mini">최근 기록이 많아 최신 {historyItems.length}개를 화면에 표시하고 있습니다. 전체 기록은 보관 파일에 유지됩니다.</div>}
        {history?.log_path && <div className="llm-history-storage-note">
          <span>저장 위치</span><code>{history.log_path}</code>
          <small>API Key, Password, Secret, Bearer Token 패턴은 저장 전에 마스킹합니다.</small>
        </div>}
      </ReportSection>

      <ReportSection icon="⚙" title="라우팅 기본값" subtitle="현재 설정된 Provider / Model">
        <KeyValueGrid items={[
          { label: 'Default LLM Provider', value: defaults.llm_provider || '-' },
          { label: 'Local LLM Provider', value: defaults.local_llm_provider || '-' },
          { label: 'Requirements Provider', value: defaults.requirements_llm_provider || '-' },
          { label: 'Coding Provider', value: defaults.coding_llm_provider || '-' },
          { label: 'OpenAI Model', value: defaults.openai_model || '-' },
          { label: 'Ollama Model', value: defaults.ollama_model || '-' },
        ]} />
      </ReportSection>

      <ReportSection icon="ℹ" title="기록 정책" subtitle="실제 요청/응답 보관 기준">
        <div className="llm-catalog-info">
          <p>성공 호출은 요청, 응답, 토큰, 비용, 실행시간을 하나의 기록으로 저장합니다.</p>
          <p>실패 호출도 요청과 오류 결과를 저장하여 디버깅에 사용할 수 있습니다.</p>
          <p>10일보다 오래된 기록은 조회/새 기록 저장 시 자동 정리됩니다.</p>
        </div>
      </ReportSection>

      <ReportSection icon="⎔" title="LLM 요청 형식 / 라우팅 목록" subtitle="참고용 Task → Provider → JSON Body 예시" className="span-2">
        {!items.length && !loading && <div className="report-empty-mini">표시할 LLM 라우팅 정보가 없습니다.</div>}
        <div className="llm-route-list">
          {items.map((item: LegacyValue, index: LegacyValue) => <LlmRouteCard key={`${item.task}-${index}`} item={item} index={index} />)}
        </div>
      </ReportSection>
    </div>
  </div>
}
