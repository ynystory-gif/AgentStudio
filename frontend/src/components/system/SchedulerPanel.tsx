import React from 'react'

type SchedulerJob={
  id?:string
  source?:string
  source_label?:string
  kind?:string
  status?:string
  progress?:number
  stage?:string
  message?:string
  created_at?:string
  updated_at?:string
  active?:boolean
  can_cancel?:boolean
  hard_timeout_triggered?:boolean
  backend_cleanup_state?:string
  backend_cleanup_completed?:boolean
  backend_execution_active?:boolean
  backend_analysis_ended?:boolean
  backend_terminated_at?:string
  backend_worker_process_count?:number
}

type SchedulerSummary={
  total?:number
  active?:number
  running?:number
  queued?:number
  cancelling?:number
  success?:number
  failed?:number
  cancelled?:number
}

type SchedulerReport={
  jobs?:SchedulerJob[]
  summary?:SchedulerSummary
  generated_at?:string
  include_terminal?:boolean
}

const ACTIVE_STATUSES=new Set(['QUEUED','PENDING','RUNNING','WAITING_USER','CANCELLING'])

const STATUS_LABEL:Record<string,string>={
  QUEUED:'대기',PENDING:'대기',RUNNING:'실행 중',WAITING_USER:'사용자 대기',CANCELLING:'취소 중',
  SUCCESS:'완료',COMPLETED:'완료',FAILED:'실패',ERROR:'오류',CANCELLED:'취소됨',
}

const KIND_LABEL:Record<string,string>={
  AGENT_BUILD:'Agent 개발',
  AGENT_REDEVELOP:'Agent 재개발',
  COMMAND:'명령 실행',
  EXTERNAL_PROJECT_ANALYSIS:'외부 프로젝트 분석',
  AI_ATTACHMENT_ANALYSIS:'첨부 파일 AI 분석',
  PGVECTOR_INSTALL:'pgvector 설치',
  OLLAMA_INSTALL:'Ollama 설치',
  UI_THEME_ANALYSIS:'UI / Layout Theme 분석',
}

const formatTime=(value?:string)=>{
  if(!value)return '-'
  const date=new Date(value)
  if(Number.isNaN(date.getTime()))return String(value)
  return date.toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})
}

const shortId=(value?:string)=>{
  const text=String(value||'')
  return text.length>14?`${text.slice(0,8)}…${text.slice(-4)}`:text||'-'
}

export function SchedulerPanel({
  report,
  loading=false,
  error='',
  includeTerminal=false,
  cancelBusy='',
  onRefresh,
  onIncludeTerminalChange,
  onCancel,
}:{
  report?:SchedulerReport|null
  loading?:boolean
  error?:string
  includeTerminal?:boolean
  cancelBusy?:string
  onRefresh?:()=>void
  onIncludeTerminalChange?:(value:boolean)=>void
  onCancel?:(job:SchedulerJob)=>void
}){
  const jobs=Array.isArray(report?.jobs)?report?.jobs:[]
  const summary=report?.summary||{}
  return <div className="scheduler-dashboard">
    <div className="dashboard-hero report scheduler-hero">
      <div>
        <span className="dashboard-eyebrow">AGENTSTUDIO BACKGROUND SCHEDULER</span>
        <h2>스케줄러</h2>
        <p>AgentStudio Backend에서 실행·대기 중인 Background Job과 UI / Layout Theme 분석 작업을 한 곳에서 확인하고 실행을 취소합니다.</p>
      </div>
      <div className="scheduler-hero-actions">
        <label className="scheduler-history-toggle">
          <input type="checkbox" checked={includeTerminal} onChange={(event: LegacyValue)=>onIncludeTerminalChange?.(event.target.checked)}/>
          <span>종료된 작업 포함</span>
        </label>
        <button type="button" onClick={()=>onRefresh?.()} disabled={loading}>{loading?'조회 중...':'↻ 새로고침'}</button>
      </div>
    </div>

    <div className="scheduler-metrics">
      <div><span>현재 실행/대기</span><strong>{Number(summary.active||0)}개</strong><small>취소 가능한 Scheduler 작업</small></div>
      <div><span>실행 중</span><strong>{Number(summary.running||0)}개</strong><small>RUNNING</small></div>
      <div><span>대기/사용자 대기</span><strong>{Number(summary.queued||0)}개</strong><small>QUEUED · WAITING</small></div>
      <div><span>실패/취소</span><strong>{Number(summary.failed||0)+Number(summary.cancelled||0)}개</strong><small>최근 Backend 메모리 기준</small></div>
    </div>

    {error&&<div className="scheduler-error">스케줄러 조회 오류: {error}</div>}

    <section className="scheduler-list-card">
      <div className="scheduler-list-head">
        <div>
          <strong>{includeTerminal?'Scheduler 작업 목록':'현재 실행 중인 Scheduler 목록'}</strong>
          <small>{jobs.length}개 표시 · {report?.generated_at?`마지막 확인 ${formatTime(report.generated_at)}`:'Backend 상태 확인 대기'}</small>
        </div>
        <span className={Number(summary.active||0)>0?'live':'idle'}>{Number(summary.active||0)>0?'● LIVE':'● IDLE'}</span>
      </div>

      <div className="scheduler-table-wrap">
        <div className="scheduler-table scheduler-table-header" aria-hidden="true">
          <span>작업</span><span>상태</span><span>진행률</span><span>현재 단계 / 메시지</span><span>시작 / 갱신</span><span>실행</span>
        </div>
        {jobs.map((job: LegacyValue)=>{
          const status=String(job.status||'').toUpperCase()
          const active=Boolean(job.active)||ACTIVE_STATUSES.has(status)
          const key=`${job.source||'JOB'}:${job.id||''}`
          const cancelling=cancelBusy===key||status==='CANCELLING'
          const progress=Math.max(0,Math.min(100,Number(job.progress||0)))
          return <div className={`scheduler-table scheduler-row ${active?'active':'terminal'}`} key={key}>
            <div className="scheduler-job-name">
              <strong>{KIND_LABEL[String(job.kind||'').toUpperCase()]||job.kind||'Background Job'}</strong>
              <small>{job.source_label||job.source||'AgentStudio'} · ID {shortId(job.id)}</small>
            </div>
            <div><span className={`scheduler-status ${status.toLowerCase()}`}>{STATUS_LABEL[status]||status||'-'}</span></div>
            <div className="scheduler-progress-cell">
              <div className="scheduler-progress-track"><i style={{width:`${progress}%`}}/></div>
              <small>{Math.round(progress)}%</small>
            </div>
            <div className="scheduler-stage-cell">
              <strong>{job.stage||'진행 상태 확인 중'}</strong>
              <small title={job.message||''}>{job.message||'-'}</small>
              {job.source==='UI_THEME'&&<small className={job.backend_analysis_ended?'scheduler-backend-ended':job.hard_timeout_triggered?'scheduler-backend-ending':''}>
                {job.backend_analysis_ended
                  ? `Backend 종료 확인됨 · Worker ${Number(job.backend_worker_process_count||0)}개`
                  : job.hard_timeout_triggered
                    ? `Backend 종료 처리 중 · cleanup=${job.backend_cleanup_state||'running'}`
                    : `Backend 실행 상태 · Worker ${Number(job.backend_worker_process_count||0)}개`}
              </small>}
            </div>
            <div className="scheduler-time-cell">
              <small>시작 {formatTime(job.created_at)}</small>
              <small>갱신 {formatTime(job.updated_at)}</small>
            </div>
            <div className="scheduler-cancel-cell">
              <button
                type="button"
                className="scheduler-cancel-button"
                disabled={!active||!job.can_cancel||cancelling}
                onClick={()=>onCancel?.(job)}
                title={active?'해당 Backend Scheduler 작업만 취소합니다.':'이미 종료된 작업입니다.'}
              >
                {cancelling?'취소 중...':active?(job.can_cancel?'실행취소':'취소 불가'):'종료됨'}
              </button>
            </div>
          </div>
        })}
        {!loading&&!jobs.length&&<div className="scheduler-empty">
          <span>✓</span>
          <strong>현재 실행 중인 Scheduler 작업이 없습니다.</strong>
          <p>Agent 개발, 명령 실행, UI / Layout Theme 분석 같은 Backend 작업이 시작되면 여기에 표시됩니다.</p>
        </div>}
        {loading&&!jobs.length&&<div className="scheduler-empty"><span>…</span><strong>Backend Scheduler 상태를 불러오는 중입니다.</strong></div>}
      </div>
    </section>
  </div>
}
