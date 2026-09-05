import { Fragment, useState } from 'react'
import { MediaWorkflowEditor } from './components/MediaWorkflowEditor'

const WORKFLOW_ICON_RULES:Array<[string[],string]>=[
  [['transport','stdio','streamable'],'⇄'],
  [['security','보안','경로 검증','허용'],'🛡'],
  [['extension','확장자'],'✓'],
  [['provider','모델 선택','llm provider'],'◉'],
  [['export','내보내기','txt','md 저장'],'⇩'],
  [['upload','등록','업로드','publish'],'⇧'],
  [['auth','인증','oauth','login'],'◉'],
  [['validate','검증','확인','check'],'✓'],
  [['select','선택','choose'],'⌁'],
  [['analy','분석','analyze'],'⌕'],
  [['plan','계획','설계','design'],'◇'],
  [['search','조회','검색','find'],'⌕'],
  [['download','다운로드'],'⇩'],
  [['generate','생성','작성','create'],'✦'],
  [['save','저장','persist'],'▣'],
  [['test','테스트','시험'],'▶'],
  [['retry','재시도','복구','repair'],'↻'],
  [['error','실패','오류','fail'],'!'],
  [['channel','채널'],'▦'],
  [['video','영상'],'▷'],
  [['file','파일'],'▤'],
  [['message','질문','대화','chat'],'✉'],
  [['database','db','데이터'],'◫'],
  [['api','mcp','tool','도구'],'⚙'],
]

function workflowIconFor(text: LegacyValue=''){
  const value=String(text).toLowerCase()
  for(const [keys,icon] of WORKFLOW_ICON_RULES){
    if(keys.some((key: LegacyValue)=>value.includes(String(key).toLowerCase()))){
      return icon
    }
  }
  return '◆'
}

function normalizeTargetStep(step: LegacyValue,index: LegacyValue){
  if(typeof step==='string'){
    return {
      name:step,
      label:step,
      description:'',
      icon:workflowIconFor(step),
      index
    }
  }

  const item=step||{}
  const label=
    item.label
    || item.title
    || item.name
    || item.step
    || `Step ${index+1}`

  return {
    ...item,
    name:item.name||label,
    label,
    description:
      item.description
      || item.purpose
      || item.detail
      || item.reason
      || '',
    icon:item.icon||workflowIconFor(label),
    index
  }
}

function FactoryNodeCard({node,index}:LegacyRecord){
  const accent=node?.accent||'default'

  return <div className={`factory-node-card ${accent}`}>
    <div className="factory-node-visual">
      <span className="factory-node-icon">{node?.icon||'◆'}</span>
      <span className="factory-node-number">{String(index+1).padStart(2,'0')}</span>
    </div>
    <div className="factory-node-copy">
      <strong>{node?.label||node.name}</strong>
      <small>{node?.description||''}</small>
    </div>
  </div>
}

function FactoryPhaseCard({phase,phaseIndex,isLast=false}:LegacyRecord){
  return <div className="factory-phase-wrap">
    <section className={`factory-phase-card phase-${String(phase?.id||'').toLowerCase()}`}>
      <header className="factory-phase-head">
        <div className="factory-phase-symbol">{phase?.icon||'◇'}</div>
        <div>
          <span>PHASE {String(phaseIndex+1).padStart(2,'0')}</span>
          <strong>{phase?.title||phase?.id}</strong>
          <small>{phase?.subtitle||''}</small>
        </div>
      </header>

      <div className="factory-phase-nodes">
        {(phase?.nodes||[]).map((node: LegacyValue,index: LegacyValue)=>
          <FactoryNodeCard
            key={node.name||index}
            node={node}
            index={index}
          />
        )}
      </div>
    </section>
    {!isLast&&<div className="factory-phase-connector">
      <span></span>
      <b>→</b>
      <span></span>
    </div>}
  </div>
}

export function FactoryWorkflowDiagram({definition}:LegacyRecord){
  const fallback=[
    {
      id:'DISCOVER',
      title:'요구 이해',
      subtitle:'무엇을 왜 만들지 정리합니다.',
      icon:'◎',
      nodes:[
        {label:'요구사항 분석',description:'목표·입력·출력·제약 구조화',icon:'✦'},
        {label:'프로젝트 분석',description:'기존 구조와 관련 파일 파악',icon:'⌕'}
      ]
    },
    {
      id:'DESIGN',
      title:'Agent 설계',
      subtitle:'기능·도구·구조·업무 흐름을 결정합니다.',
      icon:'◇',
      nodes:[
        {label:'기능 설계',description:'핵심 능력 정의',icon:'✣'},
        {label:'Tool / MCP 판단',description:'외부 기능 연결 방식 결정',icon:'⚙'},
        {label:'Agent 아키텍처',description:'컴포넌트와 상태 설계',icon:'⬡'},
        {label:'대상 Agent Workflow',description:'실제 업무 흐름 설계',icon:'⇢',accent:'target'},
        {label:'파일 계획',description:'수정·생성 파일 배치',icon:'▤'}
      ]
    },
    {
      id:'BUILD',
      title:'제작',
      subtitle:'코드와 실행 환경을 구성합니다.',
      icon:'⌘',
      nodes:[
        {label:'체크포인트',description:'변경 전 복구 지점',icon:'◈'},
        {label:'실행 승인',description:'실제 변경 전 확인',icon:'✓'},
        {label:'코드 생성 / 수정',description:'파일 생성과 최소 수정',icon:'</>'},
        {label:'환경 구성',description:'패키지·환경변수 설정',icon:'⚡'}
      ]
    },
    {
      id:'VERIFY',
      title:'검증 & 완성',
      subtitle:'실행·복구·완료를 확인합니다.',
      icon:'✓',
      nodes:[
        {label:'테스트',description:'실행·기능 검증',icon:'▶'},
        {label:'디버그 / 복구',description:'실패 원인 분석 후 재수정',icon:'↻',accent:'warning'},
        {label:'완성 패키지',description:'결과 정리',icon:'▣'},
        {label:'최종 검토',description:'완료 조건 확인',icon:'★'}
      ]
    }
  ]

  const phases=definition?.factory_phases||fallback

  return <div className="factory-workflow-diagram">
    <div className="factory-start-pill">
      <span>USER</span>
      <b>“OO 에이전트 만들어줘”</b>
    </div>

    <div className="factory-start-line">
      <span></span><b>↓</b><span></span>
    </div>

    <div className="factory-phase-grid">
      {phases.map((phase: LegacyValue,index: LegacyValue)=>
        <FactoryPhaseCard
          key={phase.id||index}
          phase={phase}
          phaseIndex={index}
          isLast={index===phases.length-1}
        />
      )}
    </div>

    <div className="factory-repair-band">
      <div className="repair-band-icon">↻</div>
      <div>
        <strong>자동 복구 루프</strong>
        <small>테스트 실패 시 원인을 분석하고 코드를 다시 수정한 뒤 재검증합니다.</small>
      </div>
      <div className="repair-band-flow">
        <span>TEST</span><b>→</b>
        <span className="warn">DEBUG</span><b>→</b>
        <span>CODE</span><b>→</b>
        <span>ENV</span><b>→</b>
        <span>RE-TEST</span>
      </div>
    </div>

    <div className="factory-complete-pill">
      <span>★</span>
      <div>
        <strong>실행 가능한 Agent 프로그램 완성</strong>
        <small>코드 생성만이 아니라 테스트와 최종 검토까지 통과한 상태</small>
      </div>
    </div>
  </div>
}

export function DevelopmentStageWorkflowDiagram({workflow}:LegacyRecord){
  const stages=Array.isArray(workflow?.stages)?workflow.stages:[]
  if(!stages.length) return null
  return <div className="development-stage-workflow">
    <div className="development-stage-workflow-head">
      <div><small>APPROVED DEVELOPMENT WORKFLOW</small><strong>Agent 개발 Stage Workflow</strong></div>
      <span>{stages.length} Stage · 단계별 완료 조건 / 검증</span>
    </div>
    <div className="development-stage-workflow-track">
      {stages.map((stage: LegacyValue,index: LegacyValue)=><Fragment key={stage.id||index}>
        <article className="development-stage-workflow-card">
          <span className="development-stage-workflow-number">{index+1}</span>
          <div>
            <div className="development-stage-workflow-title"><strong>{stage.title||`Stage ${index+1}`}</strong><span>{stage.status||'APPROVED'}</span></div>
            <small>{stage.goal||''}</small>
            {Array.isArray(stage.validation)&&stage.validation.length>0&&<div className="development-stage-workflow-checks">{stage.validation.slice(0,2).map((item: LegacyValue,checkIndex: LegacyValue)=><span key={checkIndex}>✓ {item}</span>)}</div>}
            <em>계획 파일 {Number(stage.planned_file_count||0)}개 · Checkpoint {stage.checkpoint_after_stage===false?'OFF':'ON'} · Stage Test {stage.test_after_stage===false?'OFF':'ON'}</em>
          </div>
        </article>
        {index<stages.length-1&&<div className="development-stage-workflow-arrow">→</div>}
      </Fragment>)}
    </div>
    <div className="development-stage-workflow-policy">순차 개발 정책 · Stage 실패 시 중단 · 완료 Stage 보존 · 실패 Stage부터 재개하도록 Workflow 계약 구성</div>
  </div>
}

export function TargetWorkflowDiagram({workflow,onWorkflowChange}:LegacyRecord){
  const [selectedGroup,setSelectedGroup]=useState<LegacyValue|null>(null)
  const [workflowMode,setWorkflowMode]=useState('GROUPS')

  const rawSteps=(workflow?.steps||[]).map((step: LegacyValue,index: LegacyValue)=>{
    if(typeof step==='string'){
      return {
        name:`step_${index+1}`,
        label:step,
        description:'',
        type:'process',
        icon:'◆'
      }
    }

    return {
      ...step,
      name:step?.name||`step_${index+1}`,
      label:step?.label||step?.name||`Step ${index+1}`,
      description:step?.description||'',
      type:step?.type||'process',
      icon:step?.icon||workflowIconFor(step),
    }
  })

  const mediaStepTypes=new Set(['media_input','media_analysis','media_plan','media_process','media_generate','media_validate','approval','preview'])
  const hasMediaWorkflow=rawSteps.some((step: LegacyValue)=>mediaStepTypes.has(String(step?.type||'').toLowerCase()))
    ||(Array.isArray(workflow?.nodes)&&workflow.nodes.some((node: LegacyValue)=>String(node?.type||'').toUpperCase().includes('IMAGE')||String(node?.type||'').toUpperCase().includes('VIDEO')))

  if(!rawSteps.length){
    return <div className="target-empty">
      <div className="target-empty-graphic">
        <span>◇</span>
        <i></i>
        <span>◆</span>
        <i></i>
        <span>★</span>
      </div>
      <strong>아직 대상 Agent Workflow가 없습니다.</strong>
      <p>에이전트 개발 요청을 분석하면 실제 업무 단계가 시각적인 Workflow로 표시됩니다.</p>
    </div>
  }

  const classifyStep=(step: LegacyValue)=>{
    const text=[
      step?.name,
      step?.label,
      step?.description,
      step?.type
    ].join(' ').toLowerCase()

    const explicitType=String(step?.type||'').toLowerCase()
    if(explicitType==='media_input') return 'MEDIA_INPUT'
    if(explicitType==='media_analysis') return 'MEDIA_ANALYSIS'
    if(explicitType==='media_plan') return 'MEDIA_PLAN'
    if(explicitType==='media_process'||explicitType==='media_generate') return 'MEDIA_EXECUTION'
    if(explicitType==='media_validate') return 'QA'
    if(explicitType==='approval') return 'APPROVAL'
    if(explicitType==='preview') return 'PREVIEW'

    if(
      text.includes('complete')
      || text.includes('완료')
    ) return 'COMPLETE'

    if(
      text.includes('viewport')
      || text.includes('vision')
      || text.includes('qa')
      || text.includes('repair')
      || text.includes('품질')
      || text.includes('수정 필요')
    ) return 'QA'

    if(
      text.includes('blender')
      || text.includes('3d')
      || text.includes('scene')
      || text.includes('mesh')
      || text.includes('material')
      || text.includes('camera')
      || text.includes('lighting')
      || text.includes('render')
      || text.includes('export')
    ) return 'BLENDER'

    if(
      text.includes('save')
      || text.includes('저장')
      || text.includes('output')
      || text.includes('storage')
    ) return 'SAVE'

    if(
      text.includes('display')
      || text.includes('결과 표시')
      || text.includes('ui')
      || text.includes('react')
    ) return 'OUTPUT'

    if(
      text.includes('llm')
      || text.includes('provider')
      || text.includes('model')
      || text.includes('요약 생성')
      || text.includes('generate_summary')
    ) return 'LLM'

    if(
      text.includes('mcp')
      || text.includes('transport')
      || text.includes('tool')
      || text.includes('파일 읽기')
      || text.includes('file_read')
    ) return 'MCP'

    if(
      text.includes('validate')
      || text.includes('검증')
      || text.includes('파일 선택')
      || text.includes('input')
      || text.includes('extension')
      || text.includes('root')
    ) return 'INPUT'

    return 'INPUT'
  }

  const groupDefinitions=[
    {
      id:'INPUT',
      title:'입력 / 검증',
      subtitle:'파일 선택과 접근 검증',
      icon:'✓'
    },
    {
      id:'MEDIA_INPUT',
      title:'Media 입력',
      subtitle:'Image · Video · Audio · Asset',
      icon:'▧'
    },
    {
      id:'MEDIA_ANALYSIS',
      title:'Media 분석',
      subtitle:'Vision · OCR · Quality · Object',
      icon:'◎'
    },
    {
      id:'MEDIA_PLAN',
      title:'Media 계획',
      subtitle:'Prompt · Style · Layout · Scene',
      icon:'✦'
    },
    {
      id:'MEDIA_EXECUTION',
      title:'Media 생성/처리',
      subtitle:'Provider · Job · Generate · Process',
      icon:'▶'
    },
    {
      id:'APPROVAL',
      title:'Human Approval',
      subtitle:'승인 · 수정 요청 · 재생성',
      icon:'✓'
    },
    {
      id:'PREVIEW',
      title:'Media Preview',
      subtitle:'Image · Video · Before/After',
      icon:'◫'
    },
    {
      id:'MCP',
      title:'MCP / Tool 실행',
      subtitle:'Client · Transport · Server · Tool',
      icon:'⚙'
    },
    {
      id:'BLENDER',
      title:'3D Scene 제작',
      subtitle:'Blender · Scene · Material · Render',
      icon:'◈'
    },
    {
      id:'QA',
      title:'Viewport QA / 수정',
      subtitle:'Capture · Vision QA · Repair Loop',
      icon:'◎'
    },
    {
      id:'LLM',
      title:'LLM 요약',
      subtitle:'Provider 확인과 AI 요약',
      icon:'✦'
    },
    {
      id:'OUTPUT',
      title:'결과 표시',
      subtitle:'React UI 결과 제공',
      icon:'◆'
    },
    {
      id:'SAVE',
      title:'선택적 저장',
      subtitle:'형식 · 경로 검증 · 저장',
      icon:'▣'
    },
    {
      id:'COMPLETE',
      title:'완료',
      subtitle:'업무 처리 종료',
      icon:'★'
    }
  ]

  const groups=groupDefinitions
    .map((def: LegacyValue)=>({
      ...def,
      steps:rawSteps.filter((step: LegacyValue)=>classifyStep(step)===def.id)
    }))
    .filter((group: LegacyValue)=>group.steps.length>0 || group.id==='COMPLETE')

  const activeGroup=groups.find((x: LegacyValue)=>x.id===selectedGroup)

  if(workflowMode==='MEDIA_EDITOR'&&hasMediaWorkflow){
    return <div className="media-workflow-editor-back-shell">
      <MediaWorkflowEditor workflow={workflow} onChange={onWorkflowChange} onClose={()=>setWorkflowMode('GROUPS')} />
    </div>
  }

  if(activeGroup){
    return <div className="grouped-workflow-detail">
      <div className="grouped-detail-head">
        <button
          type="button"
          onClick={()=>setSelectedGroup(null)}
          className="grouped-detail-back"
        >
          ← 전체 Workflow
        </button>

        <div className="grouped-detail-title">
          <span>{activeGroup.icon}</span>
          <div>
            <small>WORKFLOW GROUP</small>
            <strong>{activeGroup.title}</strong>
            <p>{activeGroup.subtitle}</p>
          </div>
        </div>
      </div>

      <div className="target-workflow-diagram detailed">
        <div className="target-start-card">
          <span className="target-start-icon">◎</span>
          <div>
            <small>START</small>
            <strong>{activeGroup.title}</strong>
          </div>
        </div>

        <div className="target-flow-track">
          {activeGroup.steps.map((step: LegacyValue,index: LegacyValue)=><div className="target-step-wrap" key={`${step.name}-${index}`}>
            <article className="target-step-card">
              <div className="target-step-top">
                <span className="target-step-icon">{step.icon}</span>
                <span className="target-step-index">{String(index+1).padStart(2,'0')}</span>
              </div>
              <strong>{step.label}</strong>
              {step.description&&<small>{step.description}</small>}
            </article>
            {index<activeGroup.steps.length-1&&<div className="target-step-arrow">
              <span></span><b>→</b><span></span>
            </div>}
          </div>)}
        </div>

        <div className="target-end-card">
          <span>★</span>
          <div>
            <small>GROUP COMPLETE</small>
            <strong>{activeGroup.title} 완료</strong>
          </div>
        </div>
      </div>
    </div>
  }

  return <div className="grouped-workflow-overview">
    <div className="grouped-workflow-head">
      <div>
        <small>TARGET AGENT WORKFLOW</small>
        <strong>{workflow?.name||'Agent Workflow'}</strong>
      </div>
      <div className="media-workflow-editor-actions">
        <span>그룹을 클릭하면 상세 단계가 표시됩니다.</span>
        {hasMediaWorkflow&&<button type="button" className="media-workflow-editor-open" onClick={()=>setWorkflowMode('MEDIA_EDITOR')}>▧ Media Workflow Editor</button>}
      </div>
    </div>

    <div className="grouped-workflow-track">
      {groups.map((group: LegacyValue,index: LegacyValue)=><div className="grouped-workflow-wrap" key={group.id}>
        <button
          type="button"
          className={`grouped-workflow-card ${group.id.toLowerCase()}`}
          onClick={()=>group.steps.length&&setSelectedGroup(group.id)}
          disabled={!group.steps.length}
          title={`${group.title} 상세 보기`}
        >
          <span className="grouped-workflow-icon">{group.icon}</span>
          <strong>{group.title}</strong>
          <small>{group.steps.length}단계</small>
        </button>

        {index<groups.length-1&&<div className="grouped-workflow-arrow">
          <span></span>
          <b>→</b>
          <span></span>
        </div>}
      </div>)}
    </div>

    {(workflow?.requirement_coverage?.length>0)&&<div className="workflow-coverage-panel compact">
      <div className="workflow-coverage-head">
        <div>
          <small>REQUIREMENT TRACEABILITY</small>
          <strong>요구사항 반영 확인</strong>
        </div>
        <span>
          {workflow.requirement_coverage.filter((x: LegacyValue)=>x?.status==='covered').length}
          /{workflow.requirement_coverage.length} 반영
        </span>
      </div>
    </div>}
  </div>
}
