import { asLegacyError } from '../../../utils/errors'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  loadMediaWorkflowCatalog,
  loadMediaWorkflowContracts,
  normalizeMediaWorkflow,
  validateMediaPortConnection,
  validateMediaWorkflow,
} from '../../../services/mediaWorkflowApi'
import './MediaWorkflowEditor.css'

const FALLBACK_CATALOG=[
  {type:'IMAGE_INPUT',label:'Image Input',category:'MEDIA_INPUT',phase:'1A',inputs:[],outputs:[{name:'image',type:'IMAGE',required:true}]},
  {type:'IMAGE_ANALYZER',label:'Image Analyzer',category:'MEDIA_ANALYSIS',phase:'1B',inputs:[{name:'image',type:'IMAGE',required:true}],outputs:[{name:'analysis',type:'JSON',required:true}]},
  {type:'PROMPT_GENERATOR',label:'Prompt Generator',category:'MEDIA_PLANNING',phase:'1B',inputs:[{name:'request',type:'TEXT',required:true},{name:'analysis',type:'JSON',required:false}],outputs:[{name:'prompt',type:'PROMPT',required:true},{name:'plan',type:'JSON',required:true}]},
  {type:'IMAGE_GENERATE',label:'Image Generate',category:'MEDIA_GENERATION',phase:'1A',execution_mode:'ASYNC',inputs:[{name:'prompt',type:'PROMPT',required:true},{name:'reference_image',type:'IMAGE',required:false},{name:'config',type:'JSON',required:false}],outputs:[{name:'image',type:'IMAGE',required:true},{name:'metadata',type:'JSON',required:true}]},
  {type:'IMAGE_QUALITY_VALIDATOR',label:'Image Quality Validator',category:'MEDIA_VALIDATION',phase:'1B',inputs:[{name:'image',type:'IMAGE',required:true},{name:'criteria',type:'JSON',required:false}],outputs:[{name:'validation',type:'JSON',required:true},{name:'valid',type:'BOOLEAN',required:true}]},
  {type:'HUMAN_APPROVAL',label:'Human Approval',category:'MEDIA_CONTROL',phase:'1B',execution_mode:'INTERRUPT',inputs:[{name:'artifact',type:'JSON',required:true}],outputs:[{name:'approved',type:'BOOLEAN',required:true},{name:'feedback',type:'TEXT',required:false}]},
  {type:'IMAGE_PREVIEW',label:'Image Preview',category:'MEDIA_PREVIEW',phase:'1A',inputs:[{name:'image',type:'IMAGE',required:true}],outputs:[{name:'artifact',type:'JSON',required:true}]},
  {type:'SAVE_IMAGE',label:'Save Image',category:'MEDIA_OUTPUT',phase:'1A',inputs:[{name:'image',type:'IMAGE',required:true},{name:'config',type:'JSON',required:false}],outputs:[{name:'artifact',type:'JSON',required:true}]},
  {type:'TEXT_TO_VIDEO',label:'Text-to-Video',category:'MEDIA_GENERATION',phase:'3',execution_mode:'ASYNC',inputs:[{name:'prompt',type:'PROMPT',required:true}],outputs:[{name:'video',type:'VIDEO',required:true},{name:'metadata',type:'JSON',required:true}]},
  {type:'VIDEO_QUALITY_VALIDATOR',label:'Video Quality Validator',category:'MEDIA_VALIDATION',phase:'3',inputs:[{name:'video',type:'VIDEO',required:true}],outputs:[{name:'validation',type:'JSON',required:true},{name:'valid',type:'BOOLEAN',required:true}]},
  {type:'VIDEO_PREVIEW',label:'Video Preview',category:'MEDIA_PREVIEW',phase:'3',inputs:[{name:'video',type:'VIDEO',required:true}],outputs:[{name:'artifact',type:'JSON',required:true}]},
  {type:'SAVE_VIDEO',label:'Save Video',category:'MEDIA_OUTPUT',phase:'3',inputs:[{name:'video',type:'VIDEO',required:true}],outputs:[{name:'artifact',type:'JSON',required:true}]},
]

const CATEGORY_META={
  MEDIA_INPUT:{label:'입력',icon:'▧'},
  MEDIA_ANALYSIS:{label:'분석',icon:'◎'},
  MEDIA_PLANNING:{label:'계획',icon:'✦'},
  MEDIA_PROCESSING:{label:'처리',icon:'◇'},
  MEDIA_GENERATION:{label:'생성',icon:'▶'},
  MEDIA_VALIDATION:{label:'검증',icon:'✓'},
  MEDIA_CONTROL:{label:'제어',icon:'↻'},
  MEDIA_PREVIEW:{label:'Preview',icon:'◫'},
  MEDIA_OUTPUT:{label:'출력',icon:'▣'},
}

const PROVIDERS=['AUTO','COMFYUI','DIFFUSERS','OPENAI_IMAGE','EXTERNAL_API','CUSTOM_API']
const NODE_WIDTH=190
const NODE_HEIGHT=112
const CANVAS_WIDTH=1420
const CANVAS_HEIGHT=650

const clone=(value: LegacyValue)=>JSON.parse(JSON.stringify(value??{}))
const mediaExtension=(workflow: LegacyValue)=>workflow?.extensions?.media&&typeof workflow.extensions.media==='object'?workflow.extensions.media:{}
const editorShape=(workflow: LegacyValue)=>{
  const value=clone(workflow||{})
  value.nodes=Array.isArray(value.nodes)?value.nodes:[]
  value.edges=Array.isArray(value.edges)?value.edges:[]
  value.variables=value.variables&&typeof value.variables==='object'?value.variables:{}
  value.extensions=value.extensions&&typeof value.extensions==='object'?value.extensions:{}
  value.extensions.media=value.extensions.media&&typeof value.extensions.media==='object'?value.extensions.media:{}
  value.extensions.media.schema_version=Number(value.extensions.media.schema_version||1)
  value.extensions.media.providers=value.extensions.media.providers&&typeof value.extensions.media.providers==='object'?value.extensions.media.providers:{}
  value.extensions.media.assets=value.extensions.media.assets&&typeof value.extensions.media.assets==='object'?value.extensions.media.assets:{}
  value.extensions.media.jobs=value.extensions.media.jobs&&typeof value.extensions.media.jobs==='object'?value.extensions.media.jobs:{}
  return value
}
const nodeId=(type: LegacyValue,index: LegacyValue)=>`${String(type||'MEDIA').toLowerCase()}_${Date.now().toString(36)}_${index}`
const findDef=(catalog: LegacyValue,type: LegacyValue)=>catalog.find((row: LegacyValue)=>row.type===type)||FALLBACK_CATALOG.find((row: LegacyValue)=>row.type===type)||null
const firstPort=(def: LegacyValue,key: LegacyValue,type: LegacyValue)=>((def?.[key]||[]).find((port: LegacyValue)=>!type||port.type===type)||(def?.[key]||[])[0]||null)
const makeNode=(type: LegacyValue,x: LegacyValue,y: LegacyValue,index: LegacyValue,catalog: LegacyValue)=>({
  id:nodeId(type,index),
  type,
  x:Math.max(12,Math.round(x)),
  y:Math.max(12,Math.round(y)),
  config:{provider:'AUTO',model:'',width:1024,height:1024,max_retry:2},
  label:findDef(catalog,type)?.label||type,
})
const makeEdge=(source: LegacyValue,target: LegacyValue,output: LegacyValue,input: LegacyValue,index: LegacyValue)=>({
  id:`edge_${Date.now().toString(36)}_${index}`,
  source:source.id,
  target:target.id,
  output_port:output?.name||'',
  input_port:input?.name||'',
  output_type:output?.type||'',
  input_type:input?.type||'',
})

function seedWorkflow(workflow: LegacyValue,catalog: LegacyValue){
  const value=editorShape(workflow)
  if(value.nodes.length) return value
  const text=[value.name,...(value.steps||[]).flatMap((step: LegacyValue)=>[step?.name,step?.label,step?.description])].join(' ').toLowerCase()
  const isVideo=/video|영상|쇼츠|릴스|text-to-video|image-to-video/.test(text)
  if(isVideo){
    const prompt=makeNode('PROMPT_GENERATOR',40,90,1,catalog)
    const generate=makeNode('TEXT_TO_VIDEO',300,90,2,catalog)
    const validate=makeNode('VIDEO_QUALITY_VALIDATOR',560,90,3,catalog)
    const preview=makeNode('VIDEO_PREVIEW',820,250,4,catalog)
    const save=makeNode('SAVE_VIDEO',1080,250,5,catalog)
    value.nodes=[prompt,generate,validate,preview,save]
    const promptDef=findDef(catalog,prompt.type), generateDef=findDef(catalog,generate.type), validateDef=findDef(catalog,validate.type), previewDef=findDef(catalog,preview.type), saveDef=findDef(catalog,save.type)
    value.edges=[
      makeEdge(prompt,generate,firstPort(promptDef,'outputs','PROMPT'),firstPort(generateDef,'inputs','PROMPT'),1),
      makeEdge(generate,validate,firstPort(generateDef,'outputs','VIDEO'),firstPort(validateDef,'inputs','VIDEO'),2),
      makeEdge(generate,preview,firstPort(generateDef,'outputs','VIDEO'),firstPort(previewDef,'inputs','VIDEO'),3),
      makeEdge(generate,save,firstPort(generateDef,'outputs','VIDEO'),firstPort(saveDef,'inputs','VIDEO'),4),
    ]
    return value
  }
  const input=makeNode('IMAGE_INPUT',30,80,1,catalog)
  const analyze=makeNode('IMAGE_ANALYZER',250,80,2,catalog)
  const prompt=makeNode('PROMPT_GENERATOR',470,80,3,catalog)
  const generate=makeNode('IMAGE_GENERATE',690,80,4,catalog)
  const validate=makeNode('IMAGE_QUALITY_VALIDATOR',910,80,5,catalog)
  const approval=makeNode('HUMAN_APPROVAL',1130,80,6,catalog)
  const preview=makeNode('IMAGE_PREVIEW',910,270,7,catalog)
  const save=makeNode('SAVE_IMAGE',1130,270,8,catalog)
  value.nodes=[input,analyze,prompt,generate,validate,approval,preview,save]
  const d=(type: LegacyValue)=>findDef(catalog,type)
  value.edges=[
    makeEdge(input,analyze,firstPort(d(input.type),'outputs','IMAGE'),firstPort(d(analyze.type),'inputs','IMAGE'),1),
    makeEdge(analyze,prompt,firstPort(d(analyze.type),'outputs','JSON'),firstPort(d(prompt.type),'inputs','JSON'),2),
    makeEdge(prompt,generate,firstPort(d(prompt.type),'outputs','PROMPT'),firstPort(d(generate.type),'inputs','PROMPT'),3),
    makeEdge(generate,validate,firstPort(d(generate.type),'outputs','IMAGE'),firstPort(d(validate.type),'inputs','IMAGE'),4),
    makeEdge(validate,approval,firstPort(d(validate.type),'outputs','JSON'),firstPort(d(approval.type),'inputs','JSON'),5),
    makeEdge(generate,preview,firstPort(d(generate.type),'outputs','IMAGE'),firstPort(d(preview.type),'inputs','IMAGE'),6),
    makeEdge(generate,save,firstPort(d(generate.type),'outputs','IMAGE'),firstPort(d(save.type),'inputs','IMAGE'),7),
  ]
  return value
}

const downloadableJson=(value: LegacyValue,filename: LegacyValue)=>{
  const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'})
  const url=URL.createObjectURL(blob)
  const anchor=document.createElement('a')
  anchor.href=url
  anchor.download=filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(()=>URL.revokeObjectURL(url),500)
}

export function MediaWorkflowEditor({workflow,onChange,onClose}:LegacyRecord){
  const canvasRef=useRef<LegacyValue|null>(null)
  const importInputRef=useRef<LegacyValue|null>(null)
  const [catalog,setCatalog]=useState(FALLBACK_CATALOG)
  const [contracts,setContracts]=useState<LegacyValue|null>(null)
  const [catalogError,setCatalogError]=useState('')
  const [editor,setEditor]=useState(()=>editorShape(workflow))
  const [selectedNodeId,setSelectedNodeId]=useState('')
  const [pendingConnection,setPendingConnection]=useState<LegacyValue|null>(null)
  const [message,setMessage]=useState('Media Workflow 편집 준비됨')
  const [validation,setValidation]=useState<LegacyValue|null>(null)
  const [busy,setBusy]=useState('')
  const workflowKey=useMemo(()=>JSON.stringify({nodes:workflow?.nodes||[],edges:workflow?.edges||[],media:mediaExtension(workflow)}),[workflow])

  useEffect(()=>{
    let cancelled=false
    Promise.allSettled([loadMediaWorkflowCatalog(),loadMediaWorkflowContracts()]).then((results: LegacyValue)=>{
      if(cancelled) return
      const catalogResult=results[0]
      if(catalogResult.status==='fulfilled'&&Array.isArray(catalogResult.value?.nodes)&&catalogResult.value.nodes.length){
        setCatalog(catalogResult.value.nodes)
        setCatalogError('')
      }else{
        setCatalogError('Backend Media Catalog를 불러오지 못해 내장 Core Node 목록을 표시합니다. AgentStudio Backend 재시작 후 다시 확인하세요.')
      }
      if(results[1].status==='fulfilled') setContracts(results[1].value)
    })
    return()=>{cancelled=true}
  },[])

  useEffect(()=>{
    setEditor(editorShape(workflow))
    setSelectedNodeId('')
    setPendingConnection(null)
    setValidation(null)
  },[workflowKey])

  useEffect(()=>{
    if(editor.nodes.length||!catalog.length) return
    setEditor(seedWorkflow(workflow,catalog))
  },[catalog,editor.nodes.length,workflow])

  const nodeMap=useMemo(()=>Object.fromEntries(editor.nodes.map((node: LegacyValue)=>[node.id,node])),[editor.nodes])
  const selectedNode=nodeMap[selectedNodeId]||null
  const selectedDef=selectedNode?findDef(catalog,selectedNode.type):null
  const groups=useMemo(()=>{
    const map=new Map<LegacyValue,LegacyValue>()
    for(const row of catalog){
      const key=row.category||'MEDIA_PROCESSING'
      if(!map.has(key)) map.set(key,[])
      map.get(key).push(row)
    }
    return [...map.entries()]
  },[catalog])
  const jobs=Object.values(mediaExtension(editor).jobs||{}) as LegacyRecord[]
  const currentJob=jobs.length?jobs[jobs.length-1]:null
  const artifacts=Object.values(mediaExtension(editor).assets||{}) as LegacyRecord[]
  const currentArtifact=artifacts.length?artifacts[artifacts.length-1]:null

  const updateNode=(id: LegacyValue,patch: LegacyValue)=>setEditor((prev: LegacyValue)=>({...prev,nodes:prev.nodes.map((node: LegacyValue)=>node.id===id?{...node,...patch}:node)}))
  const updateNodeConfig=(key: LegacyValue,value: LegacyValue)=>{
    if(!selectedNode) return
    setEditor((prev: LegacyValue)=>({...prev,nodes:prev.nodes.map((node: LegacyValue)=>node.id===selectedNode.id?{...node,config:{...(node.config||{}),[key]:value}}:node)}))
  }
  const removeNode=(id: LegacyValue)=>{
    setEditor((prev: LegacyValue)=>({...prev,nodes:prev.nodes.filter((node: LegacyValue)=>node.id!==id),edges:prev.edges.filter((edge: LegacyValue)=>edge.source!==id&&edge.target!==id)}))
    if(selectedNodeId===id) setSelectedNodeId('')
    setMessage('Node와 연결선을 제거했습니다.')
  }
  const addNode=(type: LegacyValue,x: LegacyValue=80,y: LegacyValue=80)=>{
    const node=makeNode(type,x,y,editor.nodes.length+1,catalog)
    setEditor((prev: LegacyValue)=>({...prev,nodes:[...prev.nodes,node]}))
    setSelectedNodeId(node.id)
    setMessage(`${node.label} Node를 추가했습니다.`)
  }
  const beginDrag=(event: LegacyValue,payload: LegacyValue)=>{
    event.dataTransfer.effectAllowed='move'
    event.dataTransfer.setData('application/x-theanova-media-node',JSON.stringify(payload))
  }
  const dropOnCanvas=(event: LegacyValue)=>{
    event.preventDefault()
    let payload:LegacyValue|null=null
    try{payload=JSON.parse(event.dataTransfer.getData('application/x-theanova-media-node')||'null')}catch{}
    if(!payload||!canvasRef.current) return
    const rect=canvasRef.current.getBoundingClientRect()
    const x=Math.max(10,Math.min(CANVAS_WIDTH-NODE_WIDTH-10,event.clientX-rect.left+canvasRef.current.scrollLeft-NODE_WIDTH/2))
    const y=Math.max(10,Math.min(CANVAS_HEIGHT-NODE_HEIGHT-10,event.clientY-rect.top+canvasRef.current.scrollTop-NODE_HEIGHT/2))
    if(payload.kind==='new') addNode(payload.type,x,y)
    if(payload.kind==='move'&&payload.id) updateNode(payload.id,{x:Math.round(x),y:Math.round(y)})
  }

  const connectToInput=async(targetNode: LegacyValue,inputPort: LegacyValue)=>{
    if(!pendingConnection) return
    if(pendingConnection.nodeId===targetNode.id){
      setMessage('같은 Node의 입출력은 연결할 수 없습니다.')
      return
    }
    setBusy('PORT')
    try{
      const result=await validateMediaPortConnection(pendingConnection.port.type,inputPort.type)
      if(!result?.compatible){
        setMessage(`연결 불가: ${pendingConnection.port.type} → ${inputPort.type}`)
        return
      }
      const duplicate=editor.edges.some((edge: LegacyValue)=>edge.source===pendingConnection.nodeId&&edge.target===targetNode.id&&edge.output_port===pendingConnection.port.name&&edge.input_port===inputPort.name)
      if(duplicate){setMessage('이미 존재하는 연결입니다.');return}
      const edge={
        id:`edge_${Date.now().toString(36)}`,
        source:pendingConnection.nodeId,
        target:targetNode.id,
        output_port:pendingConnection.port.name,
        input_port:inputPort.name,
        output_type:pendingConnection.port.type,
        input_type:inputPort.type,
      }
      setEditor((prev: LegacyValue)=>({...prev,edges:[...prev.edges,edge]}))
      setPendingConnection(null)
      setMessage(`연결됨: ${pendingConnection.port.type} → ${inputPort.type}`)
    }catch(error){
      setMessage(`Port 검증 실패: ${String(asLegacyError(error).message||error)}`)
    }finally{setBusy('')}
  }

  const validateGraph=async()=>{
    setBusy('VALIDATE')
    try{
      const result=await validateMediaWorkflow(editor)
      setValidation(result)
      setMessage(result?.valid===false?`Workflow 연결 오류 ${result?.issues?.length||0}건`:'Media Workflow 연결 검증 PASS')
      return result
    }catch(error){
      setValidation({valid:false,issues:[{message:String(asLegacyError(error).message||error)}]})
      setMessage(`Workflow 검증 실패: ${String(asLegacyError(error).message||error)}`)
      return null
    }finally{setBusy('')}
  }

  const saveGraph=async()=>{
    setBusy('SAVE')
    try{
      const checked=await validateMediaWorkflow(editor)
      setValidation(checked)
      if(checked?.valid===false){
        setMessage(`저장 전 연결 오류 ${checked?.issues?.length||0}건을 수정해 주세요.`)
        return
      }
      const normalized=await normalizeMediaWorkflow(editor)
      const next=normalized?.workflow||editor
      setEditor(next)
      onChange?.(next)
      setMessage('Media Workflow 설계를 반영했습니다. Agent 설계 Draft/Checkpoint에 자동 저장됩니다.')
    }catch(error){
      setMessage(`설계 저장 실패: ${String(asLegacyError(error).message||error)}`)
    }finally{setBusy('')}
  }

  const importJson=async(event: LegacyValue)=>{
    const file=event.target.files?.[0]
    event.target.value=''
    if(!file) return
    try{
      const parsed=JSON.parse(await file.text())
      const source=parsed?.target_agent_workflow&&typeof parsed.target_agent_workflow==='object'?parsed.target_agent_workflow:parsed
      const normalized=await normalizeMediaWorkflow(source)
      const next=editorShape(normalized?.workflow||source)
      setEditor(next)
      setSelectedNodeId('')
      setPendingConnection(null)
      setMessage(`Workflow JSON을 불러왔습니다: ${file.name}`)
    }catch(error){setMessage(`Workflow JSON 가져오기 실패: ${String(asLegacyError(error).message||error)}`)}
  }

  const resetStarter=()=>{
    setEditor(seedWorkflow({...workflow,nodes:[],edges:[]},catalog))
    setSelectedNodeId('')
    setPendingConnection(null)
    setValidation(null)
    setMessage('Media Starter Workflow를 다시 구성했습니다.')
  }

  return <section className="media-workflow-editor-shell">
    <header className="media-workflow-editor-head">
      <div>
        <small>MEDIA WORKFLOW EDITOR</small>
        <strong>{workflow?.name||'Media Creation Agent Workflow'}</strong>
        <span>고수준 Media Node만 편집합니다. ComfyUI의 KSampler/VAE/Checkpoint 그래프는 Provider Adapter 뒤에 유지됩니다.</span>
      </div>
      <div className="media-workflow-editor-toolbar">
        {onClose&&<button type="button" onClick={onClose}>← 그룹 Workflow</button>}
        <button type="button" onClick={()=>void validateGraph()} disabled={!!busy}>{busy==='VALIDATE'?'검증 중...':'✓ 연결 검증'}</button>
        <button type="button" className="primary" onClick={()=>void saveGraph()} disabled={!!busy}>{busy==='SAVE'?'저장 중...':'▣ 설계 반영'}</button>
        <button type="button" onClick={()=>importInputRef.current?.click()}>JSON 가져오기</button>
        <button type="button" onClick={()=>downloadableJson(editor,'media_workflow.json')}>JSON 내보내기</button>
        <input ref={importInputRef} type="file" accept="application/json,.json" hidden onChange={importJson}/>
      </div>
    </header>

    <div className="media-workflow-runtime-note">
      <span className="editor-mode">EDITOR MODE</span>
      <b>▶ 실행</b><b>■ 정지</b>
      <span>현재는 설계/검증 UI입니다. 실제 Provider 실행은 생성 대상 Agent의 Media Provider Adapter가 연결되면 활성화됩니다.</span>
    </div>

    {catalogError&&<div className="media-workflow-warning">! {catalogError}</div>}

    <div className="media-workflow-editor-grid">
      <aside className="media-node-palette">
        <div className="media-pane-head"><strong>Media Nodes</strong><small>{catalog.length} Node · Drag / Click</small></div>
        <div className="media-node-palette-scroll">
          {groups.map(([category,rows]: LegacyValue)=><div className="media-palette-group" key={category}>
            <div><span>{CATEGORY_META[category as keyof typeof CATEGORY_META]?.icon||'◇'}</span><strong>{CATEGORY_META[category as keyof typeof CATEGORY_META]?.label||category}</strong><small>{rows.length}</small></div>
            {rows.map((row: LegacyValue)=><button
              key={row.type}
              type="button"
              draggable
              onDragStart={(event: LegacyValue)=>beginDrag(event,{kind:'new',type:row.type})}
              onClick={()=>addNode(row.type,80+((editor.nodes.length%4)*220),420)}
              title={row.description||row.type}
            >
              <span>{row.label||row.type}</span>
              <small>{row.type} · {row.phase||'-'}</small>
            </button>)}
          </div>)}
        </div>
      </aside>

      <main className="media-workflow-canvas-pane">
        <div className="media-pane-head canvas-head">
          <div><strong>Workflow Canvas</strong><small>{editor.nodes.length} Nodes · {editor.edges.length} Edges</small></div>
          <div><button type="button" onClick={resetStarter}>Starter 재구성</button><span>{pendingConnection?`${pendingConnection.port.type} 연결 대상 선택 중`:'Output Port를 누른 뒤 Input Port를 선택하세요.'}</span></div>
        </div>
        <div
          className="media-workflow-canvas-scroll"
          ref={canvasRef}
          onDragOver={(event: LegacyValue)=>event.preventDefault()}
          onDrop={dropOnCanvas}
          onClick={()=>setSelectedNodeId('')}
        >
          <div className="media-workflow-canvas" style={{width:CANVAS_WIDTH,height:CANVAS_HEIGHT}}>
            <svg className="media-workflow-edge-layer" width={CANVAS_WIDTH} height={CANVAS_HEIGHT} aria-hidden="true">
              {editor.edges.map((edge: LegacyValue)=>{
                const source=nodeMap[edge.source],target=nodeMap[edge.target]
                if(!source||!target) return null
                const sx=Number(source.x||0)+NODE_WIDTH, sy=Number(source.y||0)+NODE_HEIGHT/2
                const tx=Number(target.x||0), ty=Number(target.y||0)+NODE_HEIGHT/2
                const bend=Math.max(45,Math.abs(tx-sx)*.45)
                return <g key={edge.id} className="media-workflow-edge">
                  <path d={`M ${sx} ${sy} C ${sx+bend} ${sy}, ${tx-bend} ${ty}, ${tx} ${ty}`}/>
                  <text x={(sx+tx)/2} y={(sy+ty)/2-8}>{edge.output_type||''}</text>
                </g>
              })}
            </svg>
            {editor.nodes.map((node: LegacyValue)=>{
              const def=findDef(catalog,node.type)||{inputs:[],outputs:[],label:node.type,category:'MEDIA_PROCESSING'}
              const selected=node.id===selectedNodeId
              return <article
                key={node.id}
                className={`media-canvas-node ${selected?'selected':''}`}
                style={{left:Number(node.x||0),top:Number(node.y||0),width:NODE_WIDTH,minHeight:NODE_HEIGHT}}
                draggable
                onDragStart={(event: LegacyValue)=>beginDrag(event,{kind:'move',id:node.id})}
                onClick={(event: LegacyValue)=>{event.stopPropagation();setSelectedNodeId(node.id)}}
              >
                <div className="media-canvas-node-title"><span>{CATEGORY_META[def.category as keyof typeof CATEGORY_META]?.icon||'◇'}</span><div><strong>{node.label||def.label||node.type}</strong><small>{node.type}</small></div><button type="button" title="Node 삭제" onClick={(event: LegacyValue)=>{event.stopPropagation();removeNode(node.id)}}>×</button></div>
                <div className="media-canvas-node-ports inputs">
                  {(def.inputs||[]).map((port: LegacyValue)=><button key={`${port.name}-${port.type}`} type="button" className="media-port input" title={`${port.name}: ${port.type}`} onClick={(event: LegacyValue)=>{event.stopPropagation();void connectToInput(node,port)}}><i></i><span>{port.name}</span><em>{port.type}</em></button>)}
                </div>
                <div className="media-canvas-node-ports outputs">
                  {(def.outputs||[]).map((port: LegacyValue)=><button key={`${port.name}-${port.type}`} type="button" className={`media-port output ${pendingConnection?.nodeId===node.id&&pendingConnection?.port?.name===port.name?'active':''}`} title={`${port.name}: ${port.type}`} onClick={(event: LegacyValue)=>{event.stopPropagation();setPendingConnection({nodeId:node.id,port});setMessage(`${port.type} Output 선택됨. 연결할 Input Port를 선택하세요.`)}}><em>{port.type}</em><span>{port.name}</span><i></i></button>)}
                </div>
              </article>
            })}
          </div>
        </div>
      </main>

      <aside className="media-node-config-pane">
        <div className="media-pane-head"><strong>Node 설정</strong><small>{selectedNode?.type||'Node를 선택하세요'}</small></div>
        {!selectedNode&&<div className="media-config-empty"><span>◇</span><strong>Canvas에서 Node를 선택하세요.</strong><small>Provider · Model · 크기 · Retry 등 고수준 설정만 편집합니다.</small></div>}
        {selectedNode&&<div className="media-config-form">
          <label><span>Label</span><input value={selectedNode.label||''} onChange={(event: LegacyValue)=>updateNode(selectedNode.id,{label:event.target.value})}/></label>
          <label><span>Provider</span><select value={selectedNode.config?.provider||'AUTO'} onChange={(event: LegacyValue)=>updateNodeConfig('provider',event.target.value)}>{PROVIDERS.map((provider: LegacyValue)=><option key={provider}>{provider}</option>)}</select></label>
          <label><span>Model / Workflow</span><input value={selectedNode.config?.model||''} placeholder="Provider 기본값 또는 모델/Workflow ID" onChange={(event: LegacyValue)=>updateNodeConfig('model',event.target.value)}/></label>
          <div className="media-config-row"><label><span>Width</span><input type="number" min="64" step="64" value={selectedNode.config?.width||1024} onChange={(event: LegacyValue)=>updateNodeConfig('width',Number(event.target.value||0))}/></label><label><span>Height</span><input type="number" min="64" step="64" value={selectedNode.config?.height||1024} onChange={(event: LegacyValue)=>updateNodeConfig('height',Number(event.target.value||0))}/></label></div>
          <label><span>Max Retry</span><input type="number" min="0" max="10" value={selectedNode.config?.max_retry??2} onChange={(event: LegacyValue)=>updateNodeConfig('max_retry',Number(event.target.value||0))}/></label>
          <label><span>Prompt / Instructions</span><textarea value={selectedNode.config?.prompt||''} placeholder="필요한 경우 Node별 지시를 입력합니다." onChange={(event: LegacyValue)=>updateNodeConfig('prompt',event.target.value)}/></label>
          <div className="media-config-contract"><b>{selectedDef?.execution_mode||'SYNC'}</b><span>{selectedDef?.provider_capability||'Provider 독립 Node'}</span><small>{selectedDef?.description||'고수준 Media Workflow Node'}</small></div>
        </div>}
      </aside>
    </div>

    <div className="media-workflow-bottom-grid">
      <section className="media-preview-panel">
        <div className="media-pane-head"><strong>Preview / Job 상태</strong><small>{currentJob?.status||'DESIGN READY'}</small></div>
        <div className="media-preview-body">
          <div className="media-preview-tile source"><span>원본 / 입력</span><strong>{artifacts.length?'Artifact 연결됨':'입력 Artifact 대기'}</strong></div>
          <div className="media-preview-arrow">→</div>
          <div className="media-preview-tile result">
            {currentArtifact&&/^(https?:|data:|blob:)/i.test(String(currentArtifact.uri||''))&&String(currentArtifact.type||'').toUpperCase()==='IMAGE'
              ?<img src={currentArtifact.uri} alt="Media Artifact Preview"/>
              :<><span>생성 결과</span><strong>{currentArtifact?.artifact_id||'실행 후 Preview 표시'}</strong></>}
          </div>
          <div className="media-job-summary"><b>{currentJob?.provider||'Provider 미실행'}</b><span>{currentJob?.status||'EDITOR MODE'}</span><div><i style={{width:`${Math.round(Number(currentJob?.progress||0)*100)}%`}}></i></div><small>{currentJob?`Job ${currentJob.job_id||'-'} · Retry ${currentJob.retry_count||0}/${currentJob.max_retry||0}`:'실제 실행 Job이 기록되면 Queue/Progress/Cancel 상태가 이 영역에 표시됩니다.'}</small></div>
        </div>
      </section>
      <section className={`media-workflow-validation ${validation?.valid===false?'invalid':validation?.valid===true?'valid':''}`}>
        <div className="media-pane-head"><strong>Workflow Validation</strong><small>{validation?.valid===true?'PASS':validation?.valid===false?'FAIL':'미검증'}</small></div>
        <div className="media-validation-body"><strong>{message}</strong>{(validation?.issues||[]).slice(0,5).map((issue: LegacyValue,index: LegacyValue)=><span key={index}>! {issue.message||issue?.reason||JSON.stringify(issue)}</span>)}{contracts&&<small>Backend Contract 연결됨 · Provider Adapter {contracts?.provider_adapter?.methods?.length||contracts?.provider?.methods?.length||6} methods</small>}</div>
      </section>
    </div>
  </section>
}
