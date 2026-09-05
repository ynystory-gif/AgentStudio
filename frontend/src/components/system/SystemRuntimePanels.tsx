import type { ChangeEvent, ReactNode } from 'react'
import { StatusDot } from '../common/CommonUi'
import type {
  DatabaseRuntimeInfo,
  GpuRuntimeInfo,
  DatabaseRuntimeResult,
  OllamaRuntimeInfo,
  PortRecommendationInfo,
  RuntimeDatabaseProvider,
  SystemJobState,
  SystemSettingScalar,
  SystemStatus,
} from '../../types/system'

interface ServicePortSettingsPanelProps {
  busy: boolean
  portCheckBusy: boolean
  portInfo: PortRecommendationInfo | null
  runtimeApiBase: string
  frontendOrigin: string
  valueOf: (key: string) => SystemSettingScalar | Record<string, unknown>
  setValue: (key: string, value: string) => void
  portStateLabel: (state?: string) => string
  onCheckRecommendations: () => void
  onApplyRecommendations: () => void
  onSave: () => void
}

export function ServicePortSettingsPanel({
  busy,
  portCheckBusy,
  portInfo,
  runtimeApiBase,
  frontendOrigin,
  valueOf,
  setValue,
  portStateLabel,
  onCheckRecommendations,
  onApplyRecommendations,
  onSave,
}: ServicePortSettingsPanelProps) {
  return (
    <section className="settings-panel settings-panel-wide service-port-settings">
      <h2>서비스 포트 설정</h2>
      <div className="hint-box">
        PC마다 이미 사용 중인 포트가 다를 수 있습니다. 프로젝트 루트 .env의 Backend/Frontend 포트를 기준으로 사용하며,
        저장한 값은 다음 SYSTEM_ADMIN.cmd 실행부터 적용됩니다. 다른 프로그램이 사용 중인 포트는 강제로 종료하지 않습니다.
      </div>
      <div className="two-col-fields">
        <label className="setting-field">
          <span>Backend API 포트</span>
          <input
            type="number" min="1024" max="65535"
            value={String(valueOf('AGENTSTUDIO_BACKEND_PORT') || window.__AGENTSTUDIO_CONFIG__?.BACKEND_PORT || '')}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setValue('AGENTSTUDIO_BACKEND_PORT', event.target.value)}
          />
          <small>현재 실행: {runtimeApiBase}</small>
          {portInfo?.backend && <small className={`port-state ${portInfo.backend.state || ''}`}>
            상태: {portStateLabel(portInfo.backend.state)} · 추천: {portInfo.backend.recommended}
          </small>}
        </label>
        <label className="setting-field">
          <span>Frontend 포트</span>
          <input
            type="number" min="1024" max="65535"
            value={String(valueOf('AGENTSTUDIO_FRONTEND_PORT') || window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT || '')}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setValue('AGENTSTUDIO_FRONTEND_PORT', event.target.value)}
          />
          <small>현재 실행: {frontendOrigin}</small>
          {portInfo?.frontend && <small className={`port-state ${portInfo.frontend.state || ''}`}>
            상태: {portStateLabel(portInfo.frontend.state)} · 추천: {portInfo.frontend.recommended}
          </small>}
        </label>
      </div>
      {portInfo && <div className="port-recommendation-box">
        <div><b>추천 Backend:</b> {portInfo.backend?.recommended} {Boolean(portInfo.backend?.suggestions?.length) && ` · 후보 ${portInfo.backend?.suggestions?.join(', ')}`}</div>
        <div><b>추천 Frontend:</b> {portInfo.frontend?.recommended} {Boolean(portInfo.frontend?.suggestions?.length) && ` · 후보 ${portInfo.frontend?.suggestions?.join(', ')}`}</div>
        <small>{portInfo.note}</small>
      </div>}
      <div className="panel-actions">
        <button disabled={busy || portCheckBusy} onClick={onCheckRecommendations}>
          {portCheckBusy ? '포트 확인 중...' : '포트 사용 여부 / 추천 확인'}
        </button>
        <button disabled={busy || !portInfo} onClick={onApplyRecommendations}>추천 포트 적용</button>
        <button disabled={busy || portCheckBusy} onClick={onSave}>포트 설정 저장</button>
      </div>
    </section>
  )
}

interface RuntimeDatabasePanelProps {
  providerChoice: RuntimeDatabaseProvider
  runtime: DatabaseRuntimeInfo | null
  result: DatabaseRuntimeResult | null
  supabaseRuntimeUrl: string
  supabaseLanggraphRuntimeUrl: string
  supabaseRuntimeSchema: string
  runtimeBusy: boolean
  infoSaveBusy: boolean
  onProviderChoice: (provider: RuntimeDatabaseProvider) => void
  onSupabaseRuntimeUrl: (value: string) => void
  onSupabaseLanggraphRuntimeUrl: (value: string) => void
  onSupabaseRuntimeSchema: (value: string) => void
  onSaveSupabaseInfo: () => void
  onInitializeSupabaseSchema: () => void
  onDownloadSupabaseSchema: () => void
  onActivateRuntimeDatabase: () => void
}

export function RuntimeDatabasePanel({
  providerChoice,
  runtime,
  result,
  supabaseRuntimeUrl,
  supabaseLanggraphRuntimeUrl,
  supabaseRuntimeSchema,
  runtimeBusy,
  infoSaveBusy,
  onProviderChoice,
  onSupabaseRuntimeUrl,
  onSupabaseLanggraphRuntimeUrl,
  onSupabaseRuntimeSchema,
  onSaveSupabaseInfo,
  onInitializeSupabaseSchema,
  onDownloadSupabaseSchema,
  onActivateRuntimeDatabase,
}: RuntimeDatabasePanelProps) {
  const schemaResult = result?.schema
  const verificationOk = schemaResult?.verification?.ok === true || result?.verification?.ok === true
  const vectorResult = schemaResult?.vector || result?.vector
  const langgraphMigrationCount = schemaResult?.langgraph?.migration_count ?? result?.langgraph?.migration_count
  const rolledBack = schemaResult?.rolled_back === true || result?.rolled_back === true

  return (
    <div className="database-runtime-switch-box">
      <h3>AgentStudio Runtime DB 선택</h3>
      <div className="hint-box">
        기본은 <b>기존 로컬 PostgreSQL</b>입니다. Supabase PostgreSQL을 선택하면 먼저 로컬 PostgreSQL의
        <b> app_settings</b>에 선택 상태를 기록한 뒤 AgentStudio runtime DB와 LangGraph Checkpointer를 Supabase로 전환합니다.
        Supabase 비밀번호가 포함된 URL은 로컬 DB에 저장하지 않고 <b>backend/.env</b>에만 저장합니다.
      </div>
      <div className="database-provider-choice">
        <label className={providerChoice === 'local' ? 'active' : ''}>
          <input type="radio" name="agentstudio-db-provider" value="local" checked={providerChoice === 'local'} onChange={() => onProviderChoice('local')}/>
          <span><b>로컬 PostgreSQL</b><small>기본 / Control DB</small></span>
        </label>
        <label className={providerChoice === 'supabase' ? 'active' : ''}>
          <input type="radio" name="agentstudio-db-provider" value="supabase" checked={providerChoice === 'supabase'} onChange={() => onProviderChoice('supabase')}/>
          <span><b>Supabase PostgreSQL</b><small>선택 사용</small></span>
        </label>
      </div>
      <div className="database-runtime-summary">
        <div><b>현재 사용:</b> {runtime?.active_provider === 'supabase' ? 'Supabase PostgreSQL' : '로컬 PostgreSQL'}</div>
        <div><b>로컬 DB:</b> {runtime?.local_target || '-'}</div>
        <div><b>Supabase:</b> {runtime?.supabase_target || '아직 설정되지 않음'}</div>
        <div><b>Supabase 연결 정보:</b> {runtime?.supabase_configured ? '저장됨 (backend/.env)' : '미저장'}</div>
        <div><b>Supabase Schema:</b> {runtime?.supabase_schema || supabaseRuntimeSchema || 'theanova_agentstudio'}</div>
        {runtime?.last_error && <div className="runtime-db-warning">{runtime.last_error}</div>}
      </div>
      {providerChoice === 'supabase' && <>
        <label className="setting-field">
          <span>Supabase DATABASE URL</span>
          <input value={supabaseRuntimeUrl} onChange={(event: ChangeEvent<HTMLInputElement>) => onSupabaseRuntimeUrl(event.target.value)} placeholder={runtime?.supabase_configured ? '저장된 Supabase URL 사용 가능 · 변경할 때만 입력' : 'postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres'}/>
        </label>
        <label className="setting-field">
          <span>Supabase LangGraph DB URL</span>
          <input value={supabaseLanggraphRuntimeUrl} onChange={(event: ChangeEvent<HTMLInputElement>) => onSupabaseLanggraphRuntimeUrl(event.target.value)} placeholder={runtime?.supabase_configured ? '비우면 저장된 값 또는 DATABASE URL 기준 자동 사용' : 'postgresql://USER:PASSWORD@HOST:5432/postgres'}/>
        </label>
        <label className="setting-field">
          <span>Supabase AgentStudio Schema</span>
          <input value={supabaseRuntimeSchema} onChange={(event: ChangeEvent<HTMLInputElement>) => onSupabaseRuntimeSchema(event.target.value)} placeholder="theanova_agentstudio"/>
        </label>
        <div className="hint-box">
          <b>Supabase 정보 저장</b>을 누르면 DATABASE URL, 선택적 LangGraph URL, Schema를 <b>backend/.env</b>에만 보관합니다. 저장 후 URL 입력칸은 비워도 이후 검증/적용에서 저장된 값을 자동 사용합니다.
          최초/업그레이드 모두 <b>Supabase 스키마 준비/검증</b>을 사용할 수 있습니다. 기본 사용자 스키마는 <b>theanova_agentstudio</b>이며 AgentStudio ORM과 LangGraph Checkpointer 테이블을 public과 분리합니다. pgvector는 <b>extensions</b> 스키마를 사용합니다. LangGraph 테이블은 설치된 Checkpointer의 공식 setup()으로 migration한 뒤 같은 사용자 스키마에서 필수 구조를 재검증합니다.
          <b> Supabase 사용 적용</b>은 모든 검증이 성공한 경우에만 전환하며 실패하면 로컬 PostgreSQL을 유지합니다.
        </div>
      </>}
      <div className="panel-actions database-runtime-actions">
        {providerChoice === 'supabase' && <button disabled={runtimeBusy || infoSaveBusy} onClick={onSaveSupabaseInfo}>{infoSaveBusy ? 'Supabase 정보 저장 중...' : 'Supabase 정보 저장'}</button>}
        {providerChoice === 'supabase' && <button disabled={runtimeBusy || infoSaveBusy} onClick={onInitializeSupabaseSchema}>Supabase 스키마 준비/검증</button>}
        {providerChoice === 'supabase' && <button disabled={runtimeBusy || infoSaveBusy} onClick={onDownloadSupabaseSchema}>Supabase 스키마 SQL 다운로드</button>}
        <button className="primary-install" disabled={runtimeBusy || infoSaveBusy} onClick={onActivateRuntimeDatabase}>
          {runtimeBusy ? 'DB 전환 중...' : providerChoice === 'supabase' ? 'Supabase PostgreSQL 사용 적용' : '로컬 PostgreSQL 사용 적용'}
        </button>
      </div>
      {result && <div className={result.ok === false ? 'test-result badbox' : 'test-result okbox'}>
        <div>{result.message || '-'}</div>
        {result.target && <div>대상: {result.target}</div>}
        {(result.supabase_schema || schemaResult?.schema) && <div>Schema: {result.supabase_schema || schemaResult?.schema}</div>}
        {result.local_settings_updated && <div>로컬 DB 설정 업데이트: 완료</div>}
        {schemaResult?.agentstudio_table_count !== undefined && <div>AgentStudio 테이블 확인: {schemaResult.agentstudio_table_count}개</div>}
        {verificationOk && <div>테이블/컬럼/PK/UNIQUE/INDEX/FK 재검증: 정상</div>}
        {vectorResult && <div>pgvector: {vectorResult === 'already_installed' ? '이미 설치됨' : '설치/확인 완료'}</div>}
        {langgraphMigrationCount !== undefined && <div>LangGraph migration 기록: {langgraphMigrationCount}개</div>}
        {rolledBack && <div>실패 단계 변경사항: rollback 완료</div>}
        {result.langgraph_ok === false && result.langgraph_error && <details><summary>LangGraph 확인 필요</summary><pre>{result.langgraph_error}</pre></details>}
        {schemaResult?.langgraph?.ok === false && <details><summary>LangGraph migration/검증 실패</summary><pre>{schemaResult.langgraph.message || '-'}</pre></details>}
      </div>}
    </div>
  )
}

interface GpuSettingsPanelProps {
  busy: boolean
  runtime: GpuRuntimeInfo | null
  onStart: () => void
  onStop: () => void
  onRefresh: () => void
}

export function GpuSettingsPanel({ busy, runtime, onStart, onStop, onRefresh }: GpuSettingsPanelProps) {
  const device = runtime?.devices?.[0]
  return (
    <section className="settings-panel gpu-runtime-panel">
      <h2>GPU 가속</h2>
      <div className="hint-box">
        <b>GPU 시작/정지</b>는 그래픽카드 전원을 켜고 끄는 기능이 아닙니다. AgentStudio가 관리하는 Ollama, 로컬 Embedding,
        생성 Agent 테스트에서 GPU 가속을 사용할지 제어합니다. GPU 정지 시 가능한 작업은 CPU 모드로 실행됩니다.
      </div>
      {runtime && <div className={`ollama-runtime-card ${runtime.enabled ? 'running' : runtime.available ? 'stopped' : 'missing'}`}>
        <div className="ollama-runtime-head">
          <strong>GPU Runtime</strong>
          <span>{runtime.enabled ? '● GPU 가속 사용' : runtime.available ? '○ GPU 가속 정지' : '○ GPU 확인 필요'}</span>
        </div>
        <div><b>감지:</b> {runtime.available ? `${runtime.vendor || 'GPU'} ${runtime.device_count || 1}개` : '지원 GPU를 찾지 못함'}</div>
        {device?.name && <div><b>장치:</b> {device.name}</div>}
        {device?.memory_total_mb !== undefined && <div><b>VRAM:</b> {device.memory_used_mb || 0} / {device.memory_total_mb} MB</div>}
        {device?.utilization_percent !== undefined && <div><b>GPU 사용률:</b> {device.utilization_percent}%</div>}
        {device?.driver_version && <div><b>Driver:</b> {device.driver_version}</div>}
        {runtime.message && <div><b>상태:</b> {runtime.message}</div>}
        {runtime.ollama?.message && <div><b>Ollama:</b> {runtime.ollama.message}</div>}
      </div>}
      <div className="panel-actions">
        <button className="primary-install" disabled={busy || !runtime?.available || runtime?.enabled} onClick={onStart}>
          {busy ? 'GPU 시작 중...' : 'GPU 시작'}
        </button>
        <button disabled={busy || !runtime?.available || !runtime?.enabled} onClick={onStop}>GPU 정지</button>
        <button disabled={busy} onClick={onRefresh}>상태 새로고침</button>
      </div>
    </section>
  )
}

interface OllamaSettingsPanelProps {
  busy: boolean
  runtimeBusy: boolean
  runtime: OllamaRuntimeInfo | null
  install: SystemJobState | null
  valueOf: (key: string) => SystemSettingScalar | Record<string, unknown>
  setValue: (key: string, value: string) => void
  renderField: (label: string, name: string, type?: string, placeholder?: string) => ReactNode
  renderTestResult: (name: string) => ReactNode
  onSave: () => void
  onTest: () => void
  onStart: () => void
  onStop: () => void
  onInstall: () => void
  onRefresh: () => void
}

export function OllamaSettingsPanel({
  busy,
  runtimeBusy,
  runtime,
  install,
  valueOf,
  setValue,
  renderField,
  renderTestResult,
  onSave,
  onTest,
  onStart,
  onStop,
  onInstall,
  onRefresh,
}: OllamaSettingsPanelProps) {
  const logPath = runtime?.log_path
  return (
    <section className="settings-panel">
      <h2>Ollama</h2>
      {renderField('Ollama URL', 'OLLAMA_BASE_URL', 'text', '')}
      {renderField('Ollama 모델', 'OLLAMA_MODEL', 'text', '')}
      {renderField('Embedding 모델', 'OLLAMA_EMBEDDING_MODEL', 'text', '')}
      <label className="setting-checkbox-row">
        <input
          type="checkbox"
          checked={String(valueOf('OLLAMA_AUTO_START')).toLowerCase() !== 'false'}
          onChange={(event: ChangeEvent<HTMLInputElement>) => setValue('OLLAMA_AUTO_START', event.target.checked ? 'true' : 'false')}
        />
        <span>AgentStudio 시작 시 로컬 Ollama 서버 자동 시작</span>
      </label>
      <div className="hint-box">
        Ollama는 별도 Agent가 아니라 AgentStudio가 HTTP Provider로 연결하는 로컬 LLM 서버입니다.
        설치된 Ollama 서버가 중지되어 있으면 아래의 <b>Ollama 실행</b>으로 시작할 수 있습니다.
      </div>

      {runtime && <div className={`ollama-runtime-card ${runtime.running ? 'running' : runtime.installed ? 'stopped' : 'missing'}`}>
        <div className="ollama-runtime-head">
          <strong>Ollama Server</strong>
          <span>{runtime.running ? '● 연결됨' : runtime.installed ? '○ 서버 중지' : '○ 설치 필요'}</span>
        </div>
        <div><b>설치:</b> {runtime.installed ? '설치됨' : '설치되지 않음'}</div>
        {runtime.ollama_exe && <div><b>실행 파일:</b> {runtime.ollama_exe}</div>}
        <div><b>API:</b> {runtime.base_url || String(valueOf('OLLAMA_BASE_URL') || '')}</div>
        {runtime.version && <div><b>버전:</b> {runtime.version}</div>}
        {Boolean(runtime.models?.length) && <div><b>모델:</b> {runtime.models?.join(', ')}</div>}
        {runtime.managed_by_agentstudio && <div><b>관리:</b> AgentStudio가 시작한 서버 · PID {runtime.managed_pid}</div>}
        {!runtime.running && runtime.last_error && <div><b>최근 상태:</b> {runtime.last_error}</div>}
        {logPath && <div className="connection-log-path">
          <b>서버 로그:</b><code>{logPath}</code>
          <button type="button" onClick={() => navigator.clipboard?.writeText?.(logPath)}>경로 복사</button>
        </div>}
      </div>}

      <div className="panel-actions">
        <button disabled={busy} onClick={onSave}>Ollama 설정 저장</button>
        <button disabled={runtimeBusy} onClick={onTest}>Ollama 연결 테스트</button>
        {runtime?.installed && !runtime?.running && runtime?.manageable &&
          <button className="primary-install" disabled={runtimeBusy} onClick={onStart}>
            {runtimeBusy ? 'Ollama 시작 중...' : 'Ollama 실행'}
          </button>}
        {runtime?.running && runtime?.managed_by_agentstudio &&
          <button disabled={runtimeBusy} onClick={onStop}>Ollama 중지</button>}
        {runtime && !runtime.installed && runtime.local && !runtime.running &&
          <button className="primary-install" disabled={busy} onClick={onInstall}>
            {install && ['QUEUED', 'RUNNING'].includes(String(install.status)) ? 'Ollama 설치 중...' : 'Ollama 설치'}
          </button>}
        <button disabled={runtimeBusy} onClick={onRefresh}>상태 새로고침</button>
      </div>
      {renderTestResult('ollama')}
      {install && <div className={
        install.status === 'SUCCESS' ? 'test-result okbox' :
        install.status === 'FAILED' ? 'test-result badbox' :
        'test-result install-running'
      }>
        <div><b>설치 상태:</b> {install.status}</div>
        <progress max="100" value={install.progress || 0}/>
        <div>{install.message}</div>
        {install.result?.ollama_exe && <div>Ollama: {install.result.ollama_exe}</div>}
        {install.result?.models_path && <div>모델 경로: {install.result.models_path}</div>}
      </div>}
    </section>
  )
}

interface SystemStatusSummaryProps {
  status: SystemStatus
}

export function SystemStatusSummary({ status }: SystemStatusSummaryProps) {
  const items: Array<[string, boolean | undefined]> = [
    ['Python', status.python], ['Node.js', status.node], ['npm', status.npm], ['Git', status.git],
    ['PostgreSQL', status.postgres], ['FastAPI', status.fastapi], ['LangGraph', status.langgraph],
    ['LangGraph 영속화', status.langgraph_persistent], ['Ollama', status.ollama],
    ['Tavily Key', status.tavily_key], ['LangSmith Key', status.langsmith_key],
  ]

  return (
    <section className="status-summary">
      <h2>현재 상태 요약</h2>
      <div className="system-grid">
        {items.map(([name, ok]: LegacyValue) => <div className="status-row" key={name}>
          <span><StatusDot ok={!!ok}/>{name}</span><strong>{ok ? '정상/설정됨' : '확인 필요'}</strong>
        </div>)}
        <div className="status-row">
          <span><StatusDot ok={status.openai_enabled === false || !!status.openai_key}/>OpenAI</span>
          <strong>{status.openai_enabled === false ? '비사용 · Ollama 전용' : status.openai_key ? '사용 · Key 설정됨' : '사용 · Key 확인 필요'}</strong>
        </div>
      </div>
      {!status.langgraph_persistent && status.langgraph_persistent_message && (
        <div className="hint-box" style={{ marginTop: 12 }}>
          LangGraph 영속화 진단: {String(status.langgraph_persistent_message)}
        </div>
      )}
    </section>
  )
}
