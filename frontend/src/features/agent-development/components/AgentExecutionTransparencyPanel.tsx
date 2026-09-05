import React, { useMemo } from 'react'

type LegacyValue=any

type Props={
  mode:'DESIGN'|'DEVELOPMENT'
  active:boolean
  stage:string
  detail:string
  percent:number
  elapsedLabel?:string
  requirementItems?:LegacyValue[]
  stagePlan?:LegacyValue
  workflowPreview?:LegacyValue
  databasePreview?:LegacyValue
  events?:LegacyValue[]
  recoveryInfo?:LegacyValue
}

const DESIGN_PHASES=[
  {icon:'🔎',label:'요구사항 구조화',min:0},
  {icon:'✦',label:'AI 설계 요청',min:18},
  {icon:'⛓',label:'Workflow 구성',min:45},
  {icon:'▦',label:'DB / Tool 설계',min:68},
  {icon:'✓',label:'설계 검증',min:90},
]
const DEVELOPMENT_PHASES=[
  {icon:'⚙',label:'개발 준비',min:0},
  {icon:'◆',label:'Factory 실행',min:10},
  {icon:'⌘',label:'코드 생성 / 수정',min:30},
  {icon:'▶',label:'테스트 / 복구',min:58},
  {icon:'▣',label:'패키징 / 검증',min:78},
  {icon:'✓',label:'완료',min:100},
]

function countList(value:LegacyValue):number{
  return Array.isArray(value)?value.length:0
}

function displayStageIcon(mode:'DESIGN'|'DEVELOPMENT',stage:string){
  const text=String(stage||'').toLowerCase()
  if(text.includes('요구'))return '🔎'
  if(text.includes('검증'))return '✓'
  if(text.includes('db')||text.includes('database'))return '▦'
  if(text.includes('복구')||text.includes('재개'))return '↻'
  if(text.includes('테스트'))return '▶'
  if(text.includes('패키'))return '▣'
  if(text.includes('코드')||text.includes('file'))return '⌘'
  return mode==='DESIGN'?'✦':'◆'
}

export function AgentExecutionTransparencyPanel({
  mode,active,stage,detail,percent,elapsedLabel='',
  requirementItems=[],stagePlan,workflowPreview,databasePreview,events=[],recoveryInfo,
}:Props){
  const safePercent=Math.max(0,Math.min(100,Number(percent||0)))
  const phases=mode==='DESIGN'?DESIGN_PHASES:DEVELOPMENT_PHASES
  const collected=requirementItems.filter((item:LegacyValue)=>item?.collected)
  const targetWorkflow=workflowPreview?.target_agent_workflow||workflowPreview?.workflow||{}
  const workflowSteps=countList(targetWorkflow?.steps)
  const workflowBranches=countList(targetWorkflow?.branches)
  const dbModules=countList(databasePreview?.modules||workflowPreview?.database_plan?.modules)
  const dbEntities=countList(databasePreview?.tables||workflowPreview?.database_plan?.tables)
  const stageCount=countList(stagePlan?.stages)
  const latestEvents=Array.isArray(events)?events.slice(-5):[]

  const summaryRows=useMemo(()=>{
    if(mode==='DESIGN'){
      return [
        {icon:'☑',label:'확정 요구사항',value:`${collected.length}/${requirementItems.length||collected.length||0}`},
        {icon:'◇',label:'개발 Stage',value:stageCount?`${stageCount}개`:'승인 정보 대기'},
        {icon:'⛓',label:'Workflow',value:workflowSteps?`${workflowSteps} 단계 · 분기 ${workflowBranches}`:'설계 응답 대기'},
        {icon:'▦',label:'DB 초안',value:(dbModules||dbEntities)?`Module ${dbModules} · Entity ${dbEntities}`:'DB 요구사항에 따라 계산'},
      ]
    }
    return [
      {icon:'◆',label:'현재 Stage',value:stage||'대기'},
      {icon:'⌁',label:'최근 완료 이벤트',value:latestEvents.length?`${latestEvents.length}개 표시`:'Backend 이벤트 대기'},
      {icon:'↻',label:'복구 상태',value:recoveryInfo?.message?'복구 정보 있음':'정상 진행'},
      {icon:'▣',label:'진행률',value:`${safePercent}%`},
    ]
  },[mode,collected.length,requirementItems.length,stageCount,workflowSteps,workflowBranches,dbModules,dbEntities,stage,latestEvents.length,recoveryInfo?.message,safePercent])

  return <section className={`agent-execution-transparency ${mode.toLowerCase()} ${active?'active':''}`}>
    <div className="agent-execution-transparency-head">
      <div className={`agent-execution-icon ${active?'working':''}`}>
        <span>{displayStageIcon(mode,stage)}</span>
        {active&&<i/>}
      </div>
      <div>
        <small>{mode==='DESIGN'?'DESIGN ACTIVITY':'DEVELOPMENT ACTIVITY'}</small>
        <strong>{stage||'대기 중'}</strong>
        <p>{detail||'현재 처리할 작업을 기다리고 있습니다.'}</p>
      </div>
      <div className="agent-execution-progress-badge">
        <b>{safePercent}%</b>
        {elapsedLabel&&<span>{elapsedLabel}</span>}
      </div>
    </div>

    <div className="agent-execution-phase-list">
      {phases.map((phase,index)=>{
        const done=safePercent>=100||safePercent>=phase.min+(index===phases.length-1?0:12)
        const current=!done&&safePercent>=phase.min
        return <div key={phase.label} className={`agent-execution-phase ${done?'done':current?'current':'waiting'}`}>
          <span className="agent-execution-phase-icon">{done?'✓':phase.icon}</span>
          <div><b>{phase.label}</b><small>{done?'완료':current?'진행 중':'대기'}</small></div>
          {current&&<em><i/><i/><i/></em>}
        </div>
      })}
    </div>

    <div className="agent-execution-now">
      <div className="agent-execution-now-title">
        <span className="agent-execution-live-dot"/>
        <div><small>지금 처리 중</small><strong>{stage||'대기'}</strong></div>
      </div>
      <p>{detail||'Backend 진행 이벤트를 기다리고 있습니다.'}</p>
      <small className="agent-execution-truth-note">표시 내용은 현재 Stage, 확정 요구사항, 설계 결과 및 Backend 이벤트를 기준으로 합니다. AI 내부 사고 과정을 임의로 만들어 표시하지 않습니다.</small>
    </div>

    <div className="agent-execution-summary">
      <div className="agent-execution-summary-head">
        <div><span>▤</span><div><strong>현재까지 정리된 내용</strong><small>사용자가 지금까지 무엇이 확정·생성되었는지 확인할 수 있습니다.</small></div></div>
      </div>
      <div className="agent-execution-summary-grid">
        {summaryRows.map(row=><div key={row.label}><span>{row.icon}</span><small>{row.label}</small><strong>{row.value}</strong></div>)}
      </div>
    </div>

    {mode==='DESIGN'&&collected.length>0&&<details className="agent-execution-requirement-detail">
      <summary>요구사항 분석 내용 보기 <b>{collected.length}개</b></summary>
      <div>
        {collected.slice(0,12).map((item:LegacyValue)=><span key={String(item?.id||item?.label)}>
          <i>✓</i><b>{item?.label||item?.id}</b><em>{String(item?.value||'확인됨').slice(0,160)}</em>
        </span>)}
      </div>
    </details>}

    {mode==='DEVELOPMENT'&&latestEvents.length>0&&<div className="agent-execution-event-list">
      <div className="agent-execution-event-head"><strong>실제 Backend 진행 이벤트</strong><small>최근 {latestEvents.length}개</small></div>
      {latestEvents.map((event:LegacyValue,index:number)=><div key={`${event?.at||''}-${event?.node||''}-${index}`}>
        <span>✓</span>
        <b>{event?.node||event?.status||'workflow'}</b>
        <em>{event?.message||'단계 완료'}</em>
      </div>)}
    </div>}

    {recoveryInfo?.message&&<div className="agent-execution-recovery"><span>↻</span><div><b>복구 / 재개 상태</b><small>{recoveryInfo.message}</small></div></div>}
  </section>
}
