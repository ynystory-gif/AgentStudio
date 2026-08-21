import React, { useEffect, useState, useRef } from 'react'
import Editor, { DiffEditor } from '@monaco-editor/react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { api, connectJobs, runtimeInfo } from './api'
import { NotebookEditor } from './components/notebook/NotebookEditor'
import { PdfViewer, PresentationViewer } from './components/viewers/DocumentViewers'
import { MiniBadge, SectionTitle, StatusDot, StudioIcon } from './components/common/CommonUi'
import { FileChangeList, KeyValueGrid, MetricCard, ReportSection, StatusBadge, WorkflowMiniMap } from './components/reports/ReportComponents'
import { AgentStudioArchitecturePanel, GeneratedAgentArchitecturePanel } from './components/architecture/ArchitecturePanels'
import { LlmCatalogPanel } from './components/llm/LlmCatalogPanel'
import { DatabaseBrowserContextMenus, FirestoreBrowserPanel, RedisBrowserPanel, SqlObjectTreePanel } from './components/database/DatabaseBrowsers'
import { TerminalPanel } from './components/terminal/TerminalPanel'
import { OllamaSettingsPanel, RuntimeDatabasePanel, ServicePortSettingsPanel, SystemStatusSummary } from './components/system/SystemRuntimePanels'
import { parseTerminalServerMessage, serializeTerminalClientMessage, terminalCellWidth, terminalNextCharacter, terminalPreviousCharacter } from './utils/terminal'
import { getEditorLanguage, getEditorModelPath, isBinaryPreviewFile, isNotebookFile, isPdfFile, isPresentationFile } from './utils/editor'
import { formatNotebookSqlResult, looksLikeNotebookSqlCode, normalizeNotebookSqlCode } from './utils/notebook'

const AGENTSTUDIO_FRONTEND_VERSION='5.307'

const joinWin = (root, file) => `${root}\\${file}`.replaceAll('\\\\', '\\')
const localIsoDate = () => {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`
}
const localIsoMonth = () => localIsoDate().slice(0,7)
const normalizeProjectRelativePath=(value='')=>String(value||'').replace(/\\/g,'/').replace(/^\/+/, '')
function SystemPage() {
  const [status,setStatus]=useState({})
  const [runtimeLoopStatus,setRuntimeLoopStatus]=useState(null)
  const [settings,setSettings]=useState({})
  const [tests,setTests]=useState({})
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [pgvectorInstall,setPgvectorInstall]=useState(null)
  const [pgvectorInfo,setPgvectorInfo]=useState(null)
  const [pgPathCheck,setPgPathCheck]=useState(null)
  const [pgAdminUser,setPgAdminUser]=useState('postgres')
  const [pgAdminPassword,setPgAdminPassword]=useState('')
  const [agentDbName,setAgentDbName]=useState('theanova_agentstudio')
  const [agentDbUser,setAgentDbUser]=useState('theanova_agentstudio_app')
  const [agentDbPassword,setAgentDbPassword]=useState('')
  const [dbProvision,setDbProvision]=useState(null)
  const [ollamaInstall,setOllamaInstall]=useState(null)
  const [ollamaRuntime,setOllamaRuntime]=useState(null)
  const [ollamaRuntimeBusy,setOllamaRuntimeBusy]=useState(false)
  const [portInfo,setPortInfo]=useState(null)
  const [portCheckBusy,setPortCheckBusy]=useState(false)
  const [machineName,setMachineName]=useState('')
  const [machineNameBusy,setMachineNameBusy]=useState(false)
  const [databaseRuntime,setDatabaseRuntime]=useState(null)
  const [databaseProviderChoice,setDatabaseProviderChoice]=useState('local')
  const [supabaseRuntimeUrl,setSupabaseRuntimeUrl]=useState('')
  const [supabaseLanggraphRuntimeUrl,setSupabaseLanggraphRuntimeUrl]=useState('')
  const [supabaseRuntimeSchema,setSupabaseRuntimeSchema]=useState('theanova_agentstudio')
  const [databaseRuntimeBusy,setDatabaseRuntimeBusy]=useState(false)
  const [supabaseInfoSaveBusy,setSupabaseInfoSaveBusy]=useState(false)
  const [databaseRuntimeResult,setDatabaseRuntimeResult]=useState(null)
  const pgAdminPasswordRef=useRef(null)
  const agentDbPasswordRef=useRef(null)

  const readPgAdminPassword=()=>String(pgAdminPasswordRef.current?.value ?? pgAdminPassword ?? '')
  const readAgentDbPassword=()=>String(agentDbPasswordRef.current?.value ?? agentDbPassword ?? '')

  const refresh=async()=>{
    try{
      const [s,cfg]=await Promise.all([api('/system/status'),api('/settings')])
      setStatus(s); setSettings(cfg); setMachineName(cfg?._machine?.pending_pc_name||cfg?._machine?.pc_name||''); setError('')

      try{
        setOllamaRuntime(await api('/settings/ollama/runtime/status'))
      }catch{
        setOllamaRuntime(null)
      }

      try{
        const dbRuntime=await api('/settings/database-runtime')
        setDatabaseRuntime(dbRuntime)
        setDatabaseProviderChoice(dbRuntime?.selected_provider||dbRuntime?.active_provider||'local')
        setSupabaseRuntimeSchema(String(dbRuntime?.supabase_schema||'theanova_agentstudio'))
      }catch{
        setDatabaseRuntime(null)
      }

      const backendPort=Number(cfg.AGENTSTUDIO_BACKEND_PORT||8000)
      const frontendPort=Number(cfg.AGENTSTUDIO_FRONTEND_PORT||5173)
      const currentFrontendPort=Number(window.location.port||5173)
      try{
        const ports=await api(
          `/system/ports/recommend?backend_port=${backendPort}&frontend_port=${frontendPort}&current_frontend_port=${currentFrontendPort}`
        )
        setPortInfo(ports)
      }catch{
        setPortInfo(null)
      }
    }catch(e){setError(String(e))}
  }

  useEffect(()=>{refresh()},[])

  const valueOf=(key)=>{
    const v=settings[key]
    if(v && typeof v==='object' && 'configured' in v) return ''
    return v ?? ''
  }

  const configured=(key)=>{
    const v=settings[key]
    return !!(v && typeof v==='object' && v.configured)
  }

  const setValue=(key,value)=>setSettings(p=>({...p,[key]:value}))

  const saveGroup=async(keys)=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const values={}
      keys.forEach(k=>{ values[k]=valueOf(k) })
      const r=await api('/settings',{method:'POST',body:JSON.stringify({values})})
      setSettings(r.settings)
      if(keys.includes('DATABASE_URL')){
        const saved=r?.saved_bootstrap?.DATABASE_URL||''
        const target=(()=>{
          try{ const u=new URL(saved.replace('postgresql+asyncpg://','http://').replace('postgresql+psycopg://','http://').replace('postgresql://','http://')); return `${u.username}@${u.hostname}:${u.port||5432}${u.pathname}` }catch{return ''}
        })()
        setMessage(`${r.message||'DB 설정을 저장했습니다.'}${target?` 저장 확인: ${target}`:''}`)
      }else{
        setMessage(r.message)
      }
    }catch(e){setError(String(e))}
    finally{setBusy(false)}
  }

  const saveDatabaseEnv=async()=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const payload={
        database_url:String(valueOf('DATABASE_URL')||'').trim(),
        langgraph_database_url:String(valueOf('LANGGRAPH_DATABASE_URL')||'').trim(),
        postgresql_root:String(valueOf('POSTGRESQL18_ROOT')||'').trim()
      }
      const r=await api('/settings/database-env',{method:'POST',body:JSON.stringify(payload)})
      // 응답도 DB가 아니라 backend/.env에서 재읽은 실제 저장값입니다.
      setSettings(prev=>({
        ...prev,
        DATABASE_URL:r?.saved?.DATABASE_URL ?? payload.database_url,
        LANGGRAPH_DATABASE_URL:r?.saved?.LANGGRAPH_DATABASE_URL ?? payload.langgraph_database_url,
        POSTGRESQL18_ROOT:r?.saved?.POSTGRESQL18_ROOT ?? payload.postgresql_root
      }))
      setMessage(`${r.message||'DB 연결 설정을 .env에 저장했습니다.'} 저장 위치: ${r.env_path||'backend/.env'}`)
    }catch(e){
      setError(String(e))
    }finally{setBusy(false)}
  }

  const saveSupabaseRuntimeInfo=async()=>{
    setSupabaseInfoSaveBusy(true); setMessage(''); setError(''); setDatabaseRuntimeResult(null)
    try{
      const r=await api('/settings/database-runtime/supabase/save',{
        method:'POST',
        body:JSON.stringify({
          database_url:String(supabaseRuntimeUrl||'').trim(),
          langgraph_database_url:String(supabaseLanggraphRuntimeUrl||'').trim(),
          schema:String(supabaseRuntimeSchema||'theanova_agentstudio').trim()
        })
      })
      setDatabaseRuntimeResult(r)
      setMessage(r?.message||'Supabase PostgreSQL 연결 정보를 저장했습니다.')
      // 비밀번호가 포함될 수 있는 URL 원문은 저장 성공 후 브라우저 입력 상태에서도 제거합니다.
      setSupabaseRuntimeUrl('')
      setSupabaseLanggraphRuntimeUrl('')
      setDatabaseRuntime(await api('/settings/database-runtime'))
    }catch(e){
      setError(String(e))
      setDatabaseRuntimeResult({ok:false,message:String(e)})
    }finally{
      setSupabaseInfoSaveBusy(false)
    }
  }

  const activateRuntimeDatabase=async()=>{
    setDatabaseRuntimeBusy(true); setMessage(''); setError(''); setDatabaseRuntimeResult(null)
    try{
      const payload={
        provider:databaseProviderChoice,
        supabase_database_url:String(supabaseRuntimeUrl||'').trim(),
        supabase_langgraph_database_url:String(supabaseLanggraphRuntimeUrl||'').trim(),
        supabase_db_schema:String(supabaseRuntimeSchema||'theanova_agentstudio').trim(),
        initialize_schema:databaseProviderChoice==='supabase'
      }
      const r=await api('/settings/database-runtime/activate',{method:'POST',body:JSON.stringify(payload)})
      setDatabaseRuntimeResult(r)
      setMessage(r?.message||'Runtime DB 전환을 완료했습니다.')
      const next=await api('/settings/database-runtime')
      setDatabaseRuntime(next)
      setDatabaseProviderChoice(next?.selected_provider||next?.active_provider||databaseProviderChoice)
      await refresh()
    }catch(e){
      setError(String(e))
      setDatabaseRuntimeResult({ok:false,message:String(e)})
    }finally{
      setDatabaseRuntimeBusy(false)
    }
  }

  const initializeSupabaseRuntimeSchema=async()=>{
    setDatabaseRuntimeBusy(true); setMessage(''); setError(''); setDatabaseRuntimeResult(null)
    try{
      const r=await api('/settings/database-runtime/supabase/initialize-schema',{
        method:'POST',
        body:JSON.stringify({
          database_url:String(supabaseRuntimeUrl||'').trim(),
          langgraph_database_url:String(supabaseLanggraphRuntimeUrl||'').trim(),
          schema:String(supabaseRuntimeSchema||'theanova_agentstudio').trim()
        })
      })
      setDatabaseRuntimeResult(r)
      setMessage(r?.message||'Supabase 스키마 준비/검증을 완료했습니다.')
      setDatabaseRuntime(await api('/settings/database-runtime'))
    }catch(e){
      setError(String(e))
      setDatabaseRuntimeResult({ok:false,message:String(e)})
    }finally{
      setDatabaseRuntimeBusy(false)
    }
  }

  const downloadSupabaseSchemaScript=()=>{
    const base=runtimeInfo().apiBase
    window.open(`${base}/settings/database-runtime/supabase/schema-script`,'_blank','noopener,noreferrer')
  }

  const saveMachineName=async()=>{
    const nextName=String(machineName||'').trim()
    if(!nextName){
      setError('PC 이름을 입력하세요.')
      return
    }
    setMachineNameBusy(true); setMessage(''); setError('')
    try{
      const r=await api('/settings/machine-name',{
        method:'POST',
        body:JSON.stringify({pc_name:nextName})
      })
      if(r?.settings) setSettings(r.settings)
      setMachineName(r?.pending_pc_name||r?.pc_name||r?.settings?._machine?.pending_pc_name||r?.settings?._machine?.pc_name||nextName)
      setMessage(r?.message||`PC 이름을 ${nextName}(으)로 저장했습니다.`)
    }catch(e){
      setError(String(e))
    }finally{
      setMachineNameBusy(false)
    }
  }

  const checkPortRecommendations=async()=>{
    setPortCheckBusy(true)
    setError('')
    try{
      const backendPort=Number(valueOf('AGENTSTUDIO_BACKEND_PORT')||8000)
      const frontendPort=Number(valueOf('AGENTSTUDIO_FRONTEND_PORT')||5173)

      if(!Number.isInteger(backendPort)||backendPort<1024||backendPort>65535){
        throw new Error('Backend 포트는 1024~65535 사이의 숫자를 입력하세요.')
      }
      if(!Number.isInteger(frontendPort)||frontendPort<1024||frontendPort>65535){
        throw new Error('Frontend 포트는 1024~65535 사이의 숫자를 입력하세요.')
      }

      const currentFrontendPort=Number(window.location.port||5173)
      const result=await api(
        `/system/ports/recommend?backend_port=${backendPort}&frontend_port=${frontendPort}&current_frontend_port=${currentFrontendPort}`
      )
      setPortInfo(result)
      return result
    }catch(e){
      setError(String(e))
      return null
    }finally{
      setPortCheckBusy(false)
    }
  }

  const applyRecommendedPorts=async()=>{
    const result=portInfo||await checkPortRecommendations()
    if(!result) return
    setValue('AGENTSTUDIO_BACKEND_PORT',String(result.backend?.recommended||8000))
    setValue('AGENTSTUDIO_FRONTEND_PORT',String(result.frontend?.recommended||5173))
    setMessage('추천 포트를 입력했습니다. 포트 설정 저장 후 SYSTEM_ADMIN.cmd를 다시 실행하면 적용됩니다.')
  }

  const savePortSettings=async()=>{
    const backendPort=Number(valueOf('AGENTSTUDIO_BACKEND_PORT')||8000)
    const frontendPort=Number(valueOf('AGENTSTUDIO_FRONTEND_PORT')||5173)
    if(backendPort===frontendPort){
      setError('Backend와 Frontend는 서로 다른 포트를 사용해야 합니다.')
      return
    }
    const result=await checkPortRecommendations()
    if(!result) return

    setBusy(true); setMessage(''); setError('')
    try{
      const r=await api('/settings',{
        method:'POST',
        body:JSON.stringify({values:{
          AGENTSTUDIO_BACKEND_PORT:String(backendPort),
          AGENTSTUDIO_FRONTEND_PORT:String(frontendPort)
        }})
      })
      setSettings(r.settings)
      setMessage(
        '서비스 포트를 저장했습니다. 다음 SYSTEM_ADMIN.cmd 재실행부터 적용됩니다. '+
        '지정 포트가 다른 프로그램에서 사용 중이면 해당 프로그램을 종료하지 않고 사용 가능한 다음 포트로 안전하게 대체합니다.'
      )
      await checkPortRecommendations()
    }catch(e){
      setError(String(e))
    }finally{
      setBusy(false)
    }
  }

  const portStateLabel=(state)=>({
    current:'현재 AgentStudio 사용 중',
    available:'사용 가능',
    in_use:'다른 프로그램이 사용 중',
    conflict_with_backend:'Backend 포트와 중복'
  }[state]||state||'-')

  const testOne=async(name)=>{
    setBusy(true)
    try{
      const options={method:'POST'}
      if(name==='postgresql' || name==='pgvector'){
        options.body=JSON.stringify({database_url:String(valueOf('DATABASE_URL')||'').trim()})
      }
      const r=await api(`/settings/test/${name}`,options)
      setTests(p=>({...p,[name]:r}))
    }catch(e){
      setTests(p=>({...p,[name]:{ok:false,message:String(e)}}))
    }finally{setBusy(false)}
  }

  const testAll=async()=>{
    setBusy(true)
    try{ setTests(await api('/settings/test-all',{method:'POST'})) }
    catch(e){setError(String(e))}
    finally{setBusy(false)}
  }


  const loadPgvectorInfo=async()=>{
    try{setPgvectorInfo(await api(`/settings/pgvector/windows18/info?postgresql_root=${encodeURIComponent(valueOf('POSTGRESQL18_ROOT'))}`))}
    catch(e){setPgvectorInfo({error:String(e)})}
  }


  const pollPgvectorJob=async(jobId)=>{
    let unchanged=0
    let lastSignature=''

    for(let i=0;i<240;i++){
      try{
        const j=await api(`/jobs/${jobId}`)
        const signature=`${j.status}|${j.progress}|${j.message}`

        if(signature===lastSignature) unchanged++
        else unchanged=0
        lastSignature=signature

        setPgvectorInstall(current=>({
          ...(current||{}),
          job_id:jobId,
          status:j.status,
          progress:j.progress||0,
          message:
            unchanged>=15 && ['QUEUED','RUNNING'].includes(j.status)
              ? `${j.message} (응답 대기 중 - Backend 작업 상태를 확인하고 있습니다.)`
              : (j.message||''),
          result:j.result||{}
        }))

        if(['SUCCESS','FAILED','CANCELLED'].includes(j.status)){
          if(j.status==='SUCCESS') setPgAdminPassword('')
          setBusy(false)
          if(j.status==='SUCCESS'){
            setTimeout(()=>testOne('pgvector'),300)
          }
          return
        }
      }catch(e){
        setPgvectorInstall(current=>({
          ...(current||{}),
          message:`Job 상태 확인 중 오류: ${String(e)}`
        }))
      }

      await new Promise(r=>setTimeout(r,1000))
    }

    setBusy(false)
    setPgvectorInstall(current=>({
      ...(current||{}),
      status:'FAILED',
      message:'설치 작업 상태 확인 제한시간을 초과했습니다.'
    }))
  }

  const installPgvector18=async()=>{
    if(!pgAdminUser.trim()){
      setPgvectorInstall({status:'FAILED',progress:0,message:'PostgreSQL 관리자 사용자명을 입력하세요.'})
      return
    }
    const effectiveAdminPassword=readPgAdminPassword()
    if(!effectiveAdminPassword){
      setPgvectorInstall({status:'FAILED',progress:0,message:'PostgreSQL 관리자 비밀번호를 입력하세요.'})
      return
    }

    const confirmed=window.confirm(`PostgreSQL 18용 Windows pgvector를 다운로드하고 설치합니다.

설치 중 Windows 관리자 권한(UAC) 창이 나오면 허용을 선택해야 합니다.
계속하시겠습니까?`)
    if(!confirmed) return

    setBusy(true)
    setPgvectorInstall({
      status:'QUEUED',
      progress:0,
      message:'설치 작업을 준비하고 있습니다.'
    })

    try{
      // 긴 설치 작업은 Backend Job으로 시작하고 즉시 Job ID를 받습니다.
      const job=await api('/settings/pgvector/windows18/install',{method:'POST',body:JSON.stringify({postgresql_root:valueOf('POSTGRESQL18_ROOT'),admin_user:pgAdminUser,admin_password:effectiveAdminPassword})})
      setPgvectorInstall({
        status:job.status,
        progress:job.progress||0,
        message:job.message||'설치 작업을 시작했습니다.',
        job_id:job.id
      })
      pollPgvectorJob(job.id)
    }catch(e){
      setPgvectorInstall({
        status:'FAILED',
        progress:0,
        message:'설치 Job 시작 실패: '+String(e)
      })
      setBusy(false)
    }
  }


  const validatePgPath=async()=>{
    try{
      const r=await api('/settings/pgvector/windows18/validate-path',{
        method:'POST',
        body:JSON.stringify({postgresql_root:valueOf('POSTGRESQL18_ROOT'),admin_user:pgAdminUser,admin_password:readPgAdminPassword()})
      })
      setPgPathCheck(r)
    }catch(e){
      setPgPathCheck({ok:false,message:String(e)})
    }
  }

  const testPostgresqlAdmin=async()=>{
    const effectiveAdminPassword=readPgAdminPassword()
    setBusy(true)
    try{
      const r=await api('/settings/test/postgresql-admin',{
        method:'POST',
        body:JSON.stringify({admin_user:pgAdminUser,admin_password:effectiveAdminPassword})
      })
      setTests(p=>({...p,postgresqlAdmin:r}))
    }catch(e){
      setTests(p=>({...p,postgresqlAdmin:{ok:false,message:String(e)}}))
    }finally{
      setBusy(false)
    }
  }


  const provisionAgentstudioDb=async()=>{
    const effectiveAdminPassword=readPgAdminPassword()
    const effectiveAppPassword=readAgentDbPassword()
    if(!pgAdminUser.trim() || !effectiveAdminPassword){
      setDbProvision({ok:false,message:'PostgreSQL 관리자 사용자/비밀번호를 입력하세요.'})
      return
    }
    const missing=[]
    if(!agentDbName.trim()) missing.push('DB 이름')
    if(!agentDbUser.trim()) missing.push('앱 사용자')
    if(!effectiveAppPassword) missing.push('앱 비밀번호')
    if(missing.length){
      setDbProvision({ok:false,message:`입력되지 않은 항목: ${missing.join(', ')}`})
      return
    }

    if(!window.confirm(
      `AgentStudio 전용 DB "${agentDbName}"를 생성하고 권한과 pgvector를 설정합니다.\n\n` +
      `앱 사용자: ${agentDbUser}\n계속하시겠습니까?`
    )) return

    setBusy(true)
    setDbProvision({ok:null,message:'AgentStudio DB 생성 및 권한 설정 중...'})

    try{
      const r=await api('/settings/database/provision-agentstudio',{
        method:'POST',
        body:JSON.stringify({
          postgresql_root:valueOf('POSTGRESQL18_ROOT'),
          admin_user:pgAdminUser,
          admin_password:effectiveAdminPassword,
          app_user:agentDbUser,
          app_password:effectiveAppPassword,
          database_name:agentDbName
        })
      })
      setDbProvision(r)
      if(r?.ok){
        setAgentDbPassword('')
        setPgAdminPassword('')
        await refresh()
      }
    }catch(e){
      setDbProvision({ok:false,message:String(e)})
    }finally{
      setBusy(false)
    }
  }


  const refreshOllamaRuntime=async()=>{
    try{
      const runtime=await api('/settings/ollama/runtime/status')
      setOllamaRuntime(runtime)
      return runtime
    }catch(e){
      setOllamaRuntime({ok:false,message:String(e),running:false,installed:false})
      return null
    }
  }

  const startOllamaRuntime=async()=>{
    setOllamaRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/ollama/runtime/start',{method:'POST'})
      setOllamaRuntime(result)
      if(result.ok){
        setMessage(result.message||'Ollama 서버가 시작되었습니다.')
        setTimeout(()=>testOne('ollama'),300)
      }else{
        setError(result.message||'Ollama 서버 시작에 실패했습니다.')
      }
    }catch(e){
      setError('Ollama 서버 시작 실패: '+String(e))
    }finally{
      setOllamaRuntimeBusy(false)
    }
  }

  const stopOllamaRuntime=async()=>{
    if(!window.confirm('AgentStudio가 시작한 Ollama 서버를 종료하시겠습니까?')) return
    setOllamaRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/ollama/runtime/stop',{method:'POST'})
      setOllamaRuntime(result)
      if(result.ok){
        setMessage(result.message||'Ollama 서버를 종료했습니다.')
      }else{
        setError(result.message||'Ollama 서버 종료에 실패했습니다.')
      }
    }catch(e){
      setError('Ollama 서버 종료 실패: '+String(e))
    }finally{
      setOllamaRuntimeBusy(false)
    }
  }

  const pollOllamaJob=async(jobId)=>{
    for(let i=0;i<600;i++){
      try{
        const j=await api(`/jobs/${jobId}`)
        setOllamaInstall(current=>({
          ...(current||{}),
          job_id:jobId,
          status:j.status,
          progress:j.progress||0,
          message:j.message||'',
          result:j.result||{}
        }))
        if(['SUCCESS','FAILED','CANCELLED'].includes(j.status)){
          setBusy(false)
          if(j.status==='SUCCESS'){
            setTimeout(()=>{ refreshOllamaRuntime(); testOne('ollama') },1000)
          }
          return
        }
      }catch(e){
        setOllamaInstall(p=>({...p,message:'설치 상태 확인 실패: '+String(e)}))
      }
      await new Promise(r=>setTimeout(r,1000))
    }
    setBusy(false)
    setOllamaInstall({status:'FAILED',progress:0,message:'Ollama 설치 작업 확인 시간이 초과되었습니다.'})
  }

  const installOllama=async()=>{
    if(!window.confirm(
      'Ollama를 설치합니다. 공용 모델 경로가 설정되어 있으면 해당 경로에 모델을 저장하고, 비어 있으면 Ollama 기본 모델 경로를 사용합니다. 계속하시겠습니까?'
    )) return

    setBusy(true)
    setOllamaInstall({status:'QUEUED',progress:0,message:'Ollama 설치 작업을 준비합니다.'})

    try{
      const job=await api('/settings/ollama/windows/install',{
        method:'POST',
        body:JSON.stringify({common_models_root:valueOf('COMMON_MODELS_ROOT')})
      })
      setOllamaInstall({
        job_id:job.id,
        status:job.status,
        progress:job.progress||0,
        message:job.message||'설치 작업을 시작했습니다.'
      })
      pollOllamaJob(job.id)
    }catch(e){
      setBusy(false)
      setOllamaInstall({status:'FAILED',progress:0,message:'Ollama 설치 시작 실패: '+String(e)})
    }
  }


  const cancelSystemJob=async(jobId,label='작업')=>{
    if(!jobId) return
    try{
      await api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'})
      setMessage(`${label} 실행 중지 요청을 보냈습니다.`)
      setBusy(false)
    }catch(e){
      setError(`${label} 실행 중지 실패: ${String(e)}`)
    }
  }


  const chooseFolder=async(name,label)=>{
    try{
      const r=await api('/system/pick-folder',{
        method:'POST',
        body:JSON.stringify({
          title:`${label} 선택`,
          initial_path:valueOf(name)
        })
      })
      if(r.ok && !r.cancelled && r.path){
        setValue(name,r.path)
      }
    }catch(e){
      setError('경로 선택 실패: '+String(e))
    }
  }

  const renderPathField=(label,name,placeholder='')=><label className="setting-field">
    <span>{label}</span>
    <div className="path-input-row">
      <input
        type="text"
        value={valueOf(name)}
        placeholder={placeholder}
        onChange={e=>setValue(name,e.target.value)}
      />
      <button
        type="button"
        className="path-find-button"
        onClick={()=>chooseFolder(name,label)}
      >경로 찾기</button>
    </div>
  </label>


  const migrateSettingsToDb=async()=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const r=await api('/settings/migrate-to-db',{method:'POST'})
      if(r?.ok===false){
        setMessage(r?.message||'공용 DB 연결 복구 후 다시 동기화하세요.')
      }else{
        setMessage(r?.message||`설정 DB 동기화 완료: 신규 ${r.migrated||0}개 / 수정 ${r.updated||0}개`)
      }
      await refresh()
    }catch(e){
      setError('설정 DB 이관 실패: '+String(e))
    }finally{
      setBusy(false)
    }
  }

  const renderField=(label,name,type='text',placeholder='')=><label className="setting-field">
    <span>{label}</span>
    <input
      type={type}
      value={valueOf(name)}
      placeholder={configured(name) ? '설정됨 - 변경할 때만 새 값을 입력' : placeholder}
      onChange={e=>setValue(name,e.target.value)}
    />
  </label>

  const renderTestResult=(name)=>{
    const r=tests[name]
    if(!r) return null
    return <div className={r.ok?'test-result okbox':'test-result badbox'}>
      <div>{r.message}</div>
      {r.target&&<div><b>연결 대상:</b> {`${r.target.user||'?'}@${r.target.host||'?'}:${r.target.port||'?'} / ${r.target.database||'?'}`}</div>}
      {!r.ok&&r.sqlstate&&<div><b>PostgreSQL 코드:</b> {r.sqlstate}</div>}
      {!r.ok&&r.error_type&&<div><b>오류 유형:</b> {r.error_type}</div>}
      {!r.ok&&r.url&&<div><b>연결 URL:</b> {r.url}</div>}
      {!r.ok&&r.port_open!==undefined&&<div><b>포트 상태:</b> {r.port_open?'열림':'연결 안 됨'}</div>}
      {!r.ok&&r.ollama_exe&&<div><b>Ollama 실행 파일:</b> {r.ollama_exe}</div>}
      {!r.ok&&r.recommendation&&<div><b>확인 사항:</b> {r.recommendation}</div>}
      {!r.ok&&r.log_path&&<div className="connection-log-path">
        <b>로그 파일:</b>
        <code>{r.log_path}</code>
        <button
          type="button"
          onClick={()=>navigator.clipboard?.writeText?.(r.log_path)}
          title="로그 파일 경로 복사"
        >경로 복사</button>
      </div>}
    </div>
  }

  const checkRuntimeLoop=async()=>{
    try{
      const result=await api('/health/runtime')
      setRuntimeLoopStatus(result)
      return result
    }catch(e){
      setRuntimeLoopStatus({
        ok:false,
        message:String(e)
      })
      return null
    }
  }


  return <div className="system-page"><div className="system-card system-card-wide">
    <div className="system-head">
      <div><h1>THEANOVA AgentStudio - 시스템 관리</h1>
      <p>설정 입력 → 저장 → 연결 테스트 순서로 관리합니다.</p>
      <div className="hint-box settings-storage-note">
        일반 PC별 설정은 공용 PostgreSQL <b>app_settings</b>를 사용하고 각 PC의 <b>.env</b>를 fallback cache로 유지합니다.
        단, <b>DATABASE URL / LangGraph DB URL은 DB 연결 자체에 필요한 bootstrap 정보이므로 예외적으로 backend/.env에만 저장</b>하며 app_settings에는 저장하지 않습니다.
      </div>
      {settings?._storage?.db_connected===false&&<div className="settings-db-offline-warning">
        <strong>공용 DB 연결 안 됨 · 현재 .env fallback 모드</strong>
        <span>DATABASE URL의 호스트/포트/사용자/비밀번호를 확인하고 [DB 설정 .env 저장] → [AgentStudio DB 연결 테스트] 순서로 복구하세요.</span>
      </div>}
      <div className="machine-scope-info machine-scope-editable">
        <div className="machine-scope-title">
          <span>AgentStudio PC 이름</span>
          <small>공용 DB에서 환경설정을 구분하는 유니크 이름입니다. 사용자가 수정할 수 있습니다.</small>
        </div>
        <div className="machine-name-edit-row">
          <input
            value={machineName}
            maxLength={64}
            onChange={e=>setMachineName(e.target.value)}
            onKeyDown={e=>{if(e.key==='Enter'&&!e.nativeEvent?.isComposing){e.preventDefault();saveMachineName()}}}
            placeholder="예: OFFICE-PC-01"
            aria-label="AgentStudio PC 이름"
          />
          <button type="button" disabled={machineNameBusy} onClick={saveMachineName}>
            {machineNameBusy?'확인 중...':'PC 이름 저장'}
          </button>
        </div>
        <div className="machine-scope-meta">
          <span>Windows PC 이름</span>
          <strong>{settings?._machine?.system_host_name||'확인 중...'}</strong>
          <span className={`machine-unique-badge ${settings?._machine?.pending_pc_name?'pending':settings?._machine?.unique_verified?'':'unverified'}`}>
            {settings?._machine?.pending_pc_name?'검증 대기':settings?._machine?.unique_verified?'UNIQUE':'DB 확인 필요'}
          </span>
        </div>
        {settings?._machine?.pending_pc_name&&<small>요청 PC 이름: <b>{settings._machine.pending_pc_name}</b> · 공용 DB 연결 후 중복 검증이 완료되면 자동 적용됩니다.</small>}
        {!settings?._machine?.pending_pc_name&&<small>환경 설정 기준: PC_NAME + 설정 Key · .env: AGENTSTUDIO_PC_NAME · 중복 이름은 저장되지 않습니다.</small>}
      </div>
      <div className="runtime-port-info">
        API: {runtimeInfo().apiBase} · Frontend: {window.location.origin}
      </div>
      </div>
      <div className="button-row">
        <button onClick={refresh}>설정 다시 읽기</button>
        <button disabled={busy} onClick={migrateSettingsToDb}>설정 DB 이관</button>
        <button onClick={testAll}>전체 연결 테스트</button>
        <button onClick={()=>location.href='/'}>AgentStudio 열기</button>
      </div>
    </div>

    {message&&<div className="success-box">{message}</div>}
    {error&&<div className="error">{error}</div>}

    <div className="settings-sections">
      <ServicePortSettingsPanel
        busy={busy}
        portCheckBusy={portCheckBusy}
        portInfo={portInfo}
        runtimeApiBase={runtimeInfo().apiBase}
        frontendOrigin={window.location.origin}
        valueOf={valueOf}
        setValue={setValue}
        portStateLabel={portStateLabel}
        onCheckRecommendations={checkPortRecommendations}
        onApplyRecommendations={applyRecommendedPorts}
        onSave={savePortSettings}
      />

      <section className="settings-panel settings-panel-wide">
        <h2>기본 경로 설정</h2>
        <div className="hint-box">
          신규 에이전트 생성 시 개별 경로를 입력하지 않으면 아래 기본 경로를 사용합니다.
        </div>
        <div className="two-col-fields">
          {renderPathField("프로젝트 기본 경로","DEFAULT_PROJECT_ROOT","Agent 프로젝트 기본 폴더")}
          {renderPathField("Cache 기본 경로","DEFAULT_CACHE_ROOT","비우면 프로젝트경로\\\\cache")}
          {renderPathField("Temp 기본 경로","DEFAULT_TEMP_ROOT","비우면 프로젝트경로\\\\temp")}
          {renderPathField("Output 기본 경로","DEFAULT_OUTPUT_ROOT","비우면 프로젝트경로\\\\output")}
          {renderPathField("공용 모델 경로","COMMON_MODELS_ROOT","비우면 프로젝트경로\\\\models")}
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup([
            'DEFAULT_PROJECT_ROOT','DEFAULT_CACHE_ROOT','DEFAULT_TEMP_ROOT',
            'DEFAULT_OUTPUT_ROOT','COMMON_MODELS_ROOT'
          ])}>기본 경로 저장</button>
        </div>
      </section>

      <section className="settings-panel settings-panel-wide weather-settings-panel">
        <h2>홈 날씨 설정</h2>
        <div className="hint-box">
          메인 화면에 오늘의 아침·점심·저녁·밤 날씨를 표시합니다. 현재 위치 사용을 켜면 브라우저 위치 권한을 사용하고,
          권한이 없거나 끈 경우 아래 기본 지역을 사용합니다. 추가 지역은 세미콜론(;)으로 구분해 최대 4개까지 표시합니다. 오늘 한 번 조회한 날씨는 로컬 캐시에 저장하고 같은 날에는 저장된 데이터를 우선 사용합니다.
        </div>
        <label className="setting-checkbox-row">
          <input
            type="checkbox"
            checked={String(valueOf('WEATHER_AUTO_LOCATION')||'true').toLowerCase()!=='false'}
            onChange={e=>setValue('WEATHER_AUTO_LOCATION',e.target.checked?'true':'false')}
          />
          <span>메인 화면에서 현재 위치 날씨 사용</span>
        </label>
        <div className="two-col-fields">
          {renderField("기본 날씨 지역","WEATHER_LOCATION","text","예: 부천시, 서울, Busan")}
          {renderField("추가 지역","WEATHER_EXTRA_LOCATIONS","text","예: 부일로815번길 36; 인천; 부산")}
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup([
            'WEATHER_AUTO_LOCATION','WEATHER_LOCATION','WEATHER_EXTRA_LOCATIONS'
          ])}>날씨 설정 저장</button>
        </div>
      </section>

      <div className="settings-balanced-columns">
        <div className="settings-column settings-column-left">
      <section className="settings-panel">
        <h2>PostgreSQL / LangGraph</h2>

        <RuntimeDatabasePanel
          providerChoice={databaseProviderChoice}
          runtime={databaseRuntime}
          result={databaseRuntimeResult}
          supabaseRuntimeUrl={supabaseRuntimeUrl}
          supabaseLanggraphRuntimeUrl={supabaseLanggraphRuntimeUrl}
          supabaseRuntimeSchema={supabaseRuntimeSchema}
          runtimeBusy={databaseRuntimeBusy}
          infoSaveBusy={supabaseInfoSaveBusy}
          onProviderChoice={setDatabaseProviderChoice}
          onSupabaseRuntimeUrl={setSupabaseRuntimeUrl}
          onSupabaseLanggraphRuntimeUrl={setSupabaseLanggraphRuntimeUrl}
          onSupabaseRuntimeSchema={setSupabaseRuntimeSchema}
          onSaveSupabaseInfo={saveSupabaseRuntimeInfo}
          onInitializeSupabaseSchema={initializeSupabaseRuntimeSchema}
          onDownloadSupabaseSchema={downloadSupabaseSchemaScript}
          onActivateRuntimeDatabase={activateRuntimeDatabase}
        />

        {renderField("로컬 DATABASE URL (기본 / Control DB)","DATABASE_URL","text","")}
        {renderField("로컬 LangGraph DB URL","LANGGRAPH_DATABASE_URL","text","")}
        {renderPathField("PostgreSQL 18 설치 경로","POSTGRESQL18_ROOT","PostgreSQL 18이 설치된 폴더를 입력하세요.")}
        <label className="setting-field">
          <span>PostgreSQL 관리자 사용자</span>
          <input value={pgAdminUser} onChange={e=>setPgAdminUser(e.target.value)} placeholder="예: postgres"/>
        </label>
        <label className="setting-field">
          <span>PostgreSQL 관리자 비밀번호 (저장하지 않음)</span>
          <input ref={pgAdminPasswordRef} type="password" value={pgAdminPassword} onInput={e=>setPgAdminPassword(e.currentTarget.value)} onChange={e=>setPgAdminPassword(e.target.value)} autoComplete="new-password" placeholder="DB 생성/pgvector 관리자 작업에만 사용"/>
        </label>
        <div className="hint-box credential-scope-hint">
          <b>비밀번호 사용 범위:</b> [관리자 계정 테스트/전용 DB 생성/pgvector 설치]는 위 관리자 비밀번호를 사용합니다.
          [AgentStudio DB 연결 테스트/AgentStudio DB pgvector 테스트]는 <b>화면에 현재 입력되어 있는 DATABASE URL</b>의 사용자/비밀번호를 즉시 사용합니다.
          DB 설정 저장을 먼저 누르지 않아도 현재 입력값으로 테스트합니다. 두 비밀번호는 서로 다를 수 있습니다.
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={testPostgresqlAdmin}>관리자 계정 테스트</button>
        </div>
        {renderTestResult('postgresqlAdmin')}
        <div className="provision-box">
          <h3>AgentStudio 전용 DB 생성</h3>
          <label className="setting-field">
            <span>데이터베이스 이름</span>
            <input value={agentDbName} onChange={e=>setAgentDbName(e.target.value)}/>
          </label>
          <label className="setting-field">
            <span>AgentStudio 앱 사용자</span>
            <input value={agentDbUser} onChange={e=>setAgentDbUser(e.target.value)}/>
          </label>
          <label className="setting-field">
            <span>AgentStudio 앱 비밀번호 (저장하지 않음)</span>
            <input ref={agentDbPasswordRef} type="password" value={agentDbPassword} onInput={e=>setAgentDbPassword(e.currentTarget.value)} onChange={e=>setAgentDbPassword(e.target.value)} autoComplete="new-password"/>
          </label>
          <button className="primary-install" disabled={busy} onClick={provisionAgentstudioDb}>
            theanova_agentstudio DB 생성 + pgvector 설치 + 권한 + 테이블 초기화
          </button>
          {dbProvision&&<div className={
            dbProvision.ok===true ? 'test-result okbox' :
            dbProvision.ok===false ? 'test-result badbox' :
            'test-result install-running'
          }>
            {dbProvision.message}
            {dbProvision.database_url&&<div>DATABASE URL: {dbProvision.database_url}</div>}
            {dbProvision.langgraph_database_url&&<div>LangGraph DB URL: {dbProvision.langgraph_database_url}</div>}
            {dbProvision.table_count!==undefined&&<div>생성/확인된 테이블 수: {dbProvision.table_count}</div>}
            {dbProvision.agentstudio_tables?.length>0&&<details>
              <summary>AgentStudio 테이블 ({dbProvision.agentstudio_tables.length})</summary>
              <div className="table-list">{dbProvision.agentstudio_tables.join(', ')}</div>
            </details>}
            {dbProvision.langgraph_tables?.length>0&&<details>
              <summary>LangGraph 테이블 ({dbProvision.langgraph_tables.length})</summary>
              <div className="table-list">{dbProvision.langgraph_tables.join(', ')}</div>
            </details>}
          </div>}
        </div>

        <div className="hint-box">
          <b>저장 위치:</b> DATABASE URL과 LangGraph DB URL은 DB 연결 이전에 필요한 bootstrap 설정이므로 <b>backend/.env에만 저장</b>합니다.
          PostgreSQL app_settings에는 저장하지 않습니다. PostgreSQL이 연결되지 않은 상태에서도 저장할 수 있습니다.
          PostgreSQL 관리자 비밀번호와 AgentStudio 앱 비밀번호는 저장하지 않습니다.
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={saveDatabaseEnv}>DB 설정 .env 저장</button>
          <button onClick={()=>testOne('postgresql')}>AgentStudio DB 연결 테스트</button>
          <button type="button" onClick={checkRuntimeLoop}>Event Loop 확인</button>
          <button onClick={()=>testOne('pgvector')}>AgentStudio DB pgvector 테스트</button>
          {runtimeLoopStatus&&<div className="runtime-loop-status">
            Event Loop: {runtimeLoopStatus.event_loop||runtimeLoopStatus.message}
            {runtimeLoopStatus.is_selector===true&&' · Selector 정상'}
            {runtimeLoopStatus.is_proactor===true&&' · Proactor 오류'}
          </div>}
          <button disabled={busy} onClick={()=>saveGroup(['POSTGRESQL18_ROOT'])}>PostgreSQL 경로 저장</button>
          <button onClick={validatePgPath}>PostgreSQL 경로 확인</button>
          <button className="primary-install" disabled={busy || (pgvectorInstall && ['QUEUED','RUNNING'].includes(pgvectorInstall.status))} onClick={installPgvector18}>{pgvectorInstall && ['QUEUED','RUNNING'].includes(pgvectorInstall.status) ? 'pgvector 설치 진행 중...' : 'PostgreSQL 18 x64 pgvector 다운로드 및 설치'}</button>
          {pgvectorInstall?.job_id&&['QUEUED','RUNNING'].includes(pgvectorInstall.status)&&<button className="execution-stop-button" onClick={()=>cancelSystemJob(pgvectorInstall.job_id,'pgvector 설치')}>■ 실행 정지</button>}
          <button onClick={loadPgvectorInfo}>설치 패키지 정보</button>
        </div>
        {renderTestResult("postgresql")}{renderTestResult("pgvector")}
        {pgPathCheck&&<div className={pgPathCheck.ok?'test-result okbox':'test-result badbox'}>
          {pgPathCheck.message}
          {pgPathCheck.psql&&<div>psql.exe: {pgPathCheck.psql}</div>}
          {pgPathCheck.version&&<div>{pgPathCheck.version}</div>}
        </div>}
        {pgvectorInfo&&<div className="install-info">
          <b>PostgreSQL 경로:</b> {pgvectorInfo.postgresql_root||'자동 탐지 실패'}<br/>
          <b>패키지:</b> {pgvectorInfo.release?.release_name||pgvectorInfo.error||'-'}<br/>
          {pgvectorInfo.release?.asset_name&&<><b>파일:</b> {pgvectorInfo.release.asset_name}</>}
        </div>}
        {pgvectorInstall&&<div className={
          pgvectorInstall.status==='SUCCESS'
            ?'test-result okbox'
            :pgvectorInstall.status==='FAILED'
              ?'test-result badbox'
              :'test-result install-running'
        }>
          <div><b>설치 상태:</b> {pgvectorInstall.status}</div>
          <progress max="100" value={pgvectorInstall.progress||0}/>
          <div>{pgvectorInstall.message}</div>
          {pgvectorInstall.result?.release?.release_name&&
            <div>설치 패키지: {pgvectorInstall.result.release.release_name}</div>}
          {pgvectorInstall.result?.postgresql_root&&
            <div>설치 경로: {pgvectorInstall.result.postgresql_root}</div>}
          {pgvectorInstall.result?.traceback&&
            <details><summary>상세 오류</summary><pre>{pgvectorInstall.result.traceback}</pre></details>}
        </div>}
      </section>

      <section className="settings-panel">
        <h2>LangSmith</h2>
        {renderField("LangSmith API Key","LANGSMITH_API_KEY","password","")}
        {renderField("Project","LANGSMITH_PROJECT","text","")}
        {renderField("Tracing (true/false)","LANGSMITH_TRACING","text","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['LANGSMITH_API_KEY','LANGSMITH_PROJECT','LANGSMITH_TRACING'])}>LangSmith 설정 저장</button>
          <button onClick={()=>testOne('langsmith')}>LangSmith 연결 테스트</button>
        </div>
        {renderTestResult("langsmith")}
      </section>
        </div>

        <div className="settings-column settings-column-right">
      <section className="settings-panel">
        <h2>OpenAI</h2>
        {renderField("OpenAI API Key","OPENAI_API_KEY","password","")}
        {renderField("GPT 코딩 모델","OPENAI_MODEL","text","")}
        {renderField("Embedding 모델","OPENAI_EMBEDDING_MODEL","text","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['OPENAI_API_KEY','OPENAI_MODEL','OPENAI_EMBEDDING_MODEL'])}>OpenAI 설정 저장</button>
          <button onClick={()=>testOne('openai')}>OpenAI 연결 테스트</button>
        </div>
        {renderTestResult("openai")}
      </section>

      <OllamaSettingsPanel
        busy={busy}
        runtimeBusy={ollamaRuntimeBusy}
        runtime={ollamaRuntime}
        install={ollamaInstall}
        valueOf={valueOf}
        setValue={setValue}
        renderField={renderField}
        renderTestResult={renderTestResult}
        onSave={()=>saveGroup(['OLLAMA_BASE_URL','OLLAMA_MODEL','OLLAMA_EMBEDDING_MODEL','OLLAMA_AUTO_START'])}
        onTest={()=>{refreshOllamaRuntime();testOne('ollama')}}
        onStart={startOllamaRuntime}
        onStop={stopOllamaRuntime}
        onInstall={installOllama}
        onRefresh={refreshOllamaRuntime}
      />

      <section className="settings-panel">
        <h2>Tavily</h2>
        {renderField("Tavily API Key","TAVILY_API_KEY","password","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['TAVILY_API_KEY'])}>Tavily 설정 저장</button>
          <button onClick={()=>testOne('tavily')}>Tavily 연결 테스트</button>
        </div>
        {renderTestResult("tavily")}
      </section>

      <section className="settings-panel">
        <h2>AI 모델 라우팅</h2>
        {renderField("로컬 작업 Provider","LOCAL_LLM_PROVIDER","text","")}
        {renderField("코딩 Provider","CODING_LLM_PROVIDER","text","")}
        {renderField("요구사항 분석 Provider","REQUIREMENTS_LLM_PROVIDER","text","")}
        <div className="hint-box">권장: local=ollama / coding=openai / requirements=openai</div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['LOCAL_LLM_PROVIDER','CODING_LLM_PROVIDER','REQUIREMENTS_LLM_PROVIDER'])}>라우팅 설정 저장</button>
        </div>
      </section>
        </div>
      </div>

      <section className="settings-panel settings-panel-wide">
        <h2>로컬 프로젝트 / 실행 정책</h2>
        <div className="two-col-fields">
          {renderPathField("허용 프로젝트 경로","ALLOWED_PROJECT_ROOTS","프로젝트 작업을 허용할 루트 폴더")}
          {renderPathField("Sandbox 경로","SANDBOX_ROOT","Sandbox 폴더")}
          {renderField("명령 최대 실행시간(초)","MAX_COMMAND_SECONDS","text","")}
          {renderField("자동 승인 Risk Level","AUTO_APPROVE_RISK_LEVEL","text","")}
          {renderField("자동 Debug 최대 반복","MAX_DEBUG_ITERATIONS","text","")}
          {renderField("Project Analyzer 최대 파일","PROJECT_ANALYZER_MAX_FILES","text","")}
          {renderField("MCP Timeout(초)","MCP_DEFAULT_TIMEOUT_SECONDS","text","")}
          {renderField("MCP Registry 갱신주기(초)","MCP_REGISTRY_REFRESH_SECONDS","text","")}
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup([
            'ALLOWED_PROJECT_ROOTS','SANDBOX_ROOT','MAX_COMMAND_SECONDS','AUTO_APPROVE_RISK_LEVEL',
            'MAX_DEBUG_ITERATIONS','PROJECT_ANALYZER_MAX_FILES','MCP_DEFAULT_TIMEOUT_SECONDS',
            'MCP_REGISTRY_REFRESH_SECONDS'
          ])}>로컬/실행 설정 저장</button>
        </div>
      </section>
    </div>

    <SystemStatusSummary status={status}/>
  </div></div>
}


const WORKFLOW_ICON_RULES=[
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

function workflowIconFor(text=''){
  const value=String(text).toLowerCase()
  for(const [keys,icon] of WORKFLOW_ICON_RULES){
    if(keys.some(key=>value.includes(String(key).toLowerCase()))){
      return icon
    }
  }
  return '◆'
}

function normalizeTargetStep(step,index){
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

function FactoryNodeCard({node,index}){
  const accent=node?.accent||'default'

  return <div className={`factory-node-card ${accent}`}>
    <div className="factory-node-visual">
      <span className="factory-node-icon">{node?.icon||'◆'}</span>
      <span className="factory-node-number">{String(index+1).padStart(2,'0')}</span>
    </div>
    <div className="factory-node-copy">
      <strong>{node?.label||node?.name}</strong>
      <small>{node?.description||''}</small>
    </div>
  </div>
}

function FactoryPhaseCard({phase,phaseIndex,isLast=false}){
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
        {(phase?.nodes||[]).map((node,index)=>
          <FactoryNodeCard
            key={node?.name||index}
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

function FactoryWorkflowDiagram({definition}){
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
      {phases.map((phase,index)=>
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

function TargetWorkflowDiagram({workflow}){
  const [selectedGroup,setSelectedGroup]=useState(null)

  const rawSteps=(workflow?.steps||[]).map((step,index)=>{
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

  const classifyStep=(step)=>{
    const text=[
      step?.name,
      step?.label,
      step?.description,
      step?.type
    ].join(' ').toLowerCase()

    if(
      text.includes('complete')
      || text.includes('완료')
    ) return 'COMPLETE'

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
      id:'MCP',
      title:'MCP 파일 처리',
      subtitle:'Client · Transport · Server · Tool',
      icon:'⚙'
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
    .map(def=>({
      ...def,
      steps:rawSteps.filter(step=>classifyStep(step)===def.id)
    }))
    .filter(group=>group.steps.length>0 || group.id==='COMPLETE')

  const activeGroup=groups.find(x=>x.id===selectedGroup)

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
          {activeGroup.steps.map((step,index)=><div className="target-step-wrap" key={`${step.name}-${index}`}>
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
      <span>그룹을 클릭하면 상세 단계가 표시됩니다.</span>
    </div>

    <div className="grouped-workflow-track">
      {groups.map((group,index)=><div className="grouped-workflow-wrap" key={group.id}>
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
          {workflow.requirement_coverage.filter(x=>x?.status==='covered').length}
          /{workflow.requirement_coverage.length} 반영
        </span>
      </div>
    </div>}
  </div>
}


function AgentBuildActionBar({
  stage='REQUIREMENTS',
  busy=false,
  message='',
  workflowEnabled=true,
  onWorkflow,
  onCreateProject,
  onStartDevelopment,
  onStop,
  compact=false,
}){
  const workflowReady=[
    'WORKFLOW_READY',
    'PROJECT_CREATED',
    'BUILDING'
  ].includes(stage)

  const projectReady=[
    'PROJECT_CREATED',
    'BUILDING'
  ].includes(stage)

  return <div className={`shared-build-actions ${compact?'compact':''}`}>
    <div className="shared-build-stage">
      <span className="done">1</span>
      <b>요구사항</b>
      <i>→</i>

      <span className={workflowReady?'done':'active'}>2</span>
      <b>Workflow</b>
      <i>→</i>

      <span className={projectReady?'done':''}>3</span>
      <b>프로젝트</b>
      <i>→</i>

      <span className={stage==='BUILDING'?'done':''}>4</span>
      <b>개발</b>
    </div>

    <div className="shared-build-buttons">
      <button
        type="button"
        className={stage==='REQUIREMENTS'?'primary':''}
        disabled={busy||!workflowEnabled||stage==='BUILDING'}
        onClick={onWorkflow}
      >
        ◇ Workflow 설계
      </button>

      <button
        type="button"
        className={stage==='WORKFLOW_READY'?'primary':''}
        disabled={busy||stage!=='WORKFLOW_READY'}
        onClick={onCreateProject}
      >
        ＋ 프로젝트 생성
      </button>

      <button
        type="button"
        className={stage==='PROJECT_CREATED'?'primary success':''}
        disabled={busy||stage!=='PROJECT_CREATED'}
        onClick={onStartDevelopment}
      >
        ▶ 개발 시작
      </button>
      {busy&&onStop&&<button type="button" className="execution-stop-button" onClick={onStop}>■ 실행 정지</button>}
    </div>

    {message&&<div className="shared-build-message">{message}</div>}
  </div>
}

function IDE() {
  const [root,setRoot]=useState('')

  const [newAgentName,setNewAgentName]=useState('')
  const [newAgentProjectRoot,setNewAgentProjectRoot]=useState('')
  const [newAgentCachePath,setNewAgentCachePath]=useState('')
  const [newAgentTempPath,setNewAgentTempPath]=useState('')
  const [newAgentOutputPath,setNewAgentOutputPath]=useState('')
  const [newAgentVenvPath,setNewAgentVenvPath]=useState('')
  const [newAgentModelsPath,setNewAgentModelsPath]=useState('')
  const [newAgentCreateResult,setNewAgentCreateResult]=useState(null)
  const [projectListOpen,setProjectListOpen]=useState(false)
  const [projectSwitcherOpen,setProjectSwitcherOpen]=useState(false)
  const [projectList,setProjectList]=useState([])
  const [projectListLoading,setProjectListLoading]=useState(false)
  const [selectedProjectId,setSelectedProjectId]=useState(null)
  const [screen,setScreen]=useState('HOME')
  const [weatherDashboard,setWeatherDashboard]=useState(null)
  const [weatherBusy,setWeatherBusy]=useState(false)
  const [weatherError,setWeatherError]=useState('')
  const weatherRequestTokenRef=useRef(0)
  const [showPathSettings,setShowPathSettings]=useState(false)
  const [usageOpen,setUsageOpen]=useState(false)
  const [builderStarted,setBuilderStarted]=useState(false)
  const [defaultPaths,setDefaultPaths]=useState({})

  const [projectLoadMessage,setProjectLoadMessage]=useState('')
  const [projectTerminalSessions,setProjectTerminalSessions]=useState({})
  const [activeTerminalProjectId,setActiveTerminalProjectId]=useState(null)
  const terminalSocketsRef=useRef({})
  const terminalIntentionalCloseRef=useRef({})
  const terminalOutputRefs=useRef({})
  const terminalInlineInputRef=useRef(null)
  const xtermInstancesRef=useRef({})
  const xtermContainersRef=useRef({})
  const xtermFitAddonsRef=useRef({})
  const xtermDisposablesRef=useRef({})
  const xtermCommandBuffersRef=useRef({})
  const xtermCommandHistoryRef=useRef({})
  const xtermHistoryIndexRef=useRef({})
  const xtermCursorIndexRef=useRef({})
  const xtermPromptRef=useRef({})
  const xtermOutputParseBufferRef=useRef({})
  const xtermRequiredColsRef=useRef({})
  const xtermSetCommandLineRef=useRef({})
  // Keyboard-only terminal text selection state. Shift+Up/Down extends the
  // selected buffer lines without feeding arrow escape sequences into the
  // local command-history handler. This mirrors the familiar terminal
  // selection workflow while preserving normal Up/Down history navigation.
  const xtermKeyboardSelectionRef=useRef({})
  const terminalCommandBusyRef=useRef({})
  const terminalCwdRef=useRef({})
  const terminalRootRef=useRef({})
  const terminalCompletionRef=useRef(null)
  const terminalCompletionTimerRef=useRef({})
  const [terminalCompletion,setTerminalCompletion]=useState(null)

  // v5.189: 터미널은 일반 콘솔처럼 현재 화면 폭에 맞춰 자동 줄바꿈합니다.
  // 입력/터미널 선택 시 가로 스크롤 위치를 강제로 변경하는 로직은 사용하지 않습니다.
  const scrollTerminalHorizontallyToEnd=()=>{}
  const scrollTerminalHorizontallyToStart=()=>{}
  const scrollTerminalHorizontallyToCaret=()=>{}

  const fitTerminalViewport=(id)=>{
    const term=xtermInstancesRef.current[id]
    const container=xtermContainersRef.current[id]
    const fit=xtermFitAddonsRef.current[id]
    if(!term||!container) return

    const rect=container.getBoundingClientRect?.()
    if(!rect||rect.width<120||rect.height<80) return

    // 동적으로 열 수를 늘려 가로 스크롤을 만드는 대신,
    // 현재 보이는 터미널 폭/높이에 맞는 cols/rows만 적용합니다.
    let proposed=null
    try{ proposed=fit?.proposeDimensions?.()||null }catch{}

    const targetCols=Math.max(20,proposed?.cols||term.cols||80)
    // xterm의 마지막 입력 줄/커서가 컨테이너 하단에 가려지지 않도록
    // 화면에 맞는 행 수에서 1행을 안전 여백으로 확보합니다.
    const proposedRows=proposed?.rows||term.rows||24
    const targetRows=Math.max(2,proposedRows-1)

    try{
      container.style.removeProperty('--terminal-min-width')
      container.style.removeProperty('--terminal-required-cols')
    }catch{}

    try{
      if(term.cols!==targetCols||term.rows!==targetRows){
        term.resize(targetCols,targetRows)
      }
    }catch{}
  }

  const fileLoadTokenRef=useRef(0)


  const [terminalConnectionState,setTerminalConnectionState]=useState({})
  const [terminalErrors,setTerminalErrors]=useState({})



  const [gitInfo,setGitInfo]=useState(null)
  const [gitInfoLoading,setGitInfoLoading]=useState(false)
  const [gitCommitMessage,setGitCommitMessage]=useState('')
  const [gitActionBusy,setGitActionBusy]=useState('')
  const [gitActionResult,setGitActionResult]=useState(null)


  const [projectLoadProgress,setProjectLoadProgress]=useState({
    active:false,
    percent:0,
    message:'',
    failed:false
  })

  const [externalProjectPath,setExternalProjectPath]=useState('')
  const [externalProjectAnalysis,setExternalProjectAnalysis]=useState(null)
  const [externalProjectLoading,setExternalProjectLoading]=useState(false)
  const [externalProjectPickerLoading,setExternalProjectPickerLoading]=useState(false)
  const [externalProjectPickerMessage,setExternalProjectPickerMessage]=useState('')

  const [externalProjectProgress,setExternalProjectProgress]=useState(0)
  const [externalProjectStatus,setExternalProjectStatus]=useState('')
  const [externalProjectStep,setExternalProjectStep]=useState('')
  const [externalProjectMode,setExternalProjectMode]=useState(false)
  const [loadedProjectAnalysis,setLoadedProjectAnalysis]=useState(null)
  const [files,setFiles]=useState([])
  const [fileLoading,setFileLoading]=useState(false)
  const [editorLoadErrors,setEditorLoadErrors]=useState({})
  const [fileCreateLoading,setFileCreateLoading]=useState(false)
  const fileCreateBusyRef=useRef(false)
  const [projectDirs,setProjectDirs]=useState([])
  const [selected,setSelected]=useState('')
  const [openEditorFiles,setOpenEditorFiles]=useState([])
  const [editorFileContents,setEditorFileContents]=useState({})
  const [editorFileDirty,setEditorFileDirty]=useState({})
  const [editorFileDiskMeta,setEditorFileDiskMeta]=useState({})
  const editorFileDiskMetaRef=useRef({})
  const [editorExternalState,setEditorExternalState]=useState({})
  const [pdfPreviewRevision,setPdfPreviewRevision]=useState({})
  const [presentationPreviewRevision,setPresentationPreviewRevision]=useState({})
  const projectFileSnapshotRef=useRef(null)
  const fileWatchBusyRef=useRef(false)
  const openEditorFilesRef=useRef([])
  const editorFileDirtyRef=useRef({})
  const selectedEditorFileRef=useRef('')
  const [pinnedEditorFiles,setPinnedEditorFiles]=useState([])
  const [fileSaveStatus,setFileSaveStatus]=useState('')
  const [editorTabMenu,setEditorTabMenu]=useState(null)
  const [editorFilesMenu,setEditorFilesMenu]=useState(null)
  const [editorCloseConfirm,setEditorCloseConfirm]=useState(null)
  const [fileTreeSelectedPaths,setFileTreeSelectedPaths]=useState([])
  const fileTreeSelectionAnchorRef=useRef('')
  const [fileTreeContextMenu,setFileTreeContextMenu]=useState(null)
  const [fileDeleteConfirm,setFileDeleteConfirm]=useState(null)
  const [externalChangeConfirm,setExternalChangeConfirm]=useState(null)
  const [externalFileNotifications,setExternalFileNotifications]=useState([])
  const [externalNotificationOpen,setExternalNotificationOpen]=useState(false)


  const [code,setCode]=useState('// 파일을 선택하세요.')
  const [focusOwner,setFocusOwner]=useState('editor')
  const focusOwnerRef=useRef('editor')
  const editorInstanceRef=useRef(null)
  const notebookEditorControllerRef=useRef(null)
  const editorTabsScrollRef=useRef(null)

  const setFocusOwnerSafe=(owner)=>{
    focusOwnerRef.current=owner
    setFocusOwner(owner)
  }

  const isTextEntryFocused=()=>{
    if(typeof document==='undefined') return false
    const el=document.activeElement
    if(!el) return false
    const tag=String(el.tagName||'').toLowerCase()
    return tag==='textarea'||tag==='input'||tag==='select'||!!el.isContentEditable
  }

  const canAutoFocusTerminal=()=>
    focusOwnerRef.current==='terminal'&&!isTextEntryFocused()

  const scrollEditorTabs=(direction=1)=>{
    const strip=editorTabsScrollRef.current
    if(!strip) return
    const distance=Math.max(260,Math.min(520,Math.round(strip.clientWidth*0.72)))
    strip.scrollBy({left:direction*distance,behavior:'smooth'})
  }

  useEffect(()=>{
    const strip=editorTabsScrollRef.current
    if(!strip||!selected) return
    const active=Array.from(strip.querySelectorAll('.code-file-tab'))
      .find(node=>node?.dataset?.editorPath===selected)
    active?.scrollIntoView({behavior:'smooth',block:'nearest',inline:'nearest'})
  },[selected,openEditorFiles.length])

  const provider='auto'
  const [aiRuntimeStatus,setAiRuntimeStatus]=useState(null)
  const [aiModeMenuOpen,setAiModeMenuOpen]=useState(false)
  const [aiModeBusy,setAiModeBusy]=useState(false)
  const [aiModeError,setAiModeError]=useState('')
  const [tab,setTab]=useState('TERMINAL')
  const [terminal,setTerminal]=useState('')
  const [command,setCommand]=useState('git status')
  const [jobs,setJobs]=useState({})
  const [workflowReq,setWorkflowReq]=useState('')
  const [confirmedInterviewRequirements,setConfirmedInterviewRequirements]=useState({})
  const [requirementDraftRestored,setRequirementDraftRestored]=useState(false)
  const [requirementDraftSavedAt,setRequirementDraftSavedAt]=useState('')
  const builderMessagesEndRef=useRef(null)
  const [workflow,setWorkflow]=useState(null)
  const [workflowDefinition,setWorkflowDefinition]=useState(null)
  const [workflowView,setWorkflowView]=useState('STUDIO')
  const [targetWorkflowPreview,setTargetWorkflowPreview]=useState(null)
  const [targetWorkflowLoading,setTargetWorkflowLoading]=useState(false)
  const [workflowProgress,setWorkflowProgress]=useState({
    active:false,
    percent:0,
    stage:'대기',
    detail:'',
    startedAt:null
  })
  const [developmentProgress,setDevelopmentProgress]=useState({
    active:false,
    percent:0,
    stage:'대기',
    detail:'',
    startedAt:null,
    elapsedSeconds:0
  })
  const [developmentFinalStatus,setDevelopmentFinalStatus]=useState(null)
  const [targetWorkflowError,setTargetWorkflowError]=useState('')
  const [targetWorkflowQuality,setTargetWorkflowQuality]=useState(null)
  const [agentBuildStage,setAgentBuildStage]=useState('REQUIREMENTS')
  const [agentBuildBusy,setAgentBuildBusy]=useState(false)
  const [agentBuildMessage,setAgentBuildMessage]=useState('')
  const [codingStyleReport,setCodingStyleReport]=useState(null)
  const [llmUsageSummary,setLlmUsageSummary]=useState(null)
  const [llmCatalog,setLlmCatalog]=useState(null)
  const [llmHistory,setLlmHistory]=useState(null)
  const [llmCatalogLoading,setLlmCatalogLoading]=useState(false)
  const [llmCatalogError,setLlmCatalogError]=useState('')
  const [llmUsageScope,setLlmUsageScope]=useState('today')
  const [llmUsageDate,setLlmUsageDate]=useState(localIsoDate)
  const [llmUsageMonth,setLlmUsageMonth]=useState(localIsoMonth)
  const [reportGeneratedAt,setReportGeneratedAt]=useState('')
  const [analysis,setAnalysis]=useState(null)
  const [mcpName,setMcpName]=useState('Local MCP')
  const [mcpEndpoint,setMcpEndpoint]=useState('http://127.0.0.1:8001/mcp')
  const [mcpServers,setMcpServers]=useState([])
  const [mcpTools,setMcpTools]=useState([])
  const [mcpAddOpen,setMcpAddOpen]=useState(false)
  const [mcpAddBusy,setMcpAddBusy]=useState(false)
  const [mcpAddError,setMcpAddError]=useState('')
  const [mcpAddForm,setMcpAddForm]=useState({
    name:'',
    endpoint:'',
    trust_level:'UNTRUSTED',
    allow_read_without_prompt:false,
    allow_write_without_prompt:false,
  })
  const [memoryQuery,setMemoryQuery]=useState('')
  const [memoryResult,setMemoryResult]=useState([])











  const [chat,setChat]=useState([{role:'assistant',content:'만들고 싶은 AI Agent + MCP 프로그램을 말씀해 주세요. 필요한 질문은 한 번에 하나씩 하겠습니다.'}])
  const [input,setInput]=useState('')
  const [busy,setBusy]=useState(false)
  const [workspaceTab,setWorkspaceTab]=useState('DESIGN')
  const [workspaceLeftCollapsed,setWorkspaceLeftCollapsed]=useState(()=>{
    try{return localStorage.getItem('agentstudio.workspace.leftCollapsed')==='1'}catch{return false}
  })
  const [workspaceRightCollapsed,setWorkspaceRightCollapsed]=useState(()=>{
    try{return localStorage.getItem('agentstudio.workspace.rightCollapsed')==='1'}catch{return false}
  })
  const [workspaceBottomCollapsed,setWorkspaceBottomCollapsed]=useState(()=>{
    try{return localStorage.getItem('agentstudio.workspace.bottomCollapsed')==='1'}catch{return false}
  })
  const [workspaceBottomHeight,setWorkspaceBottomHeight]=useState(()=>{
    try{
      const saved=Number(localStorage.getItem('agentstudio.workspace.bottomHeight'))
      return Number.isFinite(saved)&&saved>=305?saved:305
    }catch{return 305}
  })
  const workspaceLayoutRef=useRef(null)
  const workspaceResizeCleanupRef=useRef(null)
  const workspaceBottomResizeCleanupRef=useRef(null)
  const [workspaceResizeSide,setWorkspaceResizeSide]=useState(null)
  const [workspaceBottomResizing,setWorkspaceBottomResizing]=useState(false)
  const [workspaceLeftWidth,setWorkspaceLeftWidth]=useState(()=>{
    try{
      const saved=Number(localStorage.getItem('agentstudio.workspace.leftWidth'))
      return Number.isFinite(saved)&&saved>=230?saved:270
    }catch{return 270}
  })
  const [workspaceRightWidth,setWorkspaceRightWidth]=useState(()=>{
    try{
      const saved=Number(localStorage.getItem('agentstudio.workspace.rightWidth'))
      return Number.isFinite(saved)&&saved>=260?saved:300
    }catch{return 300}
  })
  const [codeEditPrompt,setCodeEditPrompt]=useState('')
  const [codeEditScope,setCodeEditScope]=useState('FILE')
  const [codeEditChat,setCodeEditChat]=useState([
    {
      role:'assistant',
      content:'수정할 파일을 선택한 뒤 원하는 변경 내용을 입력하세요. 현재 파일 코드를 기준으로 수정안을 만들고 적용할 수 있습니다.'
    }
  ])
  const codeEditChatRef=useRef(null)
  const [codeEditBusy,setCodeEditBusy]=useState(false)
  const [codeEditProposal,setCodeEditProposal]=useState(null)
  const [codeDiffReview,setCodeDiffReview]=useState(null)
  const [codeRightPanelTab,setCodeRightPanelTab]=useState('FILES')
  const [sqlProfile,setSqlProfile]=useState({
    connection_id:'',
    name:'PostgreSQL 연결',
    db_type:'postgresql',
    host:'127.0.0.1',
    port:5432,
    database:'',
    schema_name:'',
    username:'postgres',
    password:'',
    driver:'ODBC Driver 18 for SQL Server',
    service_name:'FREEPDB1',
    project_id:'',
    service_account_json:'',
    dashboard_url:'',
    ssl_mode:'',
    trust_server_certificate:true,
    credential_saved:false
  })
  const [sqlConnections,setSqlConnections]=useState([])
  const [sqlSupabaseConnectionUrl,setSqlSupabaseConnectionUrl]=useState('')
  const [sqlConnectionImport,setSqlConnectionImport]=useState({busy:false,db_type:'',source_name:'',message:'',error:''})
  const [sqlDatabaseManual,setSqlDatabaseManual]=useState(false)
  const [sqlConnectionStatus,setSqlConnectionStatus]=useState(null)
  const [sqlConnectionBusy,setSqlConnectionBusy]=useState(false)
  const [sqlQueryBusy,setSqlQueryBusy]=useState(false)
  const sqlStopRequestedRef=useRef(false)
  const [pythonExecutionState,setPythonExecutionState]=useState({busy:false,root:'',sessionId:'',label:'',kind:''})
  const pythonStopRequestedRef=useRef(false)
  const [cmdExecution,setCmdExecution]=useState({busy:false,executionId:'',path:'',pid:null})
  const [activeWorkflowJobId,setActiveWorkflowJobId]=useState('')
  const [globalStopBusy,setGlobalStopBusy]=useState(false)
  const [sqlQueryResult,setSqlQueryResult]=useState(null)
  const [sqlResultTab,setSqlResultTab]=useState('DATA')
  const [sqlMessages,setSqlMessages]=useState([])
  const [sqlDbObjects,setSqlDbObjects]=useState(null)
  const [sqlDbObjectsBusy,setSqlDbObjectsBusy]=useState(false)
  const [sqlDbObjectsError,setSqlDbObjectsError]=useState('')
  const [sqlDbObjectExpanded,setSqlDbObjectExpanded]=useState({})
  const [firestoreBrowser,setFirestoreBrowser]=useState(null)
  const [firestoreBrowserBusy,setFirestoreBrowserBusy]=useState(false)
  const [firestoreBrowserError,setFirestoreBrowserError]=useState('')
  const [firestoreCollectionFilter,setFirestoreCollectionFilter]=useState('')
  const [firestoreDocumentFilter,setFirestoreDocumentFilter]=useState('')
  const [firestoreSelectedCollection,setFirestoreSelectedCollection]=useState('')
  const [firestoreDocuments,setFirestoreDocuments]=useState(null)
  const [firestoreDocumentsBusy,setFirestoreDocumentsBusy]=useState(false)
  const [firestoreSelectedDocument,setFirestoreSelectedDocument]=useState('')
  const [firestoreDocumentDetail,setFirestoreDocumentDetail]=useState(null)
  const [firestoreDocumentDetailBusy,setFirestoreDocumentDetailBusy]=useState(false)
  const [firestoreContextMenu,setFirestoreContextMenu]=useState(null)
  const [firestoreScriptBusy,setFirestoreScriptBusy]=useState('')
  const [redisBrowser,setRedisBrowser]=useState(null)
  const [redisBrowserBusy,setRedisBrowserBusy]=useState(false)
  const [redisBrowserError,setRedisBrowserError]=useState('')
  const [redisKeyFilter,setRedisKeyFilter]=useState('')
  const [redisTypeFilter,setRedisTypeFilter]=useState('all')
  const [redisSelectedKey,setRedisSelectedKey]=useState('')
  const [redisKeyDetail,setRedisKeyDetail]=useState(null)
  const [redisKeyDetailBusy,setRedisKeyDetailBusy]=useState(false)
  const [redisKeyExpanded,setRedisKeyExpanded]=useState({})
  const [redisContextMenu,setRedisContextMenu]=useState(null)
  const [redisScriptBusy,setRedisScriptBusy]=useState('')
  const [sqlObjectActionBusy,setSqlObjectActionBusy]=useState('')
  const [sqlObjectContextMenu,setSqlObjectContextMenu]=useState(null)
  const [sqlDatabaseContextMenu,setSqlDatabaseContextMenu]=useState(null)
  const [sqlAdminPrompt,setSqlAdminPrompt]=useState(null)
  const [sqliteProjectStatus,setSqliteProjectStatus]=useState(null)
  const [sqliteProjectStatusBusy,setSqliteProjectStatusBusy]=useState(false)
  const sqlLoadedRootRef=useRef('')

  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.leftCollapsed',workspaceLeftCollapsed?'1':'0')}catch{}
  },[workspaceLeftCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.rightCollapsed',workspaceRightCollapsed?'1':'0')}catch{}
  },[workspaceRightCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.bottomCollapsed',workspaceBottomCollapsed?'1':'0')}catch{}
  },[workspaceBottomCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.bottomHeight',String(Math.round(workspaceBottomHeight)))}catch{}
  },[workspaceBottomHeight])
  useEffect(()=>{
    const timer=setTimeout(()=>{
      try{window.dispatchEvent(new Event('resize'))}catch(_){}
    },40)
    return ()=>clearTimeout(timer)
  },[workspaceBottomHeight,workspaceBottomCollapsed])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.leftWidth',String(Math.round(workspaceLeftWidth)))}catch{}
  },[workspaceLeftWidth])
  useEffect(()=>{
    try{localStorage.setItem('agentstudio.workspace.rightWidth',String(Math.round(workspaceRightWidth)))}catch{}
  },[workspaceRightWidth])
  useEffect(()=>()=>{
    try{workspaceResizeCleanupRef.current?.()}catch{}
    try{workspaceBottomResizeCleanupRef.current?.()}catch{}
  },[])

  const beginWorkspaceBottomResize=(event)=>{
    if(workspaceBottomCollapsed) return
    event.preventDefault()
    event.stopPropagation()
    const main=event.currentTarget?.closest?.('.workspace-main')
    if(!main) return
    const rect=main.getBoundingClientRect()
    const startY=event.clientY
    const startHeight=workspaceBottomHeight
    const minimum=305
    const topMinimum=180
    const maxHeight=Math.max(minimum,rect.height-42-6-topMinimum)
    const previousCursor=document.body.style.cursor
    const previousSelect=document.body.style.userSelect
    document.body.style.cursor='row-resize'
    document.body.style.userSelect='none'
    setWorkspaceBottomResizing(true)

    const onMove=(moveEvent)=>{
      const delta=startY-moveEvent.clientY
      const next=Math.max(minimum,Math.min(maxHeight,startHeight+delta))
      setWorkspaceBottomHeight(next)
    }
    const cleanup=()=>{
      window.removeEventListener('pointermove',onMove)
      window.removeEventListener('pointerup',cleanup)
      window.removeEventListener('pointercancel',cleanup)
      document.body.style.cursor=previousCursor
      document.body.style.userSelect=previousSelect
      setWorkspaceBottomResizing(false)
      workspaceBottomResizeCleanupRef.current=null
    }
    workspaceBottomResizeCleanupRef.current=cleanup
    window.addEventListener('pointermove',onMove)
    window.addEventListener('pointerup',cleanup)
    window.addEventListener('pointercancel',cleanup)
  }

  const getWorkspacePanelMinimum=(side)=>{
    const compact=typeof window!=='undefined'&&window.innerWidth<=1150
    return side==='left'?(compact?230:270):(compact?260:300)
  }

  const beginWorkspacePanelResize=(side,event)=>{
    if((side==='left'&&workspaceLeftCollapsed)||(side==='right'&&workspaceRightCollapsed)) return
    event.preventDefault()
    event.stopPropagation()

    const host=workspaceLayoutRef.current
    if(!host) return
    const rect=host.getBoundingClientRect()
    const startX=event.clientX
    const startWidth=side==='left'?workspaceLeftWidth:workspaceRightWidth
    const otherWidth=side==='left'
      ? (workspaceRightCollapsed?0:workspaceRightWidth)
      : (workspaceLeftCollapsed?0:workspaceLeftWidth)
    const minWidth=getWorkspacePanelMinimum(side)
    const centerMinimum=420
    const maxWidth=Math.max(minWidth,rect.width-otherWidth-centerMinimum)

    const previousCursor=document.body.style.cursor
    const previousSelect=document.body.style.userSelect
    document.body.style.cursor='col-resize'
    document.body.style.userSelect='none'
    setWorkspaceResizeSide(side)

    const onMove=(moveEvent)=>{
      const delta=side==='left'
        ? moveEvent.clientX-startX
        : startX-moveEvent.clientX
      const next=Math.max(minWidth,Math.min(maxWidth,startWidth+delta))
      if(side==='left') setWorkspaceLeftWidth(next)
      else setWorkspaceRightWidth(next)
    }
    const cleanup=()=>{
      window.removeEventListener('pointermove',onMove)
      window.removeEventListener('pointerup',cleanup)
      window.removeEventListener('pointercancel',cleanup)
      document.body.style.cursor=previousCursor
      document.body.style.userSelect=previousSelect
      setWorkspaceResizeSide(null)
      workspaceResizeCleanupRef.current=null
    }
    workspaceResizeCleanupRef.current=cleanup
    window.addEventListener('pointermove',onMove)
    window.addEventListener('pointerup',cleanup)
    window.addEventListener('pointercancel',cleanup)
  }

  useEffect(()=>{
    // 프로젝트를 전환하면 이전 프로젝트의 AI 코드 제안/Diff가 새 프로젝트에
    // 남아 보이지 않도록 검토 상태를 초기화합니다.
    setCodeEditProposal(null)
    setCodeDiffReview(null)
    setCodeRightPanelTab('FILES')
  },[root])

  const scrollCodeEditChatToBottom=(behavior='smooth')=>{
    requestAnimationFrame(()=>{
      const el=codeEditChatRef.current
      if(!el) return
      try{
        el.scrollTo({top:el.scrollHeight,behavior})
      }catch{
        el.scrollTop=el.scrollHeight
      }
    })
  }

  useEffect(()=>{
    // 새 사용자 요청, AI 진행 상태, AI 응답이 추가될 때 가장 최근 메시지를 보여줍니다.
    if(workspaceTab!=='CODE') return
    scrollCodeEditChatToBottom(codeEditBusy?'auto':'smooth')
  },[codeEditChat.length,codeEditBusy,codeEditProposal,workspaceTab])

  const [terminalSessions,setTerminalSessions]=useState([
    {
      id:'terminal-1',
      name:'PowerShell',
      command:'',
      output:'',
      processState:'idle',
      exitCode:null,
    }
  ])
  const [activeTerminalId,setActiveTerminalId]=useState('terminal-1')
  const [terminalNameEditId,setTerminalNameEditId]=useState(null)
  const [terminalNameDraft,setTerminalNameDraft]=useState('')

  const [projectSearch,setProjectSearch]=useState('')
  const [projectFilter,setProjectFilter]=useState('ALL')
  const [projectListStatus,setProjectListStatus]=useState('DB 프로젝트 목록을 아직 읽지 않았습니다.')
  const [projectListLogPath,setProjectListLogPath]=useState('')
  const [projectDbDiagnostic,setProjectDbDiagnostic]=useState(null)


  const [fileTreeExpanded,setFileTreeExpanded]=useState({})
  const [fileTreeSelected,setFileTreeSelected]=useState('')
  const [fileTreeRename,setFileTreeRename]=useState(null)



  useEffect(()=>{const ws=connectJobs(evt=>{
    if(evt.type==='job'){
      setJobs(p=>({...p,[evt.job.id]:evt.job}))
      if(evt.job.result?.output)setTerminal(evt.job.result.output)

      setPgvectorInstall(current=>{
        if(!current?.job_id || current.job_id!==evt.job.id) return current
        const next={
          ...current,
          status:evt.job.status,
          progress:evt.job.progress||0,
          message:evt.job.message||'',
          result:evt.job.result||{}
        }
        if(evt.job.status==='SUCCESS' || evt.job.status==='FAILED' || evt.job.status==='CANCELLED'){
          setBusy(false)
          if(evt.job.status==='SUCCESS'){
            setTimeout(()=>testOne('pgvector'),300)
          }
        }
        return next
      })
    }
  });return()=>ws.close()},[])



  const chooseAgentFolder=async(setter,currentValue,label)=>{
    try{
      const r=await api('/system/pick-folder',{
        method:'POST',
        body:JSON.stringify({
          title:`${label} 선택`,
          initial_path:currentValue||''
        })
      })
      if(r.ok && !r.cancelled && r.path){
        setter(r.path)
      }
    }catch(e){
      setNewAgentCreateResult({
        ok:false,
        message:'경로 선택 실패: '+String(e)
      })
    }
  }

  const loadDefaultPaths=async()=>{
    try{
      const d=await api('/settings/default-paths')
      setDefaultPaths(d||{})
      // 신규 Agent의 프로젝트 경로는 사용자가 직접 입력하거나 '경로 찾기'로 선택합니다.
      // 시스템 기본 project_root를 실제 input value로 자동 주입하지 않습니다.
      if(!newAgentCachePath && d?.cache_root) setNewAgentCachePath(d.cache_root)
      if(!newAgentTempPath && d?.temp_root) setNewAgentTempPath(d.temp_root)
      if(!newAgentOutputPath && d?.output_root) setNewAgentOutputPath(d.output_root)
      if(!newAgentModelsPath && d?.common_models_root) setNewAgentModelsPath(d.common_models_root)
    }catch(e){}
  }

  useEffect(()=>{
    const timer=setTimeout(()=>{
      saveRequirementDraft()
    },350)

    return()=>clearTimeout(timer)
  },[
    chat,
    workflowReq,
    confirmedInterviewRequirements,
    targetWorkflowPreview,
    targetWorkflowQuality,
    agentBuildStage,
    newAgentName,
    newAgentProjectRoot
  ])

  useEffect(()=>{
    // 프로젝트 경로가 확정/변경되면 해당 경로의 이전 요구사항 Draft를 찾습니다.
    if(!String(newAgentProjectRoot||'').trim()) return

    const timer=setTimeout(()=>{
      restoreRequirementDraft()
    },80)

    return()=>clearTimeout(timer)
  },[newAgentProjectRoot])

  useEffect(()=>{loadDefaultPaths()},[])
  useEffect(()=>{refreshProjectList()},[])
  useEffect(()=>{loadWorkflowDefinition()},[])
  useEffect(()=>{
    builderMessagesEndRef.current?.scrollIntoView({
      behavior:'smooth',
      block:'end'
    })
  },[chat,busy])

  const filteredProjects = projectList
    .filter(p=>{
      const q=(projectSearch||'').trim().toLowerCase()
      if(q && !`${p.name||''} ${p.project_root||''}`.toLowerCase().includes(q)){
        return false
      }

      if(projectFilter==='FAVORITE'){
        return !!p.is_favorite
      }

      if(projectFilter==='RECENT'){
        return !!p.last_opened_at
      }

      return true
    })
    .sort((a,b)=>{
      if(projectFilter==='RECENT'){
        return new Date(b.last_opened_at||0)-new Date(a.last_opened_at||0)
      }
      return (b.is_favorite?1:0)-(a.is_favorite?1:0)
        || new Date(b.last_opened_at||b.updated_at||0)-new Date(a.last_opened_at||a.updated_at||0)
    })
  const currentProject = projectList.find(p=>p.id===selectedProjectId) || null
  const currentProjectName = currentProject?.name || newAgentName || (root ? root.split(/[\\/]/).filter(Boolean).pop() : '') || '프로젝트 선택'
  const currentProjectPath = currentProject?.project_root || currentProject?.root_path || root || newAgentProjectRoot || ''
  const activeWorkspaceRoot = currentProjectPath
  const workspaceSummary = loadedProjectAnalysis?.summary || currentProject?.description || '프로젝트 분석 정보가 아직 없습니다.'
  const isSqlFile=!!selected?.toLowerCase?.().endsWith('.sql')

  const sqlProfileForType=(dbType,previous={})=>{
    const kind=String(dbType||'postgresql').toLowerCase()
    const common={connection_id:'',name:'DB 연결',db_type:kind,host:'',port:0,database:'',schema_name:'',username:'',password:'',driver:'',service_name:'',project_id:'',service_account_json:'',dashboard_url:'',ssl_mode:'',trust_server_certificate:true,credential_saved:false}
    const defaults=kind==='sqlite3'
      ? {...common,name:'SQLite3 연결',db_type:'sqlite3',database:'',driver:'Python sqlite3 (stdlib)'}
      : kind==='firestore'
        ? {...common,name:'Google Cloud Firestore 연결',db_type:'firestore',database:'(default)',driver:'google-cloud-firestore',dashboard_url:'https://console.cloud.google.com/firestore/databases'}
        : kind==='supabase'
          ? {...common,name:'Supabase 연결',db_type:'supabase',host:'',port:5432,database:'postgres',schema_name:'public',username:'postgres',driver:'psycopg',dashboard_url:'https://supabase.com/dashboard',ssl_mode:'require'}
          : kind==='redis'
            ? {...common,name:'Redis 연결',db_type:'redis',host:'127.0.0.1',port:6379,database:'0',username:'',driver:'redis-py'}
          : kind==='mssql'
            ? {...common,name:'MSSQL 연결',db_type:'mssql',host:'127.0.0.1',port:1433,driver:'ODBC Driver 18 for SQL Server'}
            : kind==='oracle'
              ? {...common,name:'Oracle 연결',db_type:'oracle',host:'127.0.0.1',port:1521,service_name:'FREEPDB1'}
              : {...common,name:'PostgreSQL 연결',db_type:'postgresql',host:'127.0.0.1',port:5432,username:'postgres'}
    return {...defaults,...previous,db_type:kind,port:(previous.db_type===kind&&previous.port!==undefined)?previous.port:defaults.port}
  }


  const applySupabaseConnectionUrl=()=>{
    const raw=String(sqlSupabaseConnectionUrl||'').trim()
    if(!raw) return
    try{
      const normalized=raw.replace(/^postgresql\+[^:]+:/i,'postgresql:').replace(/^postgres:/i,'postgresql:')
      const parsed=new URL(normalized)
      const host=parsed.hostname||''
      const port=Number(parsed.port||5432)
      const database=decodeURIComponent((parsed.pathname||'/postgres').replace(/^\//,'')||'postgres')
      const username=decodeURIComponent(parsed.username||'postgres')
      const password=decodeURIComponent(parsed.password||'')
      const optionsValue=decodeURIComponent(parsed.searchParams.get('options')||'')
      const optionSchemaMatch=optionsValue.match(/(?:^|\s)-csearch_path=([^\s]+)/i)
      const schemaName=String(parsed.searchParams.get('schema')||parsed.searchParams.get('search_path')||optionSchemaMatch?.[1]||'').split(',')[0].trim()
      if(!host) throw new Error('Host를 읽을 수 없습니다.')
      setSqlProfile(prev=>({...prev,db_type:'supabase',host,port,database,schema_name:schemaName||prev.schema_name||'public',username,password,ssl_mode:prev.ssl_mode||'require'}))
      setSqlSupabaseConnectionUrl('')
      setSqlMessages(prev=>[{type:'info',text:'Supabase Connection URL을 Host/Port/Database/Schema/User/Password로 분해했습니다. 원본 URL은 저장하지 않습니다.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`Supabase Connection URL 형식 확인 필요: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }
  }

  const importSqlConnectionFile=async(dbType)=>{
    const kind=String(dbType||'').toLowerCase()
    if(!['supabase','firestore','redis'].includes(kind)) return
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot){
      setSqlConnectionImport({busy:false,db_type:kind,source_name:'',message:'',error:'먼저 프로젝트를 선택하세요.'})
      return
    }
    setSqlConnectionImport({busy:true,db_type:kind,source_name:'',message:'파일 선택창을 여는 중...',error:''})
    try{
      const result=await api('/sql/import-connection-file',{
        method:'POST',
        body:JSON.stringify({root:workspaceRoot,db_type:kind,initial_path:workspaceRoot})
      })
      if(result?.cancelled){
        setSqlConnectionImport({busy:false,db_type:kind,source_name:'',message:'파일 선택을 취소했습니다.',error:''})
        return
      }
      const imported=result?.profile||{}
      const detected=Array.isArray(result?.detected_fields)?result.detected_fields:[]
      const detectedKind=String(result?.db_type||imported?.db_type||kind).toLowerCase()
      const targetKind=['supabase','firestore','redis'].includes(detectedKind)?detectedKind:kind
      setSqlProfile(prev=>{
        const defaults=sqlProfileForType(targetKind)
        const previousDefaultName=sqlProfileForType(prev.db_type||kind).name
        const providerChanged=targetKind!==kind
        const keepName=providerChanged
          ? defaults.name
          : ((!prev.name||prev.name===previousDefaultName)?defaults.name:prev.name)
        const hasImportedPassword=Object.prototype.hasOwnProperty.call(imported,'password')&&String(imported.password||'')!==''
        return {
          ...defaults,
          ...(providerChanged?{}:prev),
          ...imported,
          db_type:targetKind,
          connection_id:providerChanged?'':(prev.connection_id||''),
          name:keepName,
          password:Object.prototype.hasOwnProperty.call(imported,'password')?String(imported.password||''):(providerChanged?'':(prev.password||'')),
          credential_saved:hasImportedPassword?false:(providerChanged?false:!!prev.credential_saved)
        }
      })
      setSqlDatabaseManual(true)
      if(kind==='supabase'||targetKind==='supabase') setSqlSupabaseConnectionUrl('')
      const safeFields=detected.map(field=>field==='password'?'password(감지됨)':field).join(', ')
      const switched=targetKind!==kind?` · 파일 형식 감지: ${sqlProfileForType(targetKind).name}`:''
      const text=String(result?.message||`${result?.source_name||'연결 파일'} 분석 완료`) + switched + (safeFields?` · ${safeFields}`:'')
      setSqlConnectionImport({busy:false,db_type:targetKind,source_name:result?.source_name||'',message:text,error:''})
      setSqlMessages(prev=>[{type:'info',text,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      let text=String(e?.message||e||'연결 설정 파일 분석 실패')
      try{
        const raw=String(e?.responseBody||'')
        if(raw){
          const parsed=JSON.parse(raw)
          const detail=parsed?.detail
          text=String((detail&&typeof detail==='object'?(detail.message||detail.detail):detail)||text)
        }
      }catch{}
      text=text.replace(/^Backend HTTP \d+:\s*/,'').trim()
      setSqlConnectionImport({busy:false,db_type:kind,source_name:'',message:'',error:text})
      setSqlMessages(prev=>[{type:'error',text:`연결 설정 파일 확인 필요: ${text}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }
  }

  const getSqlDatabaseHistory=()=>{
    if(['sqlite3','oracle','firestore'].includes(String(sqlProfile.db_type||'').toLowerCase())) return []
    const kind=String(sqlProfile.db_type||'').toLowerCase()
    const host=String(sqlProfile.host||'').trim().toLowerCase()
    const port=Number(sqlProfile.port||0)
    const historyRows=Array.isArray(sqlConnectionStatus?.database_history)?sqlConnectionStatus.database_history:[]
    const historyValues=historyRows
      .filter(item=>String(item?.db_type||'').toLowerCase()===kind)
      .filter(item=>String(item?.host||'').trim().toLowerCase()===host)
      .filter(item=>Number(item?.port||0)===port)
      .map(item=>String(item?.database||'').trim())
      .filter(Boolean)
    const savedProfileValues=(sqlConnections||[])
      .filter(item=>String(item?.db_type||'').toLowerCase()===kind)
      .filter(item=>String(item?.host||'').trim().toLowerCase()===host)
      .filter(item=>Number(item?.port||0)===port)
      .map(item=>String(item?.database||'').trim())
      .filter(Boolean)
    return [...new Set([...historyValues,...savedProfileValues])].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:'base'}))
  }

  const applySqlWorkspaceStatus=(status,{preservePassword=true}={})=>{
    if(!status) return
    setSqlConnectionStatus(status)
    if(Array.isArray(status.connections)) setSqlConnections(status.connections)
    if(status?.profile){
      setSqlDatabaseManual(false)
      setSqlProfile(prev=>({
        ...sqlProfileForType(status.profile.db_type||'postgresql',status.profile),
        password:preservePassword&&prev.connection_id===status.profile.connection_id?(prev.password||''):''
      }))
    }
  }

  const newSqlWorkspaceConnection=(dbType=sqlProfile.db_type||'postgresql')=>{
    const fresh=sqlProfileForType(dbType)
    setSqlSupabaseConnectionUrl('')
    setSqlConnectionImport({busy:false,db_type:'',source_name:'',message:'',error:''})
    setSqlDatabaseManual(false)
    setSqlProfile(fresh)
    setSqlConnectionStatus(prev=>prev?{...prev,connected:false,connected_at:null,profile:fresh}:prev)
    setSqlDbObjects(null)
    setSqlDbObjectsError('')
    setSqlDbObjectExpanded({})
    resetFirestoreBrowser()
    setRedisBrowser(null)
    setRedisBrowserError('')
    setRedisSelectedKey('')
    setRedisKeyDetail(null)
    setRedisKeyExpanded({})
  }

  const selectSqlWorkspaceConnection=async(connectionId)=>{
    if(!activeWorkspaceRoot) return
    setSqlSupabaseConnectionUrl('')
    const cid=String(connectionId||'')
    if(!cid){
      newSqlWorkspaceConnection()
      return
    }
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/activate',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:cid})
      })
      applySqlWorkspaceStatus(status,{preservePassword:false})
      if(status?.connected&&status?.profile?.db_type==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true,preserveSelection:false})
      }else if(status?.connected&&status?.profile?.db_type==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true,preserveSelection:false})
      }else if(status?.connected){
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }else{
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        resetFirestoreBrowser()
        resetRedisBrowser()
      }
      if(status?.profile?.db_type==='sqlite3') await loadSqliteProjectStatus({quiet:true})
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 선택 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const loadSqliteProjectStatus=async({quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(!quiet) setSqliteProjectStatusBusy(true)
    try{
      const status=await api(`/sql/sqlite-status?root=${encodeURIComponent(workspaceRoot)}`)
      setSqliteProjectStatus(status)
      setSqlProfile(prev=>{
        if(prev.db_type!=='sqlite3'||String(prev.database||'').trim()) return prev
        return {...prev,database:status?.recommended_database||'data/app.db'}
      })
      return status
    }catch(e){
      setSqliteProjectStatus({ok:false,error:String(e),database_files:[],node_packages:[]})
      return null
    }finally{
      if(!quiet) setSqliteProjectStatusBusy(false)
    }
  }

  const loadSqlDbObjects=async({quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(['firestore','redis'].includes(String(sqlProfile.db_type||'').toLowerCase())){
      setSqlDbObjects(null)
      setSqlDbObjectsError('')
      return null
    }
    if(!quiet) setSqlDbObjectsBusy(true)
    setSqlDbObjectsError('')
    try{
      const objects=await api(`/sql/objects?root=${encodeURIComponent(workspaceRoot)}`)
      setSqlDbObjects(objects)
      setSqlDbObjectExpanded(prev=>{
        const next={...prev}
        const firstSchema=objects?.schemas?.[0]
        if(firstSchema){
          const schemaKey=`schema:${firstSchema.name}`
          if(next[schemaKey]===undefined) next[schemaKey]=true
          const tableKey=`category:${firstSchema.name}:tables`
          if(next[tableKey]===undefined) next[tableKey]=true
        }
        return next
      })
      return objects
    }catch(e){
      setSqlDbObjects(null)
      setSqlDbObjectsError(String(e))
      return null
    }finally{
      if(!quiet) setSqlDbObjectsBusy(false)
    }
  }

  const resetFirestoreBrowser=()=>{
    setFirestoreBrowser(null)
    setFirestoreBrowserError('')
    setFirestoreSelectedCollection('')
    setFirestoreDocuments(null)
    setFirestoreSelectedDocument('')
    setFirestoreDocumentDetail(null)
  }

  const loadFirestoreDocumentDetail=async(path,{quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    const documentPath=String(path||'')
    if(!workspaceRoot||!documentPath) return null
    if(!quiet) setFirestoreDocumentDetailBusy(true)
    try{
      const detail=await api(`/sql/firestore/document?root=${encodeURIComponent(workspaceRoot)}&path=${encodeURIComponent(documentPath)}`)
      setFirestoreSelectedDocument(documentPath)
      setFirestoreDocumentDetail(detail)
      return detail
    }catch(e){
      setFirestoreDocumentDetail(null)
      setFirestoreBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setFirestoreDocumentDetailBusy(false)
    }
  }

  const loadFirestoreDocuments=async(collection,{quiet=false,preserveSelection=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    const collectionPath=String(collection||'')
    if(!workspaceRoot||!collectionPath) return null
    if(!quiet) setFirestoreDocumentsBusy(true)
    setFirestoreBrowserError('')
    try{
      const result=await api(`/sql/firestore/documents?root=${encodeURIComponent(workspaceRoot)}&collection=${encodeURIComponent(collectionPath)}&limit=500`)
      setFirestoreSelectedCollection(collectionPath)
      setFirestoreDocuments(result)
      const documents=Array.isArray(result?.documents)?result.documents:[]
      const previous=preserveSelection?String(firestoreSelectedDocument||''):''
      const nextPath=previous&&documents.some(item=>String(item?.path||'')===previous)?previous:(documents[0]?.path||'')
      if(nextPath){
        await loadFirestoreDocumentDetail(nextPath,{quiet:true})
      }else{
        setFirestoreSelectedDocument('')
        setFirestoreDocumentDetail(null)
      }
      return result
    }catch(e){
      setFirestoreDocuments(null)
      setFirestoreSelectedDocument('')
      setFirestoreDocumentDetail(null)
      setFirestoreBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setFirestoreDocumentsBusy(false)
    }
  }

  const loadFirestoreCollections=async({quiet=false,preserveSelection=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(!quiet) setFirestoreBrowserBusy(true)
    setFirestoreBrowserError('')
    try{
      const result=await api(`/sql/firestore/collections?root=${encodeURIComponent(workspaceRoot)}&limit=1000`)
      setFirestoreBrowser(result)
      const collections=Array.isArray(result?.collections)?result.collections:[]
      const previous=preserveSelection?String(firestoreSelectedCollection||''):''
      const nextCollection=previous&&collections.some(item=>String(item?.path||'')===previous)?previous:(collections[0]?.path||'')
      if(nextCollection){
        await loadFirestoreDocuments(nextCollection,{quiet:true,preserveSelection})
      }else{
        setFirestoreSelectedCollection('')
        setFirestoreDocuments(null)
        setFirestoreSelectedDocument('')
        setFirestoreDocumentDetail(null)
      }
      return result
    }catch(e){
      setFirestoreBrowser(null)
      setFirestoreDocuments(null)
      setFirestoreDocumentDetail(null)
      setFirestoreBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setFirestoreBrowserBusy(false)
    }
  }

  const resetRedisBrowser=()=>{
    setRedisBrowser(null)
    setRedisBrowserError('')
    setRedisSelectedKey('')
    setRedisKeyDetail(null)
    setRedisKeyExpanded({})
    setRedisContextMenu(null)
  }

  const loadRedisKeyDetail=async(key,{quiet=false}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    const keyName=String(key||'')
    if(!workspaceRoot||!keyName) return null
    if(!quiet) setRedisKeyDetailBusy(true)
    try{
      const detail=await api(`/sql/redis/key?root=${encodeURIComponent(workspaceRoot)}&key=${encodeURIComponent(keyName)}&max_items=500`)
      const observedAt=Date.now()
      const nextDetail=detail&&typeof detail==='object'
        ? {...detail,__ttl_observed_at_ms:observedAt}
        : detail
      setRedisSelectedKey(keyName)
      setRedisKeyDetail(nextDetail)
      return nextDetail
    }catch(e){
      setRedisKeyDetail(null)
      setRedisBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setRedisKeyDetailBusy(false)
    }
  }

  const loadRedisKeys=async({quiet=false,preserveSelection=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    if(!quiet) setRedisBrowserBusy(true)
    setRedisBrowserError('')
    try{
      const raw=String(redisKeyFilter||'').trim()
      const hasGlob=/[*?\[]/.test(raw)
      const pattern=raw?(hasGlob?raw:`*${raw}*`):'*'
      const result=await api(`/sql/redis/keys?root=${encodeURIComponent(workspaceRoot)}&pattern=${encodeURIComponent(pattern)}&limit=2000`)
      const observedAt=Date.now()
      const nextResult=result&&typeof result==='object'
        ? {...result,__ttl_observed_at_ms:observedAt}
        : result
      setRedisBrowser(nextResult)
      const keys=Array.isArray(nextResult?.keys)?nextResult.keys:[]
      const previous=preserveSelection?String(redisSelectedKey||''):''
      const nextKey=previous&&keys.some(item=>String(item?.key||'')===previous)?previous:(keys[0]?.key||'')
      if(nextKey){
        await loadRedisKeyDetail(nextKey,{quiet:true})
      }else{
        setRedisSelectedKey('')
        setRedisKeyDetail(null)
      }
      return nextResult
    }catch(e){
      setRedisBrowser(null)
      setRedisKeyDetail(null)
      setRedisBrowserError(String(e))
      return null
    }finally{
      if(!quiet) setRedisBrowserBusy(false)
    }
  }

  const toggleRedisKeyGroup=(path)=>{
    setRedisKeyExpanded(prev=>({...prev,[path]:prev[path]===false?true:false}))
  }

  const openFirestoreContextMenu=(event,node)=>{
    if(!sqlConnectionStatus?.connected||String(sqlProfile.db_type||'').toLowerCase()!=='firestore') return
    event.preventDefault()
    event.stopPropagation()
    const menuWidth=306
    const menuHeight=402
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    const nodeKind=node?.kind==='document'?'document':'collection'
    const path=String(node?.path||'')
    const label=String(node?.label||path||'Firestore')
    if(nodeKind==='collection'&&path){
      setFirestoreSelectedCollection(path)
      if(firestoreSelectedCollection!==path) loadFirestoreDocuments(path,{quiet:true,preserveSelection:false})
    }else if(nodeKind==='document'&&path){
      const parts=path.split('/').filter(Boolean)
      const collectionPath=parts.slice(0,-1).join('/')
      if(collectionPath) setFirestoreSelectedCollection(collectionPath)
      setFirestoreSelectedDocument(path)
      if(firestoreSelectedDocument!==path) loadFirestoreDocumentDetail(path,{quiet:true})
    }
    setRedisContextMenu(null)
    setSqlObjectContextMenu(null)
    setSqlDatabaseContextMenu(null)
    setFirestoreContextMenu({x,y,nodeKind,path,label})
  }

  const createFirestorePythonScript=async(action)=>{
    const menu=firestoreContextMenu
    if(!menu||!activeWorkspaceRoot||!sqlConnectionStatus?.connected||firestoreScriptBusy) return
    const normalized=String(action||'').toLowerCase()
    setFirestoreContextMenu(null)
    setFirestoreScriptBusy(normalized)
    try{
      const response=await api('/sql/firestore/script',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,action:normalized,path:menu.path||'',node_kind:menu.nodeKind||'collection'})
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{type:'success',text:response?.message||'Firestore 임시 Python 코드를 생성했습니다.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{type:'error',text:`Firestore Python 코드 생성 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setFirestoreScriptBusy('')
    }
  }

  const openRedisContextMenu=(event,node)=>{
    if(!sqlConnectionStatus?.connected||String(sqlProfile.db_type||'').toLowerCase()!=='redis') return
    event.preventDefault()
    event.stopPropagation()
    const menuWidth=286
    const menuHeight=390
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    const payload={
      x,y,
      nodeKind:node?.kind==='group'?'group':'key',
      key:String(node?.key||''),
      keyType:String(node?.keyType||''),
      prefix:String(node?.prefix||''),
      label:String(node?.label||node?.key||node?.prefix||'Redis'),
    }
    if(payload.nodeKind==='key'&&payload.key){
      setRedisSelectedKey(payload.key)
      if(redisSelectedKey!==payload.key) loadRedisKeyDetail(payload.key,{quiet:true})
    }
    setFirestoreContextMenu(null)
    setSqlObjectContextMenu(null)
    setSqlDatabaseContextMenu(null)
    setRedisContextMenu(payload)
  }

  const createRedisPythonScript=async(action)=>{
    const menu=redisContextMenu
    if(!menu||!activeWorkspaceRoot||!sqlConnectionStatus?.connected||redisScriptBusy) return
    const normalized=String(action||'').toLowerCase()
    setRedisContextMenu(null)
    setRedisScriptBusy(normalized)
    try{
      const response=await api('/sql/redis/script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          action:normalized,
          key:menu.key||'',
          key_type:menu.keyType||'',
          prefix:menu.prefix||'',
          node_kind:menu.nodeKind||'key',
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||'Redis 임시 Python 코드를 생성했습니다.',
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`Redis Python 코드 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setRedisScriptBusy('')
    }
  }


  useEffect(()=>{
    if(!redisContextMenu) return
    const close=()=>setRedisContextMenu(null)
    const onKey=(event)=>{if(event.key==='Escape') close()}
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[redisContextMenu])

  useEffect(()=>{
    if(!firestoreContextMenu) return
    const close=()=>setFirestoreContextMenu(null)
    const onKey=(event)=>{if(event.key==='Escape') close()}
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[firestoreContextMenu])

  const toggleSqlDbObject=(key)=>{
    setSqlDbObjectExpanded(prev=>({...prev,[key]:!prev[key]}))
  }

  const openSqlDbObject=async(schemaName,category,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:${category}:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/object-open',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category,
          name:item.name
        })
      })
      if(response?.relative_path){
        await openFile(response.relative_path)
      }
      if(response?.result){
        setSqlQueryResult(response.result)
        setSqlResultTab(response.result?.columns?.length?'DATA':'MESSAGES')
      }else{
        setSqlResultTab('MESSAGES')
      }
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 임시 SQL을 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`DB 객체 열기 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const openSqlObjectContextMenu=(event,schemaName,category,item)=>{
    if(category!=='tables'||!item?.name) return
    event.preventDefault()
    event.stopPropagation()
    const menuWidth=270
    const menuHeight=430
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    setSqlObjectContextMenu({x,y,schemaName,category,item})
  }

  const createSqlTableScript=async(schemaName,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:table-script:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category:'tables',
          name:item.name
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 테이블 스크립트를 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 스크립트 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const createSqlTableAlterScript=async(schemaName,item)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const busyKey=`${schemaName}:table-alter-script:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-alter-script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          category:'tables',
          name:item.name
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} 테이블 수정 스크립트를 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 수정 스크립트 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const createSqlTableDmlScript=async(schemaName,item,action)=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected||!item?.name) return
    const normalized=String(action||'').toLowerCase()
    const busyKey=`${schemaName}:table-${normalized}-script:${item.name}`
    if(sqlObjectActionBusy) return
    setSqlObjectContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/table-dml-script',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          schema:schemaName,
          name:item.name,
          action:normalized,
        })
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||`${schemaName}.${item.name} ${normalized.toUpperCase()} 스크립트를 생성했습니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`테이블 ${normalized.toUpperCase()} 스크립트 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const openSqlDatabaseContextMenu=(event)=>{
    if(!sqlConnectionStatus?.connected) return
    event.preventDefault()
    event.stopPropagation()
    setSqlObjectContextMenu(null)
    const menuWidth=310
    const menuHeight=520
    const x=Math.max(8,Math.min(event.clientX,window.innerWidth-menuWidth-8))
    const y=Math.max(8,Math.min(event.clientY,window.innerHeight-menuHeight-8))
    setSqlDatabaseContextMenu({x,y})
  }

  const createPostgresqlAdminScript=async(action,value='')=>{
    if(!activeWorkspaceRoot||!sqlConnectionStatus?.connected) return
    if(sqlObjectActionBusy) return
    const busyKey=`database-admin:${action}`
    setSqlDatabaseContextMenu(null)
    setSqlObjectActionBusy(busyKey)
    try{
      const response=await api('/sql/postgresql-admin-script',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,action,value:String(value??'')})
      })
      if(response?.relative_path){
        await loadFiles()
        await openFile(response.relative_path)
      }
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:response?.message||'PostgreSQL 관리 SQL을 임시 파일로 생성했습니다.',
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{
        type:'error',
        text:`PostgreSQL 관리 SQL 생성 실패: ${e}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }finally{
      setSqlObjectActionBusy('')
    }
  }

  const openSqlAdminPrompt=(action)=>{
    const configs={
      table_locks:{title:'특정 테이블 Lock만 보기',label:'테이블 이름',placeholder:'customers',value:'customers',danger:false},
      cancel_backend:{title:'쿼리만 중지하고 DB 접속 유지',label:'중지할 세션 PID',placeholder:'예: 138',value:'',danger:true},
      terminate_backend:{title:'DB 연결 자체를 강제로 종료',label:'종료할 세션 PID',placeholder:'예: 138',value:'',danger:true},
      terminate_others:{title:'다른 세션만 종료',label:'종료 대상 세션 상태',placeholder:'idle in transaction',value:'idle in transaction',danger:true},
    }
    const config=configs[action]
    if(!config) return
    setSqlDatabaseContextMenu(null)
    setSqlAdminPrompt({action,...config})
  }

  const submitSqlAdminPrompt=async()=>{
    const prompt=sqlAdminPrompt
    if(!prompt) return
    const value=String(prompt.value??'').trim()
    if(!value){
      return
    }
    setSqlAdminPrompt(null)
    await createPostgresqlAdminScript(prompt.action,value)
  }

  useEffect(()=>{
    if(!sqlObjectContextMenu) return
    const close=()=>setSqlObjectContextMenu(null)
    const onKey=(event)=>{ if(event.key==='Escape') close() }
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[sqlObjectContextMenu])

  useEffect(()=>{
    if(!sqlDatabaseContextMenu) return
    const close=()=>setSqlDatabaseContextMenu(null)
    const onKey=(event)=>{ if(event.key==='Escape') close() }
    window.addEventListener('mousedown',close)
    window.addEventListener('scroll',close,true)
    window.addEventListener('resize',close)
    window.addEventListener('keydown',onKey,true)
    return ()=>{
      window.removeEventListener('mousedown',close)
      window.removeEventListener('scroll',close,true)
      window.removeEventListener('resize',close)
      window.removeEventListener('keydown',onKey,true)
    }
  },[sqlDatabaseContextMenu])

  const loadSqlWorkspaceProfileForType=async(dbType)=>{
    // v5.239 compatibility helper: create a new unsaved profile of the chosen DB type.
    const kind=String(dbType||'postgresql').toLowerCase()
    const fresh=sqlProfileForType(kind)
    setSqlProfile(fresh)
    if(kind==='sqlite3') await loadSqliteProjectStatus({quiet:true})
    return fresh
  }

  const loadSqlWorkspaceStatus=async()=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot) return null
    try{
      const status=await api(`/sql/status?root=${encodeURIComponent(workspaceRoot)}`)
      const rootChanged=sqlLoadedRootRef.current!==workspaceRoot
      sqlLoadedRootRef.current=workspaceRoot
      applySqlWorkspaceStatus(status,{preservePassword:!rootChanged})
      if(status?.connected&&status?.profile?.db_type==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true})
      }else if(status?.connected&&status?.profile?.db_type==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true})
      }else if(status?.connected){
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }else{
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        resetFirestoreBrowser()
        resetRedisBrowser()
      }
      return status
    }catch(e){
      setSqlConnections([])
      setSqlConnectionStatus({connected:false,error:String(e),connections:[]})
      return null
    }
  }

  const saveSqlWorkspaceProfile=async()=>{
    if(!activeWorkspaceRoot) return
    setSqlConnectionBusy(true)
    try{
      const result=await api('/sql/profile',{
        method:'POST',
        body:JSON.stringify({...sqlProfile,root:activeWorkspaceRoot})
      })
      if(Array.isArray(result?.connections)) setSqlConnections(result.connections)
      setSqlProfile(prev=>({
        ...sqlProfileForType(result?.profile?.db_type||prev.db_type,result?.profile||prev),
        password:prev.password
      }))
      const status=await api(`/sql/status?root=${encodeURIComponent(activeWorkspaceRoot)}`)
      applySqlWorkspaceStatus(status,{preservePassword:false})
      setSqlMessages(prev=>[{
        type:'info',
        text:`DB 연결 정보를 저장했습니다. · ${result?.profile?.name||sqlProfile.name||String(sqlProfile.db_type||'').toUpperCase()}${result?.profile?.credential_saved?' · 비밀번호 Windows 보안 저장 완료':''}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 설정 저장 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const renameSqlWorkspaceConnection=async()=>{
    if(!activeWorkspaceRoot||!sqlProfile.connection_id) return
    const nextName=String(sqlProfile.name||'').trim()
    if(!nextName){
      setSqlMessages(prev=>[{type:'warning',text:'변경할 연결 이름을 입력하세요.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      return
    }
    setSqlConnectionBusy(true)
    try{
      const result=await api('/sql/profile/rename',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id,name:nextName})
      })
      applySqlWorkspaceStatus(result,{preservePassword:true})
      setSqlMessages(prev=>[{
        type:'info',
        text:`DB 연결 이름을 '${result?.profile?.name||nextName}'(으)로 변경했습니다. 연결 ID와 저장된 자격증명은 그대로 유지됩니다.`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 이름 변경 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const deleteSqlWorkspaceConnection=async()=>{
    if(!activeWorkspaceRoot||!sqlProfile.connection_id) return
    const label=sqlProfile.name||String(sqlProfile.db_type||'DB').toUpperCase()
    if(!window.confirm(`저장된 DB 연결 '${label}'을 삭제하시겠습니까?\n현재 연결 중이면 연결도 함께 해제됩니다.`)) return
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/profile/delete',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id})
      })
      applySqlWorkspaceStatus(status,{preservePassword:false})
      if(!status?.profile?.connection_id) newSqlWorkspaceConnection(sqlProfile.db_type)
      if(status?.connected&&status?.profile?.db_type==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true,preserveSelection:false})
      }else if(status?.connected&&status?.profile?.db_type==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true,preserveSelection:false})
      }else if(status?.connected){
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }else{
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        resetFirestoreBrowser()
        resetRedisBrowser()
      }
      setSqlMessages(prev=>[{type:'info',text:`DB 연결 '${label}'을 삭제했습니다.`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 삭제 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const connectSqlWorkspace=async()=>{
    if(!activeWorkspaceRoot) return
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/connect',{
        method:'POST',
        body:JSON.stringify({...sqlProfile,root:activeWorkspaceRoot})
      })
      applySqlWorkspaceStatus(status,{preservePassword:false})
      setSqlMessages(prev=>[{
        type:'success',
        text:`${status?.profile?.name||String(status?.profile?.db_type||sqlProfile.db_type).toUpperCase()} 연결 성공${status?.profile?.credential_saved?' · 저장된 보안 자격증명 사용 가능':''}`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
      if((status?.profile?.db_type||sqlProfile.db_type)==='redis'){
        resetFirestoreBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadRedisKeys({quiet:true,preserveSelection:false})
      }else if((status?.profile?.db_type||sqlProfile.db_type)==='firestore'){
        resetRedisBrowser()
        setSqlDbObjects(null)
        setSqlDbObjectsError('')
        setSqlDbObjectExpanded({})
        await loadFirestoreCollections({quiet:true,preserveSelection:false})
      }else{
        resetFirestoreBrowser()
        resetRedisBrowser()
        await loadSqlDbObjects({quiet:true})
      }
      if((status?.profile?.db_type||sqlProfile.db_type)==='sqlite3') await loadSqliteProjectStatus({quiet:true})
    }catch(e){
      setSqlConnectionStatus(prev=>({...prev,connected:false,error:String(e)}))
      setSqlMessages(prev=>[{type:'error',text:`DB 연결 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const disconnectSqlWorkspace=async()=>{
    if(!activeWorkspaceRoot) return
    setSqlConnectionBusy(true)
    try{
      const status=await api('/sql/disconnect',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id||''})
      })
      applySqlWorkspaceStatus(status,{preservePassword:true})
      setSqlDbObjects(null)
      setSqlDbObjectsError('')
      setSqlDbObjectExpanded({})
      resetFirestoreBrowser()
      resetRedisBrowser()
      setSqlMessages(prev=>[{type:'info',text:`${sqlProfile.name||'데이터베이스'} 연결을 해제했습니다.`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`연결 해제 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }finally{
      setSqlConnectionBusy(false)
    }
  }

  const runSqlEditor=async({selectionOnly=false}={})=>{
    if(!isSqlFile||sqlQueryBusy) return
    if(!sqlConnectionStatus?.connected){
      setSqlResultTab('MESSAGES')
      setSqlMessages(prev=>[{type:'warning',text:'현재 선택된 DB 연결이 연결되어 있지 않습니다. 저장된 연결을 선택해 연결한 뒤 SQL을 실행하세요.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      return
    }
    let statement=code||''
    let label='전체 SQL'
    if(selectionOnly){
      const editor=editorInstanceRef.current
      const selection=editor?.getSelection?.()
      const model=editor?.getModel?.()
      const selectedText=(selection&&model)?model.getValueInRange(selection):''
      if(!selectedText.trim()){
        setSqlResultTab('MESSAGES')
        setSqlMessages(prev=>[{type:'warning',text:'선택된 SQL이 없습니다.',time:new Date().toLocaleTimeString()},...prev].slice(0,100))
        return
      }
      statement=selectedText
      label='선택 SQL'
    }
    if(!statement.trim()) return

    sqlStopRequestedRef.current=false
    setSqlQueryBusy(true)
    try{
      const result=await api('/sql/execute',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,sql:statement,max_rows:1000})
      })
      setSqlQueryResult(result)
      setSqlResultTab(result?.columns?.length?'DATA':'MESSAGES')
      setSqlMessages(prev=>[{
        type:'success',
        text:`${label} 실행 완료 · ${result?.message||''} · ${result?.elapsed_ms||0}ms`,
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlResultTab('MESSAGES')
      if(sqlStopRequestedRef.current){
        setSqlMessages(prev=>[{type:'warning',text:`${label} 실행을 사용자가 중지했습니다.`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      }else{
        setSqlMessages(prev=>[{type:'error',text:`${label} 실행 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
      }
    }finally{
      setSqlQueryBusy(false)
      sqlStopRequestedRef.current=false
    }
  }

  const stopSqlExecution=async()=>{
    if(!activeWorkspaceRoot||!sqlQueryBusy) return
    sqlStopRequestedRef.current=true
    try{
      const result=await api('/sql/cancel',{
        method:'POST',
        body:JSON.stringify({root:activeWorkspaceRoot,connection_id:sqlProfile.connection_id||''})
      })
      setSqlMessages(prev=>[{
        type:result?.cancelled?'warning':'info',
        text:result?.message||'SQL 실행 중지 요청을 보냈습니다.',
        time:new Date().toLocaleTimeString()
      },...prev].slice(0,100))
    }catch(e){
      setSqlMessages(prev=>[{type:'error',text:`SQL 실행 중지 실패: ${e}`,time:new Date().toLocaleTimeString()},...prev].slice(0,100))
    }
  }

  useEffect(()=>{
    if(workspaceTab!=='CODE') return
    if(isSqlFile){
      setCodeRightPanelTab('SQL_DB')
      setWorkspaceRightCollapsed(false)
      loadSqlWorkspaceStatus()
      loadSqliteProjectStatus({quiet:true})
    }
  },[workspaceTab,selected,activeWorkspaceRoot])

  const refreshAiRuntimeStatus=async()=>{
    try{
      const status=await api('/llm/runtime-status')
      setAiRuntimeStatus(status)
      setAiModeError('')
      return status
    }catch(e){
      setAiModeError(String(e))
      return null
    }
  }

  const applyAiMode=async(mode)=>{
    if(aiModeBusy) return
    if(mode==='ollama'&&!aiRuntimeStatus?.providers?.ollama?.connected) return
    if(mode==='openai'&&!aiRuntimeStatus?.providers?.openai?.configured) return

    const values=mode==='openai'
      ? {
          LOCAL_LLM_PROVIDER:'openai',
          CODING_LLM_PROVIDER:'openai',
          REQUIREMENTS_LLM_PROVIDER:'openai'
        }
      : mode==='ollama'
        ? {
            LOCAL_LLM_PROVIDER:'ollama',
            CODING_LLM_PROVIDER:'ollama',
            REQUIREMENTS_LLM_PROVIDER:'ollama'
          }
        : {
            LOCAL_LLM_PROVIDER:'ollama',
            CODING_LLM_PROVIDER:'openai',
            REQUIREMENTS_LLM_PROVIDER:'openai'
          }

    setAiModeBusy(true)
    setAiModeError('')
    try{
      await api('/settings',{
        method:'POST',
        body:JSON.stringify({values})
      })
      await refreshAiRuntimeStatus()
      setAiModeMenuOpen(false)
    }catch(e){
      setAiModeError(String(e))
    }finally{
      setAiModeBusy(false)
    }
  }

  const aiModeName={auto:'AUTO',openai:'OpenAI',ollama:'Ollama'}[aiRuntimeStatus?.mode]||'확인 중'
  const aiPrimaryProvider=(aiRuntimeStatus?.primary_provider||'').toLowerCase()
  const aiPrimaryModel=aiRuntimeStatus?.primary_model||''
  const aiPrimaryProviderLabel=aiPrimaryProvider==='openai'?'OpenAI':aiPrimaryProvider==='ollama'?'Ollama':''
  const aiModeHeaderLabel=aiRuntimeStatus
    ? `AI 모드 · ${aiModeName} · ${aiPrimaryProviderLabel}${aiPrimaryModel?` · ${aiPrimaryModel}`:''}`
    : 'AI 모드 · 상태 확인 중'
  const aiInterviewLabel=aiRuntimeStatus
    ? `${aiModeName} · ${aiPrimaryProviderLabel}${aiPrimaryModel?` · ${aiPrimaryModel}`:''}`
    : 'AI 상태 확인 중'

  useEffect(()=>{
    refreshAiRuntimeStatus()
  },[])

  const diagnoseProjectDatabase=async()=>{
    try{
      const result=await api('/projects/diagnostics')
      setProjectDbDiagnostic(result)

      const logPath=
        result?.api_log_path
        || result?.backend_log_path
        || ''

      setProjectListLogPath(logPath)

      return result
    }catch(e){
      setProjectDbDiagnostic({
        ok:false,
        message:String(e),
        path:'Frontend -> FastAPI -> PostgreSQL'
      })

      setProjectListLogPath(
        'FastAPI 진단 API 호출 자체가 실패했습니다. Backend 로그: <AgentStudio>\\logs\\system_manager.log'
      )

      return null
    }
  }

  const refreshProjectList=async()=>{
    setProjectListLoading(true)
    setProjectListLogPath('')

    try{
      // 프로젝트 목록은 반드시 FastAPI를 통해 조회합니다.
      // Frontend가 PostgreSQL에 직접 연결하지 않습니다.
      const rows=await api('/projects')
      const normalized=Array.isArray(rows)?rows:[]

      setProjectList(normalized)
      setProjectListStatus(
        `FastAPI → PostgreSQL 연결 정상 · DB 프로젝트 ${normalized.length}건 로드됨`
      )

      // 성공한 경우에도 실제 DB 경로/건수를 진단 API로 확인합니다.
      const diag=await diagnoseProjectDatabase()
      if(diag?.ok){
        setProjectListStatus(
          `FastAPI → PostgreSQL 연결 정상 · DB 프로젝트 ${diag.project_count}건`
        )
      }

      return normalized
    }catch(e){
      console.error('프로젝트 목록 새로고침 실패',e)

      setProjectList([])
      setProjectListStatus(
        'FastAPI 프로젝트 목록 호출 실패: '+String(e)
      )

      // REST 호출이 실패했을 때 가능한 경우 진단 API를 추가 호출하여
      // DB 오류인지 FastAPI/CORS/서버 오류인지 구분하고 로그 경로를 표시합니다.
      const diag=await diagnoseProjectDatabase()

      if(diag?.ok===false){
        setProjectListStatus(
          'FastAPI는 응답했지만 PostgreSQL 조회 실패: '
          +(diag.message||'상세 로그를 확인하세요.')
        )
      }else if(!diag){
        setProjectListStatus(
          'FastAPI 프로젝트 API 호출 실패: '+String(e)
        )
      }

      return []
    }finally{
      setProjectListLoading(false)
    }
  }

  const loadGitInfo=async(rootOverride=null)=>{
    const targetRoot=rootOverride||root
    if(!targetRoot){
      setGitInfo(null)
      return null
    }

    setGitInfoLoading(true)
    try{
      const info=await api(`/project/git-info?root=${encodeURIComponent(targetRoot)}`)
      setGitInfo(info)
      return info
    }catch(e){
      setGitInfo({
        ok:false,
        is_git:false,
        message:String(e)
      })
      return null
    }finally{
      setGitInfoLoading(false)
    }
  }

  const runGitAction=async(action)=>{
    if(!root) return null

    if((action==='commit'||action==='sync')&&!gitCommitMessage.trim()){
      setGitActionResult({
        ok:false,
        action,
        stderr:'커밋 메시지를 입력하세요.'
      })
      return null
    }

    setGitActionBusy(action)
    setGitActionResult(null)

    try{
      const result=await api('/project/git-action',{
        method:'POST',
        body:JSON.stringify({
          root,
          action,
          message:gitCommitMessage.trim()
        })
      })

      setGitActionResult(result)

      if(result?.ok){
        await loadGitInfo(root)
        if(action==='sync'||action==='commit'){
          setGitCommitMessage('')
        }
      }

      return result
    }catch(e){
      setGitActionResult({
        ok:false,
        action,
        stderr:String(e)
      })
      return null
    }finally{
      setGitActionBusy('')
    }
  }



  const activateProjectTerminal=async(project)=>{
    const projectId=project?.id
    const projectRoot=project?.project_root||project?.root_path||''
    if(!projectId||!projectRoot) return null

    const sessionId=`project-${projectId}`
    setActiveTerminalProjectId(projectId)

    const existing=terminalSessions.find(t=>t.id===sessionId)

    // 프로젝트를 이동해도 이미 만들어진 터미널은 그대로 유지합니다.
    // 사용자가 × 버튼으로 닫기 전에는 새로 만들거나 WebSocket을 교체하지 않습니다.
    if(existing){
      setActiveTerminalId(sessionId)

      // WebSocket이 닫혔더라도 Backend PowerShell 세션은 살아 있을 수 있습니다.
      // 같은 sessionId로 다시 연결하면 Backend가 기존 세션을 재사용하고
      // history를 보내 줍니다.
      if(existing.processState!=='exited'){
        await connectProjectTerminal(project,sessionId)
      }

      const restoreView=()=>{
        const term=xtermInstancesRef.current[sessionId]
        fitTerminalViewport(sessionId)
        try{
          if(term){
            term.refresh(0,Math.max(0,term.rows-1))
            term.scrollToBottom()
          }
        }catch{}

        if(
          existing.processState!=='exited'
          && canAutoFocusTerminal()
        ){
          try{ term?.focus() }catch{}
        }
      }

      setTimeout(restoreView,30)
      setTimeout(restoreView,150)
      setTimeout(restoreView,350)

      return sessionId
    }

    const session={
      id:sessionId,
      name:project?.name
        ? `${project.name} PowerShell`
        : 'Project PowerShell',
      projectId,
      projectName:project?.name||'',
      root:projectRoot,
      cwd:projectRoot,
      command:'',
      output:'',
      busy:false,
      processState:'starting',
      exitCode:null,
    }

    setTerminalSessions(prev=>[
      ...prev,
      session
    ])

    setActiveTerminalId(sessionId)

    await connectProjectTerminal(project,sessionId)

    setTimeout(async()=>{
      await ensureXtermInstance(sessionId)
      if(canAutoFocusTerminal()){
        focusXterm(sessionId)
      }
    },100)

    return sessionId
  }



  const processTerminalRawOutput=(sessionId,incoming,{reset=false}={})=>{
    const term=xtermInstancesRef.current[sessionId]

    if(reset){
      xtermOutputParseBufferRef.current[sessionId]=''
      xtermPromptRef.current[sessionId]=''
      xtermCommandBuffersRef.current[sessionId]=''
      xtermCursorIndexRef.current[sessionId]=0
      terminalCommandBusyRef.current[sessionId]=false
      xtermRequiredColsRef.current[sessionId]=0

      try{
        term?.reset()
        term?.clear()
      }catch{}
    }

    const pending=xtermOutputParseBufferRef.current[sessionId]||''
    const combined=pending+(incoming||'')
    const normalized=combined.replace(/\r\n/g,'\n')
    const parts=normalized.split('\n')
    const complete=parts.slice(0,-1)

    xtermOutputParseBufferRef.current[sessionId]=
      normalized.endsWith('\n')
        ? ''
        : parts[parts.length-1]

    const visible=[]
    let nextCwd=null
    let nextPrompt=null

    for(const line of complete){
      if(line.startsWith('__THEANOVA_CWD__=')){
        nextCwd=line.slice('__THEANOVA_CWD__='.length).trim()
        continue
      }

      if(line.startsWith('__THEANOVA_PROMPT__=')){
        nextPrompt=line.slice('__THEANOVA_PROMPT__='.length)
        continue
      }

      visible.push(line)
    }

    if(nextCwd){
      terminalCwdRef.current[sessionId]=nextCwd
      setTerminalSessions(prev=>prev.map(t=>
        t.id===sessionId
          ? {...t,cwd:nextCwd}
          : t
      ))
    }

    if(visible.length){
      writeXterm(
        sessionId,
        visible.join('\r\n')+'\r\n'
      )
    }

    if(nextPrompt!==null){
      xtermPromptRef.current[sessionId]=nextPrompt
      xtermCommandBuffersRef.current[sessionId]=''
      xtermCursorIndexRef.current[sessionId]=0
      terminalCommandBusyRef.current[sessionId]=false
      setTerminalSessions(prev=>prev.map(t=>t.id===sessionId?{...t,busy:false,interrupting:false}:t))
      fitTerminalViewport(sessionId)
      writeXterm(sessionId,nextPrompt)
      requestAnimationFrame(()=>{
        const promptTerm=xtermInstancesRef.current[sessionId]
        promptTerm?.scrollToBottom()
        if(
          activeTerminalId===sessionId
          && canAutoFocusTerminal()
        ){
          try{ promptTerm?.focus() }catch{}
        }
      })
    }

    requestAnimationFrame(()=>{
      const activeTerm=xtermInstancesRef.current[sessionId]

      fitTerminalViewport(sessionId)
      try{
        if(activeTerm){
          activeTerm.refresh(
            0,
            Math.max(0,activeTerm.rows-1)
          )
          activeTerm.scrollToBottom()
        }
      }catch{}
    })
  }


  const connectProjectTerminal=async(project,sessionId)=>{
    setTerminalErrors(prev=>({
      ...prev,
      [sessionId]:null
    }))

    const projectRoot=
      project?.project_root
      || project?.root_path
      || ''

    if(!projectRoot) return null

    terminalRootRef.current[sessionId]=projectRoot
    if(!terminalCwdRef.current[sessionId]){
      terminalCwdRef.current[sessionId]=projectRoot
    }

    const existing=terminalSocketsRef.current[sessionId]

    if(existing&&existing.readyState===WebSocket.OPEN){
      return existing
    }

    const cfg=window.__AGENTSTUDIO_CONFIG__||{}
    const host=cfg.BACKEND_HOST||window.location.hostname||'127.0.0.1'
    const port=cfg.BACKEND_PORT||8000
    const protocol=window.location.protocol==='https:'?'wss':'ws'

    const wsUrl=
      `${protocol}://${host}:${port}/ws/terminal/${encodeURIComponent(sessionId)}`
      + `?root=${encodeURIComponent(projectRoot)}`
      + `&project_name=${encodeURIComponent(project?.name||'')}`

    const ws=new WebSocket(wsUrl)
    terminalSocketsRef.current[sessionId]=ws

    setTerminalErrors(prev=>({
      ...prev,
      [sessionId]:null
    }))

    setTerminalConnectionState(prev=>({
      ...prev,
      [sessionId]:'connecting'
    }))

    ws.onopen=()=>{
      setTerminalConnectionState(prev=>({
        ...prev,
        [sessionId]:'connected'
      }))
    }

    ws.onmessage=(event)=>{
      try{
        const msg=parseTerminalServerMessage(event.data)

        if(msg.type==='history'){
          processTerminalRawOutput(
            sessionId,
            msg.data||'',
            {reset:true}
          )
          return
        }

        if(msg.type==='output'){
          processTerminalRawOutput(
            sessionId,
            msg.data||''
          )
        }

        if(msg.type==='ready'){
          setTerminalErrors(prev=>({
            ...prev,
            [sessionId]:null
          }))
          setTerminalConnectionState(prev=>({
            ...prev,
            [sessionId]:'connected'
          }))

          setTerminalSessions(prev=>prev.map(t=>
            t.id===sessionId
              ? {
                  ...t,
                  hasVenv:!!msg.has_venv,
                  cwd:t.cwd||projectRoot,
                  processState:'running',
                  exitCode:null,
                  interrupting:false
                }
              : t
          ))

          setTimeout(async()=>{
            await ensureXtermInstance(sessionId)

            if(canAutoFocusTerminal()){
              focusXterm(sessionId)
            }
          },50)
        }

        if(msg.type==='cleared'){
          return
        }

        if(msg.type==='interrupted'){
          // 'interrupted' means that the stop signal/child-tree termination
          // request was delivered.  It does NOT mean PowerShell has already
          // returned to its prompt.  Keep the command busy until the prompt
          // marker arrives so a second Ctrl+C can still be sent if shutdown
          // is taking longer than expected.  The prompt can race ahead of
          // this ACK, so ignore a late ACK once the parser already marked the
          // command idle.
          if(terminalCommandBusyRef.current[sessionId]){
            setTerminalSessions(prev=>prev.map(t=>
              t.id===sessionId
                ? {
                    ...t,
                    busy:true,
                    interrupting:true
                  }
                : t
            ))
          }
        }

        if(msg.type==='process_exit'){
          const exitCode=msg.exit_code
          terminalCommandBusyRef.current[sessionId]=false

          setTerminalSessions(prev=>prev.map(t=>
            t.id===sessionId
              ? {
                  ...t,
                  processState:'exited',
                  exitCode,
                  command:'',
                  busy:false,
                  interrupting:false
                }
              : t
          ))

          setTerminalConnectionState(prev=>({
            ...prev,
            [sessionId]:'closed'
          }))

          writeXterm(
            sessionId,
            `\r\n[터미널 종료] PowerShell 프로세스가 종료되었습니다. ExitCode=${exitCode ?? '-'}\r\n`
          )

          return
        }

        if(msg.type==='error'){
          const errorInfo={
            stage:msg.stage||'websocket',
            message:msg.message||'알 수 없는 터미널 오류',
            detail:msg.detail||'',
            logPath:msg.log_path||'',
            sessionId:msg.session_id||sessionId,
            root:msg.root||projectRoot,
            wsUrl,
            time:new Date().toLocaleString()
          }

          setTerminalErrors(prev=>({
            ...prev,
            [sessionId]:errorInfo
          }))

          setTerminalSessions(prev=>prev.map(t=>
            t.id===sessionId
              ? {
                  ...t,
                  output:
                    (t.output||'')
                    + '\n[ERROR] '
                    + errorInfo.message
                    + '\n'
                    + (
                      errorInfo.logPath
                        ? `[로그] ${errorInfo.logPath}\n`
                        : ''
                    )
                }
              : t
          ))
        }

      }catch(e){
        const errorInfo={
          stage:'message_parse',
          message:String(e),
          detail:'',
          logPath:'',
          sessionId,
          root:projectRoot,
          wsUrl,
          time:new Date().toLocaleString()
        }

        setTerminalErrors(prev=>({
          ...prev,
          [sessionId]:errorInfo
        }))
      }
    }

    ws.onerror=(event)=>{
      const errorInfo={
        stage:'websocket_error',
        message:'WebSocket 연결/통신 오류가 발생했습니다.',
        detail:
          `readyState=${ws.readyState}\n`
          + `url=${wsUrl}`,
        logPath:'',
        sessionId,
        root:projectRoot,
        wsUrl,
        time:new Date().toLocaleString()
      }

      setTerminalErrors(prev=>({
        ...prev,
        [sessionId]:errorInfo
      }))

      setTerminalConnectionState(prev=>({
        ...prev,
        [sessionId]:'error'
      }))
    }

    ws.onclose=(event)=>{
          if(terminalIntentionalCloseRef.current[sessionId]){
            terminalIntentionalCloseRef.current[sessionId]=false
            return
          }

      setTerminalConnectionState(prev=>({
        ...prev,
        [sessionId]:'closed'
      }))

      if(
        event.code!==1000
        && !terminalErrors[sessionId]
      ){
        const errorInfo={
          stage:'websocket_close',
          message:`WebSocket가 비정상 종료되었습니다. code=${event.code}`,
          detail:`reason=${event.reason||'(없음)'}`,
          logPath:'',
          sessionId,
          root:projectRoot,
          wsUrl,
          time:new Date().toLocaleString()
        }

        setTerminalErrors(prev=>({
          ...prev,
          [sessionId]:errorInfo
        }))
      }

      if(terminalSocketsRef.current[sessionId]===ws){
        delete terminalSocketsRef.current[sessionId]
      }
    }

    return ws
  }

  useEffect(()=>{
    // 기본 PowerShell 탭은 선택 프로젝트가 아니라 AgentStudio 설치 경로를 사용합니다.
    // SYSTEM_ADMIN.ps1이 runtime-config.js에 실제 설치 경로를 기록합니다.
    const cfg=window.__AGENTSTUDIO_CONFIG__||{}
    const agentStudioRoot=String(cfg.AGENTSTUDIO_ROOT||'').trim()
    const sessionId='terminal-1'

    if(!agentStudioRoot) return

    terminalRootRef.current[sessionId]=agentStudioRoot
    terminalCwdRef.current[sessionId]=agentStudioRoot

    setTerminalSessions(prev=>prev.map(t=>
      t.id===sessionId
        ? {
            ...t,
            name:'PowerShell',
            projectId:'agentstudio-root',
            projectName:'AgentStudio',
            root:agentStudioRoot,
            cwd:agentStudioRoot,
            processState:t.processState==='exited'?'exited':'starting'
          }
        : t
    ))

    let cancelled=false
    const connectDefault=async()=>{
      try{
        await ensureXtermInstance(sessionId)
        if(cancelled) return
        await connectProjectTerminal({
          id:'agentstudio-root',
          name:'AgentStudio',
          project_root:agentStudioRoot
        },sessionId)
      }catch(e){
        console.error('기본 AgentStudio PowerShell 연결 실패',e)
      }
    }

    const timer=setTimeout(connectDefault,80)
    return()=>{
      cancelled=true
      clearTimeout(timer)
    }
    // runtime config는 앱 시작 시 고정되므로 한 번만 연결합니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[])

  const sendTerminalInput=async(id)=>{
    const target=terminalSessions.find(t=>t.id===id)
    if(!target||!target.command.trim()) return

    let ws=terminalSocketsRef.current[id]

    if(!ws||ws.readyState!==WebSocket.OPEN){
      ws=await connectProjectTerminal(
        {
          id:target.projectId,
          name:target.projectName,
          project_root:target.root||root
        },
        id
      )
    }

    if(!ws) return

    if(ws.readyState===WebSocket.CONNECTING){
      await new Promise(resolve=>{
        const done=()=>resolve()
        ws.addEventListener('open',done,{once:true})
        setTimeout(resolve,2500)
      })
    }

    if(ws.readyState!==WebSocket.OPEN){
      setTerminalSessions(prev=>prev.map(t=>
        t.id===id
          ? {
              ...t,
              output:(t.output||'')
                + '\n[ERROR] 터미널 연결이 열리지 않았습니다.\n'
            }
          : t
      ))
      return
    }

    const cmd=target.command.trim()
    const cwd=target.cwd||target.root||root||''
    const prompt=`${target.hasVenv?'(.venv) ':''}PS ${cwd}> `

    setTerminalSessions(prev=>prev.map(t=>
      t.id===id
        ? {
            ...t,
            command:'',
            output:(t.output||'')
              + (t.output?.endsWith('\n')||!t.output?'':'\n')
              + prompt
              + cmd
              + '\n'
          }
        : t
    ))

    terminalCommandBusyRef.current[id]=true
    setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,busy:true,interrupting:false}:t))
    ws.send(serializeTerminalClientMessage({
      type:'input',
      data:cmd+'\r\n'
    }))

    scrollTerminalToBottom(id,'auto')

    setTimeout(()=>{
      terminalInlineInputRef.current?.focus()
    },30)
  }

  const interruptTerminal=(id)=>{
    const ws=terminalSocketsRef.current[id]
    if(ws&&ws.readyState===WebSocket.OPEN){
      // Keep the command in a busy/interrupting state until the backend
      // command wrapper emits the normal prompt marker.  This prevents the
      // first Ctrl+C acknowledgement from making later Ctrl+C presses local
      // only while Streamlit/Python is still shutting down.
      terminalCommandBusyRef.current[id]=true
      setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,busy:true,interrupting:true}:t))
      ws.send(serializeTerminalClientMessage({type:'interrupt'}))
    }
  }


  const setTerminalCompletionState=(next)=>{
    terminalCompletionRef.current=next
    setTerminalCompletion(next)
  }

  const closeTerminalCompletion=(sessionId=null)=>{
    const current=terminalCompletionRef.current
    if(sessionId){
      clearTimeout(terminalCompletionTimerRef.current[sessionId])
      delete terminalCompletionTimerRef.current[sessionId]
    }else{
      Object.values(terminalCompletionTimerRef.current).forEach(timer=>clearTimeout(timer))
      terminalCompletionTimerRef.current={}
    }
    if(!current) return
    if(sessionId&&current.sessionId!==sessionId) return
    setTerminalCompletionState(null)
  }

  const moveTerminalCompletionSelection=(delta)=>{
    const current=terminalCompletionRef.current
    if(!current?.items?.length) return
    const length=current.items.length
    const selectedIndex=(current.selectedIndex+delta+length)%length
    setTerminalCompletionState({...current,selectedIndex})
  }

  const applyTerminalCompletion=(itemOverride=null)=>{
    const current=terminalCompletionRef.current
    if(!current) return false

    const item=itemOverride||current.items?.[current.selectedIndex]
    if(!item) return false

    const id=current.sessionId
    const buffer=xtermCommandBuffersRef.current[id]||''
    const start=Math.max(0,Math.min(current.replaceStart??0,buffer.length))
    const end=Math.max(start,Math.min(current.replaceEnd??start,buffer.length))
    const insertText=String(item.insert_text??item.label??'')
    const nextBuffer=buffer.slice(0,start)+insertText+buffer.slice(end)
    const nextCursor=start+insertText.length
    const setter=xtermSetCommandLineRef.current[id]

    if(typeof setter==='function'){
      setter(nextBuffer,nextCursor)
      closeTerminalCompletion(id)
      setTimeout(()=>focusXterm(id),0)
      return true
    }

    return false
  }

  const requestTerminalCompletion=async(id,buffer,cursor,{preserveItems=false}={})=>{
    const projectRoot=terminalRootRef.current[id]||root||''
    if(!projectRoot) return

    const cwd=terminalCwdRef.current[id]||projectRoot
    const requestKey=`${id}:${Date.now()}:${Math.random().toString(16).slice(2)}`
    const current=terminalCompletionRef.current
    const canPreserve=preserveItems&&current?.sessionId===id

    if(canPreserve){
      setTerminalCompletionState({
        ...current,
        requestKey,
        loading:false,
        error:null,
        liveFiltering:true
      })
    }else{
      setTerminalCompletionState({
        sessionId:id,
        requestKey,
        loading:true,
        items:[],
        selectedIndex:0,
        replaceStart:cursor,
        replaceEnd:cursor,
        token:'',
        liveFiltering:false
      })
    }

    try{
      const result=await api('/terminal/completions',{
        method:'POST',
        body:JSON.stringify({root:projectRoot,cwd,buffer,cursor})
      })

      if(terminalCompletionRef.current?.requestKey!==requestKey) return

      const items=Array.isArray(result?.items)?result.items:[]
      setTerminalCompletionState({
        sessionId:id,
        requestKey,
        loading:false,
        items,
        selectedIndex:0,
        replaceStart:Number(result?.replace_start??cursor),
        replaceEnd:Number(result?.replace_end??cursor),
        token:String(result?.token||''),
        cwd:String(result?.cwd||cwd),
        liveFiltering:false
      })
    }catch(e){
      if(terminalCompletionRef.current?.requestKey!==requestKey) return
      setTerminalCompletionState({
        sessionId:id,
        requestKey,
        loading:false,
        items:canPreserve?(terminalCompletionRef.current?.items||[]):[],
        selectedIndex:0,
        replaceStart:cursor,
        replaceEnd:cursor,
        error:String(e),
        liveFiltering:false
      })
    }
  }

  const scheduleTerminalCompletionRefresh=(id,buffer,cursor)=>{
    const current=terminalCompletionRef.current
    if(current?.sessionId!==id) return
    clearTimeout(terminalCompletionTimerRef.current[id])
    terminalCompletionTimerRef.current[id]=setTimeout(()=>{
      delete terminalCompletionTimerRef.current[id]
      requestTerminalCompletion(id,buffer,cursor,{preserveItems:true})
    },85)
  }

  const scrollTerminalToBottom=(id,behavior='smooth')=>{
    requestAnimationFrame(()=>{
      const el=terminalOutputRefs.current[id]
      if(!el) return
      el.scrollTo({top:el.scrollHeight,behavior})
    })
  }


  const ensureXtermInstance=async(id)=>{
    const container=xtermContainersRef.current[id]
    if(!container) return null

    if(xtermInstancesRef.current[id]){
      const rect=container.getBoundingClientRect()

      if(
        screen==='WORKSPACE'
        && workspaceTab==='CODE'
        && rect.width>=120
        && rect.height>=80
      ){
        fitTerminalViewport(id)
      }

      return xtermInstancesRef.current[id]
    }

    const term=new XTerm({
      cursorBlink:true,
      cursorStyle:'block',
      cursorInactiveStyle:'outline',
      convertEol:true,
      scrollback:5000,
      fontFamily:'Consolas, "Cascadia Mono", monospace',
      fontSize:13,
      lineHeight:1.25,
      theme:{
        background:'#071009',
        foreground:'#d8e2ec',
        cursor:'#f2f5f8',
        selectionBackground:'#264d73',
        black:'#071009',
        brightBlack:'#66717c',
        green:'#57d978',
        brightGreen:'#82ec9e',
        yellow:'#e8c36a',
        brightYellow:'#f3dc91',
        blue:'#5f9eea',
        brightBlue:'#83b8f5',
        red:'#e06c75',
        brightRed:'#f08a91',
        cyan:'#56c7d9',
        brightCyan:'#79dceb',
        white:'#d8e2ec',
        brightWhite:'#ffffff'
      }
    })

    const fitAddon=new FitAddon()
    term.loadAddon(fitAddon)
    term.open(container)

    xtermInstancesRef.current[id]=term
    xtermFitAddonsRef.current[id]=fitAddon

    {
      const rect=container.getBoundingClientRect()

      if(
        screen==='WORKSPACE'
        && workspaceTab==='CODE'
        && rect.width>=120
        && rect.height>=80
      ){
        fitTerminalViewport(id)
      }
    }

    xtermCommandBuffersRef.current[id]=''
    xtermCommandHistoryRef.current[id]=
      xtermCommandHistoryRef.current[id]||[]
    xtermHistoryIndexRef.current[id]=
      xtermCommandHistoryRef.current[id].length
    xtermCursorIndexRef.current[id]=0

    const redrawCurrentLine=(value,cursorIndex)=>{
      const prompt=xtermPromptRef.current[id]||''
      fitTerminalViewport(id)
      term.write('\x1b[2K\r')

      // Keep pasted PowerShell blocks readable exactly as multi-line input.
      // The local command buffer uses LF, while xterm display uses CRLF so
      // every pasted line starts at column 0 just like VS Code Terminal.
      const displayValue=String(value||'').replace(/\r\n|\r|\n/g,'\r\n')
      term.write(prompt+displayValue)

      const tail=value.slice(cursorIndex)
      if(!/[\r\n]/.test(tail)){
        const moveLeft=terminalCellWidth(tail)
        if(moveLeft>0){
          term.write(`\x1b[${moveLeft}D`)
        }
      }
    }

    const setCommandLine=(value,cursorIndex=value.length)=>{
      xtermCommandBuffersRef.current[id]=value
      xtermCursorIndexRef.current[id]=Math.max(
        0,
        Math.min(cursorIndex,value.length)
      )
      redrawCurrentLine(
        xtermCommandBuffersRef.current[id],
        xtermCursorIndexRef.current[id]
      )
    }

    xtermSetCommandLineRef.current[id]=setCommandLine


    const clearKeyboardTerminalSelection=()=>{
      delete xtermKeyboardSelectionRef.current[id]
    }

    const extendKeyboardTerminalSelection=(direction)=>{
      const activeBuffer=term.buffer?.active
      if(!activeBuffer) return

      const maxLine=Math.max(0,activeBuffer.length-1)
      const currentLine=Math.max(
        0,
        Math.min(maxLine,(activeBuffer.baseY||0)+(activeBuffer.cursorY||0))
      )

      let state=xtermKeyboardSelectionRef.current[id]
      if(!state){
        state={anchor:currentLine,focus:currentLine}
      }

      const nextFocus=Math.max(
        0,
        Math.min(maxLine,state.focus+(direction<0?-1:1))
      )
      state={...state,focus:nextFocus}
      xtermKeyboardSelectionRef.current[id]=state

      const start=Math.min(state.anchor,state.focus)
      const end=Math.max(state.anchor,state.focus)
      term.selectLines(start,end)

      // Keep the newly extended edge visible while the user holds Shift and
      // presses Up/Down repeatedly. scrollLines only affects the viewport; it
      // does not alter PowerShell history or the local input buffer.
      if(direction<0){
        const viewportTop=activeBuffer.viewportY||0
        if(nextFocus<=viewportTop) term.scrollLines(-1)
      }else{
        const viewportTop=activeBuffer.viewportY||0
        const visibleRows=Math.max(1,term.rows||1)
        if(nextFocus>=viewportTop+visibleRows-1) term.scrollLines(1)
      }
    }

    term.attachCustomKeyEventHandler(event=>{
      // Only the terminal may consume keyboard input while it is the explicit
      // focus owner. Notebook/Monaco/LLM clicks can leave xterm's hidden
      // textarea mounted, and older builds could therefore keep receiving
      // Backspace after the user had moved back to the editor.
      if(event.type==='keydown'&&focusOwnerRef.current!=='terminal'){
        return false
      }

      if(
        event.type==='keydown'
        && event.shiftKey
        && !event.ctrlKey
        && !event.altKey
        && !event.metaKey
        && (event.code==='ArrowUp'||event.code==='ArrowDown')
      ){
        event.preventDefault?.()
        extendKeyboardTerminalSelection(event.code==='ArrowUp'?-1:1)
        return false
      }

      if(
        event.type==='keydown'
        && !event.shiftKey
        && (event.code==='ArrowUp'||event.code==='ArrowDown')
      ){
        clearKeyboardTerminalSelection()
        if(term.hasSelection()) term.clearSelection()
      }

      if(
        event.type==='keydown'
        && event.ctrlKey
        && !event.altKey
        && !event.metaKey
      ){
        // VS Code compatible copy semantics:
        // selected terminal text -> clipboard, otherwise Ctrl+C is passed
        // through to xterm/onData where it remains the PowerShell interrupt.
        if(event.code==='KeyC'&&term.hasSelection()){
          const selected=term.getSelection()
          if(selected){
            navigator.clipboard?.writeText?.(selected).catch(err=>
              console.warn('[Terminal] clipboard copy failed',err)
            )
          }
          return false
        }

        // Ctrl+V is handled only by the browser/xterm native paste event.
        // Do not read navigator.clipboard here: doing both would emit the
        // clipboard text twice. Returning false skips xterm key processing
        // while leaving the browser paste event as the single input source.
        if(event.code==='KeyV'){
          return false
        }

        if(event.code==='Space'){
          requestTerminalCompletion(
            id,
            xtermCommandBuffersRef.current[id]||'',
            xtermCursorIndexRef.current[id]??0
          )
          return false
        }
      }
      return true
    })

    const eraseTerminalCellsBackward=(count)=>{
      const cells=Math.max(0,Number(count)||0)
      if(!cells) return

      const activeBuffer=term.buffer?.active
      const cols=Math.max(1,Number(term.cols)||1)
      let cursorX=Math.max(0,Number(activeBuffer?.cursorX)||0)
      let sequence=''

      // Backspace (\b) does not reliably cross a soft-wrapped xterm row.
      // Move explicitly across the row boundary and erase in-place so a long
      // PowerShell command is shortened instead of being redrawn repeatedly.
      for(let index=0;index<cells;index++){
        if(cursorX>0){
          sequence+='\x1b[D\x1b[X'
          cursorX-=1
        }else{
          sequence+=`\x1b[A\x1b[${cols}G\x1b[X`
          cursorX=cols-1
        }
      }

      if(sequence) term.write(sequence)
    }

    const disposable=term.onData(data=>{
      // Defensive input gate matching attachCustomKeyEventHandler above.
      // Program output uses term.write() and is unaffected by this guard.
      if(focusOwnerRef.current!=='terminal') return

      const currentSession=terminalSessions.find(t=>t.id===id)
      if(currentSession?.processState==='exited') return

      const ws=terminalSocketsRef.current[id]
      if(!ws||ws.readyState!==WebSocket.OPEN) return

      // Any normal terminal input starts a new editing action, so keyboard
      // selection mode ends. Ctrl+C with a selection is intercepted above and
      // therefore still copies before this path is reached.
      if(data!=='\x00'){
        clearKeyboardTerminalSelection()
        if(term.hasSelection()) term.clearSelection()
      }

      let buffer=xtermCommandBuffersRef.current[id]||''
      let cursor=xtermCursorIndexRef.current[id]??buffer.length

      // Ctrl+Space (NUL) opens the AgentStudio terminal completion menu.
      if(data==='\x00'){
        requestTerminalCompletion(id,buffer,cursor)
        return
      }

      // xterm native paste arrives through onData as one payload. Keep it
      // as the single source of truth so Ctrl+V is inserted exactly once.
      // Preserve multi-line PowerShell blocks in the local command buffer;
      // pasting never executes the command until the user presses Enter.
      if(data.length>1&&/[\r\n]/.test(data)){
        const pasted=String(data).replace(/\r\n|\r/g,'\n')
        buffer=buffer.slice(0,cursor)+pasted+buffer.slice(cursor)
        cursor+=pasted.length
        xtermCommandBuffersRef.current[id]=buffer
        xtermCursorIndexRef.current[id]=cursor
        closeTerminalCompletion(id)
        setCommandLine(buffer,cursor)
        return
      }

      // A single-line paste can also arrive as one multi-character onData
      // payload. It is handled by the normal printable-text path below once.

      const activeCompletion=terminalCompletionRef.current
      if(activeCompletion?.sessionId===id){
        if(data==='\x1b[A'){
          moveTerminalCompletionSelection(-1)
          return
        }
        if(data==='\x1b[B'){
          moveTerminalCompletionSelection(1)
          return
        }
        if(data==='\t'||data==='\r'){
          if(activeCompletion.items?.length){
            applyTerminalCompletion()
            return
          }
          closeTerminalCompletion(id)
        }else if(data==='\x1b'){
          closeTerminalCompletion(id)
          return
        }
        // Keep the popup open for normal typing/backspace/delete/cursor moves.
        // The candidate list is refreshed from the current buffer below.
      }else if(data==='\t'){
        requestTerminalCompletion(id,buffer,cursor)
        return
      }

      // Enter
      if(data==='\r'){
        // Move cursor visually to line end before newline.
        const right=terminalCellWidth(buffer.slice(cursor))
        if(right>0){
          term.write(`\x1b[${right}C`)
        }
        term.write('\r\n',()=>revealTerminalBottom(id))

        const command=buffer
        xtermCommandBuffersRef.current[id]=''
        xtermCursorIndexRef.current[id]=0

        if(command.trim()){
          const history=xtermCommandHistoryRef.current[id]||[]
          history.push(command)
          xtermCommandHistoryRef.current[id]=history
          xtermHistoryIndexRef.current[id]=history.length
        }

        terminalCommandBusyRef.current[id]=!!command.trim()
        setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,busy:!!command.trim(),interrupting:false}:t))
        ws.send(serializeTerminalClientMessage({
          type:'command',
          data:command
        }))

        term.scrollToBottom()
        return
      }

      // Ctrl+C
      if(data==='\x03'){
        closeTerminalCompletion(id)
        const commandRunning=!!terminalCommandBusyRef.current[id]
        const hadLocalInput=!!buffer
        xtermCommandBuffersRef.current[id]=''
        xtermCursorIndexRef.current[id]=0

        // VS Code/PowerShell style: when no command is running, Ctrl+C only
        // cancels the current local input line. Do not signal the idle
        // PowerShell process, which can otherwise enter debugger mode.
        if(!commandRunning){
          const prompt=xtermPromptRef.current[id]||''
          term.write('^C\r\n'+prompt)
          return
        }

        term.write('^C\r\n')
        interruptTerminal(id)
        return
      }

      // Backspace
      if(data==='\x7f'){
        if(cursor>0){
          const atEnd=cursor===buffer.length
          const previous=terminalPreviousCharacter(buffer,cursor)
          const removed=previous.text
          buffer=buffer.slice(0,previous.start)+buffer.slice(cursor)
          cursor=previous.start

          if(atEnd){
            xtermCommandBuffersRef.current[id]=buffer
            xtermCursorIndexRef.current[id]=cursor

            // One Hangul/CJK character occupies two terminal cells. Erase by
            // display-cell width rather than JavaScript string length so
            // repeated Backspace always reaches the prompt without leaving
            // half-width remnants on screen.
            const eraseCells=Math.max(1,terminalCellWidth(removed))
            eraseTerminalCellsBackward(eraseCells)
            fitTerminalViewport(id)
          }else{
            setCommandLine(buffer,cursor)
          }
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Delete
      if(data==='\x1b[3~'){
        if(cursor<buffer.length){
          const next=terminalNextCharacter(buffer,cursor)
          buffer=buffer.slice(0,cursor)+buffer.slice(next.end)
          setCommandLine(buffer,cursor)
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Left
      if(data==='\x1b[D'){
        if(cursor>0){
          const previous=terminalPreviousCharacter(buffer,cursor)
          cursor=previous.start
          xtermCursorIndexRef.current[id]=cursor
          const move=Math.max(1,terminalCellWidth(previous.text))
          term.write(`\x1b[${move}D`)
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Right
      if(data==='\x1b[C'){
        if(cursor<buffer.length){
          const next=terminalNextCharacter(buffer,cursor)
          cursor=next.end
          xtermCursorIndexRef.current[id]=cursor
          const move=Math.max(1,terminalCellWidth(next.text))
          term.write(`\x1b[${move}C`)
          scheduleTerminalCompletionRefresh(id,buffer,cursor)
        }
        return
      }

      // Home
      if(data==='\x1b[H'||data==='\x1b[1~'){
        setCommandLine(buffer,0)
        scheduleTerminalCompletionRefresh(id,buffer,0)
        return
      }

      // End
      if(data==='\x1b[F'||data==='\x1b[4~'){
        setCommandLine(buffer,buffer.length)
        scheduleTerminalCompletionRefresh(id,buffer,buffer.length)
        return
      }

      // Up history
      if(data==='\x1b[A'){
        const history=xtermCommandHistoryRef.current[id]||[]
        if(!history.length) return

        let index=xtermHistoryIndexRef.current[id]
        index=Math.max(0,(index??history.length)-1)
        xtermHistoryIndexRef.current[id]=index

        const value=history[index]||''
        setCommandLine(value,value.length)
        return
      }

      // Down history
      if(data==='\x1b[B'){
        const history=xtermCommandHistoryRef.current[id]||[]
        if(!history.length) return

        let index=xtermHistoryIndexRef.current[id]
        index=Math.min(
          history.length,
          (index??history.length)+1
        )
        xtermHistoryIndexRef.current[id]=index

        const value=index<history.length
          ? history[index]
          : ''

        setCommandLine(value,value.length)
        return
      }

      // Ignore unsupported control sequences.
      if(data.startsWith('\x1b')||data<' '){
        return
      }

      // Insert printable text at current cursor position.
      const insertAtEnd=cursor===buffer.length
      buffer=
        buffer.slice(0,cursor)
        +data
        +buffer.slice(cursor)

      cursor+=data.length
      xtermCommandBuffersRef.current[id]=buffer
      xtermCursorIndexRef.current[id]=cursor

      if(insertAtEnd){
        // 화면 폭을 넘는 입력은 xterm의 기본 동작으로 다음 줄에 자동 줄바꿈합니다.
        fitTerminalViewport(id)
        term.write(data)
      }else{
        // Mid-line editing is rare; keep the existing redraw path for it.
        setCommandLine(buffer,cursor)
      }

      scheduleTerminalCompletionRefresh(id,buffer,cursor)
    })

    xtermDisposablesRef.current[id]=disposable

    if(canAutoFocusTerminal()){
      term.focus()
    }
    return term
  }

  const revealTerminalBottom=(id)=>{
    const term=xtermInstancesRef.current[id]
    if(!term) return

    const reveal=()=>{
      try{
        term.scrollToBottom()
        term.refresh(0,Math.max(0,term.rows-1))
      }catch{}
    }

    reveal()
    requestAnimationFrame(reveal)
    setTimeout(reveal,25)
  }

  const writeXterm=(id,text,{keepRight=false}={})=>{
    const term=xtermInstancesRef.current[id]
    if(!term||!text) return
    fitTerminalViewport(id)
    // xterm.write는 buffer 반영이 비동기일 수 있으므로 write 완료 뒤에
    // scrollToBottom을 수행해야 마지막 prompt/caret까지 실제로 보입니다.
    term.write(text,()=>revealTerminalBottom(id))
  }

  const focusXterm=(id,{force=false}={})=>{
    requestAnimationFrame(()=>{
      if(!force&&!canAutoFocusTerminal()) return
      const term=xtermInstancesRef.current[id]
      fitTerminalViewport(id)
      term?.focus()
    })
  }


  const clearTerminalView=(id)=>{
    if(!id) return

    const term=xtermInstancesRef.current[id]
    const prompt=xtermPromptRef.current[id]||''
    const buffer=xtermCommandBuffersRef.current[id]||''
    const busy=!!terminalCommandBusyRef.current[id]

    // Clear any partially parsed old output so it cannot reappear after Clear.
    xtermOutputParseBufferRef.current[id]=''

    try{
      if(term){
        term.write('\x1b[2J\x1b[3J\x1b[H',()=>{
          if(!busy){
            term.write(prompt+buffer,()=>{
              try{
                term.scrollToBottom()
                term.refresh(0,Math.max(0,term.rows-1))
              }catch{}
            })
          }else{
            try{
              term.scrollToBottom()
              term.refresh(0,Math.max(0,term.rows-1))
            }catch{}
          }
        })
      }
    }catch{}

    setTerminalSessions(prev=>prev.map(t=>
      t.id===id
        ? {...t,output:''}
        : t
    ))

    // Also clear Backend replay history so reconnecting does not restore
    // output that the user explicitly cleared. The shell process is kept alive.
    const ws=terminalSocketsRef.current[id]
    try{
      if(ws?.readyState===WebSocket.OPEN){
        ws.send(serializeTerminalClientMessage({type:'clear'}))
      }
    }catch{}

    setTimeout(()=>{
      fitTerminalViewport(id)
      if(canAutoFocusTerminal()){
        try{ xtermInstancesRef.current[id]?.focus() }catch{}
      }
    },0)
  }

  const restartTerminalSession=async(id)=>{
    const old=terminalSessions.find(t=>t.id===id)
    if(!old?.root) return

    // 기존 세션을 재시작하기 위해 닫는 것은 정상 동작입니다.
    terminalIntentionalCloseRef.current[id]=true

    setTerminalErrors(prev=>({
      ...prev,
      [id]:null
    }))

    const ws=terminalSocketsRef.current[id]
    try{ ws?.close() }catch{}
    delete terminalSocketsRef.current[id]

    try{
      xtermInstancesRef.current[id]?.clear()
      xtermInstancesRef.current[id]?.reset()
    }catch{}

    xtermCommandBuffersRef.current[id]=''
    xtermCursorIndexRef.current[id]=0
    terminalCommandBusyRef.current[id]=false
    xtermPromptRef.current[id]=''
    xtermOutputParseBufferRef.current[id]=''
    xtermRequiredColsRef.current[id]=0

    setTerminalSessions(prev=>prev.map(t=>
      t.id===id
        ? {
            ...t,
            processState:'starting',
            exitCode:null,
            command:'',
            output:''
          }
        : t
    ))

    terminalIntentionalCloseRef.current[id]=false

    await connectProjectTerminal(
      {
        id:old.projectId,
        name:old.projectName,
        project_root:old.root
      },
      id
    )

    setTimeout(async()=>{
      await ensureXtermInstance(id)
      if(canAutoFocusTerminal()){
        focusXterm(id)
      }
    },100)
  }


  // v5.145 terminal layout restore:
  // CODE 탭이 실제로 보일 때만 xterm fit을 수행합니다.
  // 숨겨진 상태에서 fit하면 0/1px 크기를 열/행으로 계산해 화면이 깨질 수 있습니다.
  useEffect(()=>{
    if(
      !activeTerminalId
      || screen!=='WORKSPACE'
      || workspaceTab!=='CODE'
      || isSqlFile
    ) return

    const restore=()=>{
      const term=xtermInstancesRef.current[activeTerminalId]
      const current=terminalSessions.find(
        t=>t.id===activeTerminalId
      )

      fitTerminalViewport(activeTerminalId)
      try{
        if(term){
          term.refresh(0,Math.max(0,term.rows-1))
          term.scrollToBottom()
        }
      }catch{}

      if(
        current?.processState!=='exited'
        && canAutoFocusTerminal()
      ){
        try{ term?.focus() }catch{}
      }
    }

    const a=setTimeout(restore,20)
    const b=setTimeout(restore,120)
    const c=setTimeout(restore,300)

    return()=>{
      clearTimeout(a)
      clearTimeout(b)
      clearTimeout(c)
    }
  },[activeTerminalId,terminalSessions.length,screen,workspaceTab,isSqlFile,selected])



  useEffect(()=>{
    const closeEditorTabContextMenu=()=>{
      setEditorTabMenu(null)
      setEditorFilesMenu(null)
    }

    const closeEditorTabContextMenuByKey=(e)=>{
      if(e.key==='Escape'){
        setEditorTabMenu(null)
        setEditorFilesMenu(null)
      }
    }

    window.addEventListener(
      'mousedown',
      closeEditorTabContextMenu
    )

    window.addEventListener(
      'keydown',
      closeEditorTabContextMenuByKey
    )

    return()=>{
      window.removeEventListener(
        'mousedown',
        closeEditorTabContextMenu
      )

      window.removeEventListener(
        'keydown',
        closeEditorTabContextMenuByKey
      )
    }
  },[])


  async function loadFiles(rootOverride=null){
    const targetRoot=rootOverride||root

    if(!targetRoot){
      setFiles([])
      setProjectDirs([])
      return {files:[],dirs:[]}
    }

    try{
      const [fileRows,dirRows]=await Promise.all([
        api(`/files?root=${encodeURIComponent(targetRoot)}`),
        api(`/folders?root=${encodeURIComponent(targetRoot)}`)
      ])

      // Keep every project path in one canonical form inside the UI.
      // Windows Backend responses may contain `\\` while tree node paths use `/`.
      // Comparing those raw strings made a selected nested folder look unknown and
      // caused new files to fall back to the project root.
      const nextFiles=(Array.isArray(fileRows)?fileRows:(fileRows?.files||[]))
        .map(normalizeProjectRelativePath)
        .filter(Boolean)
      const nextDirs=(Array.isArray(dirRows)?dirRows:(dirRows?.folders||[]))
        .map(normalizeProjectRelativePath)
        .filter(Boolean)

      setFiles(nextFiles)
      setProjectDirs(nextDirs)

      return {files:nextFiles,dirs:nextDirs}
    }catch(e){
      console.error('프로젝트 파일/폴더 목록 로드 실패',e)
      setFiles([])
      setProjectDirs([])
      throw e
    }
  }

  const addExternalFileNotification=(path,status)=>{
    const normalized=normalizeProjectRelativePath(path)
    if(!normalized) return
    setExternalFileNotifications(prev=>{
      const filtered=prev.filter(item=>item.path!==normalized)
      return [{
        id:`${Date.now()}-${normalized}`,
        path:normalized,
        status,
        time:new Date().toISOString()
      },...filtered].slice(0,50)
    })
    // External changes must be visible immediately instead of only changing
    // the bell badge. The user can close the menu after reviewing it.
    setExternalNotificationOpen(true)
  }

  const reloadExternalEditorFile=async(editorPath,{activate=false}={})=>{
    const normalized=normalizeProjectRelativePath(editorPath)

    if(isBinaryPreviewFile(editorPath)){
      let latest={exists:true,mtime_ns:0,size:0}
      try{
        latest=await api(`/files/meta?root=${encodeURIComponent(activeWorkspaceRoot)}&relative_path=${encodeURIComponent(editorPath)}`)
      }catch(_){ }
      const latestMeta={
        mtime_ns:latest.mtime_ns||Date.now(),
        size:latest.size||0,
        sha256:latest.sha256||''
      }
      editorFileDiskMetaRef.current={
        ...editorFileDiskMetaRef.current,
        [normalized]:latestMeta
      }
      setEditorFileDiskMeta(prev=>({...prev,[normalized]:latestMeta}))
      setEditorFileDirty(prev=>({...prev,[editorPath]:false}))
      setEditorExternalState(prev=>{
        const copy={...prev}; delete copy[normalized]; return copy
      })
      if(isPdfFile(editorPath)){
        setPdfPreviewRevision(prev=>({...prev,[normalized]:Date.now()}))
      }else{
        setPresentationPreviewRevision(prev=>({...prev,[normalized]:Date.now()}))
      }
      if(activate||selectedEditorFileRef.current===editorPath){
        setSelected(editorPath)
        setFileTreeSelected(editorPath)
        setFileTreeSelectedPaths([editorPath])
        setCode('')
        setFileSaveStatus(isPdfFile(editorPath)?'PDF 미리보기 새로고침':'PowerPoint 미리보기 새로고침')
      }
      return latest
    }

    const latest=await api('/files/read',{
      method:'POST',
      body:JSON.stringify({root:activeWorkspaceRoot,relative_path:editorPath})
    })
    const latestContent=latest.content??''
    setEditorFileContents(prev=>({...prev,[editorPath]:latestContent}))
    setEditorFileDirty(prev=>({...prev,[editorPath]:false}))
    const latestMeta={
      mtime_ns:latest.mtime_ns||0,
      size:latest.size||0,
      sha256:latest.sha256||''
    }
    editorFileDiskMetaRef.current={
      ...editorFileDiskMetaRef.current,
      [normalized]:latestMeta
    }
    setEditorFileDiskMeta(prev=>({
      ...prev,
      [normalized]:latestMeta
    }))
    setEditorExternalState(prev=>{
      const copy={...prev}; delete copy[normalized]; return copy
    })
    if(activate||selectedEditorFileRef.current===editorPath){
      setSelected(editorPath)
      setFileTreeSelected(editorPath)
      setFileTreeSelectedPaths([editorPath])
      setCode(latestContent)
      setFileSaveStatus('외부 파일 로드 완료')
    }
    return latest
  }

  const openExternalChangePrompt=(editorPath,{mode='external_notice',pendingContent=null}={})=>{
    const normalized=normalizeProjectRelativePath(editorPath)
    setExternalChangeConfirm({
      path:editorPath,
      normalized,
      mode,
      pendingContent,
      loading:false,
      loadingAction:'',
      error:''
    })
  }

  const handleExternalChangeDecision=async(action)=>{
    const pending=externalChangeConfirm
    if(!pending||pending.loading) return

    if(action==='cancel'){
      setExternalChangeConfirm(null)
      return
    }

    setExternalChangeConfirm(prev=>prev?{
      ...prev,
      loading:true,
      loadingAction:action,
      error:''
    }:prev)

    try{
      if(action==='load_external'){
        await reloadExternalEditorFile(pending.path,{activate:true})
        setExternalFileNotifications(prev=>prev.filter(item=>item.path!==pending.normalized))
        setExternalChangeConfirm(null)
        return
      }

      if(action==='force_save'){
        const currentContent=
          pending.pendingContent
          ?? editorFileContents[pending.path]
          ?? (selectedEditorFileRef.current===pending.path?code:'')
          ?? ''

        const result=await writeEditorFile(
          pending.path,
          currentContent,
          {force:true,promptOnConflict:false}
        )

        setTerminal(prev=>
          (prev||'')
          + `\n[외부 변경 무시 저장 완료] ${result?.path||result?.fullPath||pending.path}`
          + (result?.bytes!=null?` (${result.bytes} bytes)`:'')
          + '\n'
        )
        setFileSaveStatus('저장 완료')
        setExternalFileNotifications(prev=>prev.filter(item=>item.path!==pending.normalized))
        setExternalChangeConfirm(null)
        return
      }

      setExternalChangeConfirm(null)
    }catch(e){
      setFileSaveStatus('저장 실패')
      setExternalChangeConfirm(prev=>prev?{
        ...prev,
        loading:false,
        loadingAction:'',
        error:String(e)
      }:prev)
    }
  }

  const handleExternalNotificationClick=(item)=>{
    if(!item?.path) return
    setExternalNotificationOpen(false)
    const normalized=normalizeProjectRelativePath(item.path)
    const editorPath=(openEditorFilesRef.current||[]).find(
      path=>normalizeProjectRelativePath(path)===normalized
    )||item.path
    if(openEditorFilesRef.current?.includes(editorPath)){
      activateEditorFile(editorPath)
    }
    if(item.status==='modified_conflict'){
      openExternalChangePrompt(editorPath)
      return
    }
    setExternalFileNotifications(prev=>prev.filter(row=>row.id!==item.id))
  }

  const handleExternalNotificationIgnore=(item)=>{
    if(!item?.path) return
    const normalized=normalizeProjectRelativePath(item.path)

    // Ignore means: keep the current AgentStudio editor buffer and dismiss
    // this notification. Do NOT advance the disk baseline, because the
    // external file is still different. A later save will therefore use the
    // v5.207 save-conflict dialog and let the user explicitly choose whether
    // to load external content or force-save the AgentStudio content.
    if(item.status==='modified_conflict'){
      setEditorExternalState(prev=>({
        ...prev,
        [normalized]:'modified_ignored'
      }))
      if(selectedEditorFileRef.current&&
        normalizeProjectRelativePath(selectedEditorFileRef.current)===normalized){
        setFileSaveStatus('외부 변경 무시')
      }
    }

    setExternalFileNotifications(prev=>prev.filter(row=>row.id!==item.id))
  }

  // v5.203: detect files created/modified/deleted outside AgentStudio.
  // Polling keeps the implementation dependency-free and works for local Windows projects.
  useEffect(()=>{
    projectFileSnapshotRef.current=null
    fileWatchBusyRef.current=false

    if(!root||screen!=='WORKSPACE') return

    let cancelled=false

    const pollProjectFiles=async()=>{
      if(cancelled||fileWatchBusyRef.current) return
      fileWatchBusyRef.current=true

      try{
        const next=await api(`/files/snapshot?root=${encodeURIComponent(root)}`)
        if(cancelled) return

        const previous=projectFileSnapshotRef.current
        projectFileSnapshotRef.current=next

        if(!previous?.files){
          // The first watcher snapshot is authoritative as well. Reconcile
          // the visible tree immediately so stale in-memory/ghost entries
          // cannot survive a project reopen.
          try{ await loadFiles(root) }catch(_){ }
          return
        }

        const previousFiles=previous.files||{}
        const nextFiles=next.files||{}
        const previousKeys=new Set(Object.keys(previousFiles))
        const nextKeys=new Set(Object.keys(nextFiles))

        const added=[...nextKeys].filter(path=>!previousKeys.has(path))
        const deleted=[...previousKeys].filter(path=>!nextKeys.has(path))
        const metadataModified=[...nextKeys].filter(path=>{
          if(!previousKeys.has(path)) return false
          const before=previousFiles[path]||{}
          const after=nextFiles[path]||{}
          return before.mtime_ns!==after.mtime_ns||before.size!==after.size
        })

        if(added.length||deleted.length){
          try{ await loadFiles(root) }catch(_){ }
        }

        const openMap=new Map(
          (openEditorFilesRef.current||[]).map(path=>[normalizeProjectRelativePath(path),path])
        )

        // v5.256: the authoritative external-change signal for opened files is
        // SHA-256, not mtime/size. mtime/size remain useful only for the cheap
        // project-tree snapshot and as a fallback if hash polling fails.
        let hashStateFiles={}
        let hashPollingOk=false
        if(openMap.size){
          try{
            const hashState=await api('/files/hash-state',{
              method:'POST',
              body:JSON.stringify({
                root:activeWorkspaceRoot||root,
                relative_paths:[...openMap.keys()]
              })
            })
            hashStateFiles=hashState?.files||{}
            hashPollingOk=true
          }catch(e){
            console.warn('열린 파일 SHA-256 상태 조회 실패, 메타데이터 감지로 대체합니다.',e)
          }
        }

        const modifiedOpenKeys=new Set()
        const metadataModifiedSet=new Set(metadataModified)

        for(const [key] of openMap){
          const latest=hashStateFiles[key]
          const baseline=editorFileDiskMetaRef.current?.[key]

          if(hashPollingOk&&latest){
            if(!latest.exists) continue

            const latestSha=String(latest.sha256||'')
            const baselineSha=String(baseline?.sha256||'')

            if(baselineSha&&latestSha){
              if(latestSha!==baselineSha){
                modifiedOpenKeys.add(key)
              }else if(
                baseline?.mtime_ns!==latest.mtime_ns
                || baseline?.size!==latest.size
              ){
                // Metadata changed but bytes are identical. Advance only the
                // disk baseline and do not emit a false external-change alert.
                const refreshed={
                  mtime_ns:latest.mtime_ns||0,
                  size:latest.size||0,
                  sha256:latestSha
                }
                editorFileDiskMetaRef.current={
                  ...editorFileDiskMetaRef.current,
                  [key]:refreshed
                }
                setEditorFileDiskMeta(prev=>({...prev,[key]:refreshed}))
              }
              continue
            }

            if(latestSha){
              // Older sessions/PDFs may not yet have a hash baseline. Record it
              // once; all subsequent comparisons are hash-authoritative.
              const initialized={
                mtime_ns:latest.mtime_ns||baseline?.mtime_ns||0,
                size:latest.size||baseline?.size||0,
                sha256:latestSha
              }
              editorFileDiskMetaRef.current={
                ...editorFileDiskMetaRef.current,
                [key]:initialized
              }
              setEditorFileDiskMeta(prev=>({...prev,[key]:initialized}))
              continue
            }
          }

          // Compatibility fallback only when the hash service is unavailable.
          if(metadataModifiedSet.has(key)) modifiedOpenKeys.add(key)
        }

        for(const key of deleted){
          const editorPath=openMap.get(key)
          if(!editorPath) continue
          setEditorExternalState(prev=>({...prev,[key]:'deleted'}))
          if(selectedEditorFileRef.current===editorPath){
            setFileSaveStatus('외부 삭제 감지')
          }
          addExternalFileNotification(editorPath,'deleted')
        }

        for(const key of modifiedOpenKeys){
          const editorPath=openMap.get(key)
          if(!editorPath) continue
          const isCurrent=selectedEditorFileRef.current===editorPath
          const isDirty=!!editorFileDirtyRef.current?.[editorPath]

          if(isDirty){
            setEditorExternalState(prev=>({...prev,[key]:'modified_conflict'}))
            if(isCurrent){
              setFileSaveStatus('외부 변경 충돌')
              openExternalChangePrompt(editorPath)
            }
            addExternalFileNotification(editorPath,'modified_conflict')
            continue
          }

          try{
            await reloadExternalEditorFile(editorPath,{activate:isCurrent})
            if(cancelled) return
            if(isCurrent) setFileSaveStatus('외부 변경 자동 반영')
            // Current file is no longer special-cased: every externally changed
            // opened file creates a visible alarm entry.
            addExternalFileNotification(editorPath,'modified_reloaded')
          }catch(e){
            console.error('외부 변경 파일 다시 읽기 실패',editorPath,e)
          }
        }
      }catch(e){
        console.error('프로젝트 파일 변경 감지 실패',e)
      }finally{
        fileWatchBusyRef.current=false
      }
    }

    pollProjectFiles()
    const timer=setInterval(pollProjectFiles,1500)

    return()=>{
      cancelled=true
      clearInterval(timer)
      fileWatchBusyRef.current=false
    }
  },[root,screen])

  const createNewAgentProject=async()=>{
    if(!newAgentName.trim()){
      setNewAgentCreateResult({ok:false,message:'에이전트 이름을 입력하세요.'})
      return
    }
    if(!newAgentProjectRoot.trim()){
      setNewAgentCreateResult({ok:false,message:'프로젝트 경로를 입력하세요.'})
      return
    }
    try{
      const r=await api('/projects/create-agent',{
        method:'POST',
        body:JSON.stringify({
          name:newAgentName,
          project_root:newAgentProjectRoot,
          cache_path:newAgentCachePath,
          temp_path:newAgentTempPath,
          output_path:newAgentOutputPath,
          venv_path:newAgentVenvPath,
          models_path:newAgentModelsPath
        })
      })
      setNewAgentCreateResult(r)
      if(r.ok){
        setSelectedProjectId(r.project_id||null)
        setRoot(r.project_root||newAgentProjectRoot)
        setProjectLoadMessage(`프로젝트 #${r.project_id||''} ${r.name||newAgentName} 생성 완료`)
        setScreen('WORKSPACE')
        setTimeout(()=>loadFiles(),100)
      }
    }catch(e){
      setNewAgentCreateResult({ok:false,message:String(e)})
    }
  }


  const openProjectList=async()=>{
    setProjectListOpen(true)
    setProjectListLoading(true)
    setProjectLoadMessage('')
    try{
      const rows=await api('/projects')
      setProjectList(Array.isArray(rows)?rows:[])
    }catch(e){
      setProjectList([])
      setProjectLoadMessage('프로젝트 목록 조회 실패: '+String(e))
    }finally{
      setProjectListLoading(false)
    }
  }

  const loadProject=async(projectId)=>{
    setProjectLoadMessage('프로젝트를 불러오는 중...')
    setProjectLoadProgress({
      active:true,
      percent:5,
      message:'프로젝트 정보를 불러오는 중...',
      failed:false
    })

    try{
      const p=await api(`/projects/${projectId}`)

      if(!p.ok){
        const msg=p.message||'프로젝트를 불러오지 못했습니다.'
        setProjectLoadMessage(msg)
        setProjectLoadProgress({
          active:true,
          percent:100,
          message:msg,
          failed:true
        })
        return
      }

      setProjectLoadProgress({
        active:true,
        percent:20,
        message:'프로젝트 경로를 적용하는 중...',
        failed:false
      })

      const projectRoot=p.project_root||root||''

      setSelectedProjectId(p.id)
      setNewAgentName(p.name||'')
      setNewAgentProjectRoot(projectRoot)
      setNewAgentCachePath(p.cache_path||'')
      setNewAgentTempPath(p.temp_path||'')
      setNewAgentOutputPath(p.output_path||'')
      setNewAgentVenvPath(p.venv_path||'')
      setNewAgentModelsPath(p.models_path||'')
      setLoadedProjectAnalysis(p.analysis||null)
      setRoot(projectRoot)

      setProjectLoadProgress({
        active:true,
        percent:40,
        message:'프로젝트 파일과 폴더를 불러오는 중...',
        failed:false
      })

      // setRoot()의 비동기 state 반영을 기다리지 않고
      // API에서 받은 projectRoot를 직접 사용한다.
      await loadFiles(projectRoot)
      await activateProjectTerminal(p)
      await loadGitInfo(projectRoot)

      setProjectLoadProgress({
        active:true,
        percent:70,
        message:'프로젝트 상태를 갱신하는 중...',
        failed:false
      })

      setNewAgentCreateResult({
        ok:true,
        message:'프로젝트를 불러왔습니다.',
        project_id:p.id,
        project_root:projectRoot,
        cache_path:p.cache_path,
        temp_path:p.temp_path,
        output_path:p.output_path,
        venv_path:p.venv_path,
        models_path:p.models_path
      })

      await refreshProjectList()

      setProjectLoadProgress({
        active:true,
        percent:90,
        message:'작업공간을 준비하는 중...',
        failed:false
      })

      setProjectLoadMessage(`프로젝트 #${p.id} ${p.name} 불러오기 완료`)
      setProjectListOpen(false)
      setWorkspaceTab('CODE')
      setScreen('WORKSPACE')

      setProjectLoadProgress({
        active:true,
        percent:100,
        message:'프로젝트 로딩 완료',
        failed:false
      })

      setTimeout(()=>{
        setProjectLoadProgress({
          active:false,
          percent:0,
          message:'',
          failed:false
        })
      },800)
    }catch(e){
      const msg='프로젝트 불러오기 실패: '+String(e)
      setProjectLoadMessage(msg)
      setProjectLoadProgress({
        active:true,
        percent:100,
        message:msg,
        failed:true
      })
      setTimeout(()=>{
        setProjectLoadProgress(prev=>({...prev,active:false}))
      },3000)
    }
  }


  const startNewProject=()=>{
    setAgentBuildMessage('')
    setWorkspaceTab('DESIGN')
    setScreen('WORKSPACE')
    setInput('')
    setNewAgentCreateResult(null)
    setSelectedProjectId(null)
    setGitInfo(null)

    // '신규 Agent 만들기'는 기존 프로젝트/설계에서 사용하던 경로를 이어받지 않습니다.
    // 프로젝트 경로 input은 항상 빈 value로 시작하고 사용자가 직접 입력하거나 선택합니다.
    setNewAgentProjectRoot('')
    setRoot('')

    // 경로를 새로 선택한 뒤 동일 경로의 Draft가 존재하면 newAgentProjectRoot useEffect에서 복원합니다.
    // 버튼 클릭 직후에는 이전 경로의 Draft를 복원하지 않고 새 인터뷰를 시작합니다.
    setAgentBuildStage('REQUIREMENTS')
    setTargetWorkflowPreview(null)
    setTargetWorkflowQuality(null)
    setBuilderStarted(false)
    setChat([{
      role:'assistant',
      content:'어떤 AI Agent + MCP 프로그램을 만들고 싶으신가요? 먼저 프로그램의 목적을 한 문장으로 말씀해 주세요.'
    }])

    loadDefaultPaths()
  }

  useEffect(()=>{ openEditorFilesRef.current=openEditorFiles },[openEditorFiles])
  useEffect(()=>{ editorFileDirtyRef.current=editorFileDirty },[editorFileDirty])
  useEffect(()=>{ editorFileDiskMetaRef.current=editorFileDiskMeta },[editorFileDiskMeta])
  useEffect(()=>{ selectedEditorFileRef.current=selected },[selected])

  useEffect(()=>{
    setFileTreeSelectedPaths([])
    fileTreeSelectionAnchorRef.current=''
    setFileTreeContextMenu(null)
    setExternalNotificationOpen(false)
    setExternalFileNotifications([])
  },[root])

  const writeEditorFile=async(relativePath,content,{force=false,promptOnConflict=true}={})=>{
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot || !relativePath){
      throw new Error('프로젝트와 파일을 먼저 선택하세요.')
    }

    const normalizedRoot=String(workspaceRoot).replace(/[\\/]+$/,'')
    const normalizedSelected=String(relativePath).replace(/^[\\/]+/,'')
    const fullPath=`${normalizedRoot}\\${normalizedSelected.replace(/\//g,'\\')}`

    const metaKey=normalizeProjectRelativePath(relativePath)
    const baseline=editorFileDiskMetaRef.current?.[metaKey]
    if(editorExternalState[metaKey]==='deleted'){
      throw new Error('파일이 AgentStudio 밖에서 삭제되었습니다. 프로젝트 트리를 확인한 뒤 새 파일로 다시 생성하거나 탭을 닫아주세요.')
    }

    let result
    try{
      result=await api('/file/write',{
        method:'POST',
        body:JSON.stringify({
          path:fullPath,
          content:content??'',
          expected_mtime_ns:baseline?.mtime_ns||null,
          expected_sha256:baseline?.sha256||null,
          force:!!force
        })
      })
    }catch(e){
      if(e?.status===409){
        setEditorExternalState(prev=>({...prev,[metaKey]:'modified_conflict'}))
        if(promptOnConflict&&selectedEditorFileRef.current===relativePath){
          openExternalChangePrompt(relativePath,{
            mode:'save_conflict',
            pendingContent:content??''
          })
        }else if(selectedEditorFileRef.current!==relativePath){
          addExternalFileNotification(relativePath,'modified_conflict')
        }
      }
      throw e
    }

    if(result?.mtime_ns){
      const nextMeta={
        mtime_ns:result.mtime_ns,
        size:result.size??result.bytes??0,
        sha256:result.sha256||''
      }
      editorFileDiskMetaRef.current={
        ...editorFileDiskMetaRef.current,
        [metaKey]:nextMeta
      }
      setEditorFileDiskMeta(prev=>({...prev,[metaKey]:nextMeta}))
      setEditorExternalState(prev=>{
        const next={...prev}; delete next[metaKey]; return next
      })
      if(projectFileSnapshotRef.current?.files){
        projectFileSnapshotRef.current={
          ...projectFileSnapshotRef.current,
          files:{...projectFileSnapshotRef.current.files,[metaKey]:nextMeta}
        }
      }
    }

    setEditorFileContents(prev=>({
      ...prev,
      [relativePath]:content??''
    }))

    setEditorFileDirty(prev=>({
      ...prev,
      [relativePath]:false
    }))

    return {
      ...result,
      fullPath
    }
  }

  const saveFile=async()=>{
    if(editorLoadErrors[selected]){
      setFileSaveStatus('저장 차단 · 파일 로드 실패')
      setTerminal(prev=>(prev||'')+'\n[저장 차단] 파일 로드가 실패한 탭은 디스크에 저장하지 않습니다. 먼저 다시 불러오세요.\n')
      return
    }
    if(isBinaryPreviewFile(selected)){
      const presentation=isPresentationFile(selected)
      setFileSaveStatus(presentation?'PowerPoint 읽기 전용':'PDF 읽기 전용')
      setTerminal(prev=>(prev||'')+`\n[${presentation?'PowerPoint':'PDF'}] 바이너리 문서는 미리보기 전용이며 텍스트 저장을 수행하지 않습니다.\n`)
      return
    }
    setFileSaveStatus('저장 중')
    if(!root || !selected){
      setFileSaveStatus('저장 실패')
      setTerminal(prev=>(prev||'')+'\n[저장 실패] 프로젝트와 파일을 먼저 선택하세요.\n')
      return
    }

    try{
      const currentContent=
        editorFileContents[selected] ?? code ?? ''

      const result=await writeEditorFile(
        selected,
        currentContent
      )

      setTerminal(prev=>
        (prev||'')
        + `\n[저장 완료] ${result?.path||result.fullPath}`
        + (result?.bytes!=null?` (${result.bytes} bytes)`:'')
        + '\n'
      )

      setFileSaveStatus('저장 완료')
    }catch(e){
      if(e?.status===409){
        setFileSaveStatus('외부 변경 충돌')
        setTerminal(prev=>(prev||'')+'\n[저장 보류] 외부 파일 변경이 감지되어 사용자 선택을 기다립니다.\n')
      }else{
        setFileSaveStatus('저장 실패')
        setTerminal(prev=>(prev||'')+'\n[저장 실패] '+String(e)+'\n')
      }
    }

    if(focusOwnerRef.current==='editor'){
      setTimeout(()=>{
        try{ editorInstanceRef.current?.focus() }catch{}
      },0)
    }
  }

  const saveDirtyEditorPaths=async(paths,{label='모두 저장'}={})=>{
    const dirtyPaths=(paths||[]).filter(
      path=>!!editorFileDirty[path]
    )

    if(!dirtyPaths.length){
      return {saved:[],failed:[]}
    }

    setFileSaveStatus('저장 중')

    const saved=[]
    const failed=[]

    for(const path of dirtyPaths){
      const content=
        path===selected
          ? (editorFileContents[path] ?? code ?? '')
          : (editorFileContents[path] ?? '')

      try{
        const result=await writeEditorFile(path,content)
        saved.push(result?.path||result.fullPath||path)
      }catch(e){
        failed.push({path,error:String(e)})
      }
    }

    setTerminal(prev=>{
      let text=(prev||'')
        + `\n[${label}] ${saved.length}개 파일 저장 완료`

      if(failed.length){
        text+=` / ${failed.length}개 실패`
        for(const item of failed){
          text+=`\n  - ${item.path}: ${item.error}`
        }
      }

      return text+'\n'
    })

    setFileSaveStatus(
      failed.length?'저장 실패':'저장 완료'
    )

    return {saved,failed}
  }

  const saveAllDirtyFiles=async()=>{
    if(!root){
      setFileSaveStatus('저장 실패')
      setTerminal(prev=>(prev||'')+'\n[모두 저장 실패] 프로젝트를 먼저 선택하세요.\n')
      return
    }

    const dirtyPaths=openEditorFiles.filter(
      path=>!!editorFileDirty[path]
    )

    if(!dirtyPaths.length){
      setFileSaveStatus('저장 완료')
      setTerminal(prev=>(prev||'')+'\n[모두 저장] 수정된 열린 파일이 없습니다.\n')
      return
    }

    await saveDirtyEditorPaths(dirtyPaths,{label:'모두 저장'})

    if(focusOwnerRef.current==='editor'){
      setTimeout(()=>{
        try{ editorInstanceRef.current?.focus() }catch{}
      },0)
    }
  }

  useEffect(()=>{
    const handleEditorSaveShortcut=(e)=>{
      const isSave=
        (e.ctrlKey||e.metaKey)
        && String(e.key).toLowerCase()==='s'

      if(!isSave) return

      // v5.246: AgentStudio 내부 어디에 포커스가 있든 브라우저의
      // "웹페이지 저장(Ctrl+S)" 기본 동작이 먼저 실행되지 않게 합니다.
      // Notebook Cell, AI 변경 제안, LLM 입력창, 파일 트리 등에서도
      // 동일하게 적용됩니다.
      e.preventDefault()
      e.stopPropagation()

      // 키를 오래 누를 때 같은 파일을 중복 저장하지 않습니다.
      if(e.repeat) return

      // Ctrl+Shift+S: 코드 작업공간에서 수정된 모든 열린 파일 저장.
      if(e.shiftKey){
        if(
          screen==='WORKSPACE'
          && workspaceTab==='CODE'
          && root
        ){
          saveAllDirtyFiles()
        }
        return
      }

      // Ctrl+S: 코드 작업공간에서 현재 열린 파일을 저장합니다.
      // focusOwner에 의존하지 않으므로 .ipynb Notebook Cell에 포커스가
      // 있어도 현재 직렬화된 Notebook 문서가 정상 저장됩니다.
      if(
        screen==='WORKSPACE'
        && workspaceTab==='CODE'
        && root
        && selected
      ){
        saveFile()
      }
    }

    window.addEventListener(
      'keydown',
      handleEditorSaveShortcut,
      true
    )

    return()=>{
      window.removeEventListener(
        'keydown',
        handleEditorSaveShortcut,
        true
      )
    }
  },[
    selected,
    code,
    root,
    screen,
    workspaceTab,
    openEditorFiles,
    editorFileContents,
    editorFileDirty
  ])



  useEffect(()=>{
    if(
      screen!=='WORKSPACE'
      || workspaceTab!=='CODE'
      || isSqlFile
      || !activeTerminalId
    ){
      return
    }

    const restorePersistentTerminal=()=>{
      const activeContainer=
        xtermContainersRef.current[activeTerminalId]
      const activeRect=
        activeContainer?.getBoundingClientRect?.()

      if(
        !activeRect
        || activeRect.width<120
        || activeRect.height<80
      ){
        return false
      }

      try{
        for(const terminal of terminalSessions){
          const id=terminal.id
          const container=xtermContainersRef.current[id]
          const rect=container?.getBoundingClientRect?.()

          if(
            !rect
            || rect.width<120
            || rect.height<80
          ){
            continue
          }

          const term=xtermInstancesRef.current[id]
          fitTerminalViewport(id)
          term?.refresh(
            0,
            Math.max(0,(term?.rows||1)-1)
          )
        }

        xtermInstancesRef.current[
          activeTerminalId
        ]?.scrollToBottom()
      }catch{}

      try{
        editorInstanceRef.current?.layout()
      }catch{}

      return true
    }

    let observer=null
    const activeContainer=
      xtermContainersRef.current[activeTerminalId]

    if(
      activeContainer
      && typeof ResizeObserver!=='undefined'
    ){
      observer=new ResizeObserver(()=>{
        if(
          screen==='WORKSPACE'
          && workspaceTab==='CODE'
        ){
          requestAnimationFrame(
            restorePersistentTerminal
          )
        }
      })
      observer.observe(activeContainer)
    }

    const timers=[
      40,
      120,
      260,
      500,
      900,
    ].map(delay=>
      setTimeout(()=>{
        requestAnimationFrame(
          restorePersistentTerminal
        )
      },delay)
    )

    return()=>{
      observer?.disconnect()
      timers.forEach(clearTimeout)
    }
  },[screen,workspaceTab,activeTerminalId,terminalSessions.length,isSqlFile,selected])



  // v5.231: SQL Workspace에서는 terminal-pane이 display:none 상태가 됩니다.
  // SQL 파일 -> 일반 코드 파일로 돌아올 때 xterm DOM은 그대로 유지되지만
  // display:none 동안의 0px geometry를 기준으로 cols/rows가 stale해질 수 있습니다.
  // 파일 종류 전환 직후 visible geometry가 안정된 다음 active terminal을 다시 fit/refresh합니다.
  useEffect(()=>{
    if(
      screen!=='WORKSPACE'
      || workspaceTab!=='CODE'
      || isSqlFile
      || !activeTerminalId
    ) return

    let cancelled=false
    const restoreVisibleTerminal=()=>{
      if(cancelled) return
      const container=xtermContainersRef.current[activeTerminalId]
      const term=xtermInstancesRef.current[activeTerminalId]
      const rect=container?.getBoundingClientRect?.()
      if(!rect||rect.width<120||rect.height<80) return

      fitTerminalViewport(activeTerminalId)
      try{
        term?.refresh(0,Math.max(0,(term?.rows||1)-1))
        term?.scrollToBottom()
      }catch{}
    }

    let raf2=0
    const raf1=requestAnimationFrame(()=>{
      raf2=requestAnimationFrame(restoreVisibleTerminal)
    })
    const timers=[60,180,420].map(delay=>setTimeout(restoreVisibleTerminal,delay))

    return()=>{
      cancelled=true
      cancelAnimationFrame(raf1)
      if(raf2) cancelAnimationFrame(raf2)
      timers.forEach(clearTimeout)
    }
  },[screen,workspaceTab,isSqlFile,selected,activeTerminalId])



  const refreshMcp=async()=>{
    try{
      const servers=await api('/mcp/servers')
      setMcpServers(Array.isArray(servers)?servers:(servers?.servers||[]))
      const tools=await api('/mcp/tools')
      setMcpTools(Array.isArray(tools)?tools:(tools?.tools||[]))
    }catch(e){
      console.error('MCP 목록 새로고침 실패',e)
    }
  }

  const openMcpAddDialog=()=>{
    setMcpAddError('')
    setMcpAddOpen(true)
    setScreen('MCP')
    refreshMcp()
  }

  const closeMcpAddDialog=()=>{
    if(mcpAddBusy) return
    setMcpAddOpen(false)
    setMcpAddError('')
  }

  const submitMcpServer=async()=>{
    const name=String(mcpAddForm.name||'').trim()
    const endpoint=String(mcpAddForm.endpoint||'').trim()

    if(!name){
      setMcpAddError('MCP 서버 이름을 입력하세요.')
      return
    }
    if(!endpoint){
      setMcpAddError('MCP Endpoint를 입력하세요.')
      return
    }

    setMcpAddBusy(true)
    setMcpAddError('')
    try{
      const created=await api('/mcp/servers',{
        method:'POST',
        body:JSON.stringify({
          name,
          endpoint,
          trust_level:mcpAddForm.trust_level||'UNTRUSTED',
          allow_read_without_prompt:!!mcpAddForm.allow_read_without_prompt,
          allow_write_without_prompt:!!mcpAddForm.allow_write_without_prompt,
        })
      })

      let syncWarning=''
      if(created?.id){
        try{
          await api(`/mcp/servers/${created.id}/sync`,{method:'POST'})
        }catch(syncError){
          syncWarning=`서버는 등록되었지만 Tool 동기화에 실패했습니다: ${String(syncError)}`
        }
      }

      await refreshMcp()
      setMcpAddForm({
        name:'',
        endpoint:'',
        trust_level:'UNTRUSTED',
        allow_read_without_prompt:false,
        allow_write_without_prompt:false,
      })

      if(syncWarning){
        setMcpAddError(syncWarning)
      }else{
        setMcpAddOpen(false)
      }
    }catch(e){
      setMcpAddError(String(e))
    }finally{
      setMcpAddBusy(false)
    }
  }

  const syncMcpServer=async(serverId)=>{
    if(!serverId) return
    try{
      await api(`/mcp/servers/${serverId}/sync`,{method:'POST'})
      await refreshMcp()
    }catch(e){
      setMcpAddError(`MCP Tool 동기화 실패: ${String(e)}`)
      setMcpAddOpen(true)
    }
  }



  const getEditorFileFullPath=(relativePath)=>{
    if(!relativePath) return root||''

    const cleanRoot=String(root||'')
      .replace(/[\\/]+$/,'')

    const cleanRelative=String(relativePath)
      .replace(/^[\\/]+/,'')
      .replace(/\//g,'\\')

    return cleanRoot
      ? `${cleanRoot}\\${cleanRelative}`
      : cleanRelative
  }

  const copyEditorFileFullPath=async(relativePath)=>{
    const fullPath=getEditorFileFullPath(relativePath)
    if(!fullPath) return

    try{
      await navigator.clipboard.writeText(fullPath)
      setEditorTabMenu(null)
    }catch(e){
      window.prompt('전체 경로를 복사하세요.',fullPath)
    }
  }


  const activateEditorFile=(relativePath)=>{
    if(!relativePath) return

    setSelected(relativePath)
    setFileTreeSelected(relativePath)
    setFileTreeSelectedPaths([relativePath])
    setCode(editorFileContents[relativePath]??'')
    setFileSaveStatus('')

    if(editorExternalState[normalizeProjectRelativePath(relativePath)]==='modified_conflict'){
      openExternalChangePrompt(relativePath)
    }
  }

  const toggleEditorFilePin=(relativePath)=>{
    if(!relativePath) return

    setPinnedEditorFiles(prev=>
      prev.includes(relativePath)
        ? prev.filter(path=>path!==relativePath)
        : [...prev,relativePath]
    )

    setEditorTabMenu(null)
  }

  const closeEditorFiles=(pathsToClose)=>{
    const closeSet=new Set(pathsToClose||[])
    if(!closeSet.size) return

    const selectedIndex=openEditorFiles.indexOf(selected)
    const nextFiles=openEditorFiles.filter(
      path=>!closeSet.has(path)
    )

    setOpenEditorFiles(nextFiles)

    setEditorFileContents(prev=>{
      const next={...prev}
      for(const path of closeSet){
        delete next[path]
      }
      return next
    })

    setEditorFileDirty(prev=>{
      const next={...prev}
      for(const path of closeSet){
        delete next[path]
      }
      return next
    })

    setPinnedEditorFiles(prev=>
      prev.filter(path=>!closeSet.has(path))
    )

    if(closeSet.has(selected)){
      const nextActive=
        nextFiles[Math.min(
          Math.max(selectedIndex,0),
          Math.max(nextFiles.length-1,0)
        )]
        || nextFiles[nextFiles.length-1]
        || ''

      setSelected(nextActive)
      setFileTreeSelected(nextActive)
      setCode(
        nextActive
          ? (editorFileContents[nextActive]??'')
          : ''
      )
      setFileSaveStatus('')
    }
  }

  const requestEditorFilesClose=(pathsToClose)=>{
    const openSet=new Set(openEditorFiles)
    const targets=[...new Set(pathsToClose||[])].filter(
      path=>openSet.has(path)
    )

    setEditorFilesMenu(null)
    setEditorTabMenu(null)

    if(!targets.length) return

    const dirtyPaths=targets.filter(
      path=>!!editorFileDirty[path]
    )

    if(!dirtyPaths.length){
      closeEditorFiles(targets)
      return
    }

    setEditorCloseConfirm({
      paths:targets,
      dirtyPaths,
      saving:false,
      error:''
    })
  }

  const handleEditorCloseDecision=async(decision)=>{
    const pending=editorCloseConfirm
    if(!pending || pending.saving) return

    if(decision==='cancel'){
      setEditorCloseConfirm(null)
      return
    }

    if(decision==='discard'){
      closeEditorFiles(pending.paths)
      setEditorCloseConfirm(null)
      return
    }

    if(decision!=='save') return

    setEditorCloseConfirm(prev=>prev?{
      ...prev,
      saving:true,
      error:''
    }:prev)

    const {failed}=await saveDirtyEditorPaths(
      pending.dirtyPaths,
      {label:'닫기 전 저장'}
    )

    if(failed.length){
      setEditorCloseConfirm(prev=>prev?{
        ...prev,
        saving:false,
        error:`${failed.length}개 파일 저장에 실패했습니다. 실패한 파일을 확인한 뒤 다시 시도하세요.`
      }:prev)
      return
    }

    closeEditorFiles(pending.paths)
    setEditorCloseConfirm(null)
  }

  const closeAllEditorFiles=()=>{
    requestEditorFilesClose([...openEditorFiles])
  }

  const closeUnpinnedEditorFiles=()=>{
    const pinned=new Set(pinnedEditorFiles)
    requestEditorFilesClose(
      openEditorFiles.filter(path=>!pinned.has(path))
    )
  }

  const closeEditorFile=(relativePath)=>{
    requestEditorFilesClose([relativePath])
  }

  const updateActiveEditorCode=(value)=>{
    setFocusOwnerSafe('editor')
    const next=value??''

    setCode(next)

    queueMicrotask(()=>{
      if(focusOwnerRef.current==='editor'){
        try{ editorInstanceRef.current?.focus() }catch{}
      }
    })
    setFileSaveStatus('')

    if(selected){
      setEditorFileContents(prev=>({
        ...prev,
        [selected]:next
      }))

      setEditorFileDirty(prev=>({
        ...prev,
        [selected]:true
      }))
    }
  }


  const openFile=async(relativePath)=>{
    setWorkspaceTab('CODE')

    const requestedPath=relativePath
    if(!requestedPath) return

    if(openEditorFiles.includes(requestedPath)){
      setSelected(requestedPath)
      setFileTreeSelected(requestedPath)
      setCode(editorFileContents[requestedPath]??'')
      setFileSaveStatus('')
      return
    }

    const token=++fileLoadTokenRef.current

    setSelected(requestedPath)
    setFileTreeSelected(requestedPath)
    setFileLoading(true)

    try{
      if(isBinaryPreviewFile(requestedPath)){
        let meta=null
        try{
          meta=await api(`/files/meta?root=${encodeURIComponent(activeWorkspaceRoot)}&relative_path=${encodeURIComponent(requestedPath)}`)
        }catch(_){ }

        if(token!==fileLoadTokenRef.current) return

        const metaKey=normalizeProjectRelativePath(requestedPath)
        if(meta?.exists){
          const loadedMeta={
            mtime_ns:meta.mtime_ns||0,
            size:meta.size||0,
            sha256:meta.sha256||''
          }
          editorFileDiskMetaRef.current={
            ...editorFileDiskMetaRef.current,
            [metaKey]:loadedMeta
          }
          setEditorFileDiskMeta(prev=>({...prev,[metaKey]:loadedMeta}))
        }

        setOpenEditorFiles(prev=>prev.includes(requestedPath)?prev:[...prev,requestedPath])
        setEditorFileContents(prev=>({...prev,[requestedPath]:''}))
        setEditorFileDirty(prev=>({...prev,[requestedPath]:false}))
        if(isPdfFile(requestedPath)){
          setPdfPreviewRevision(prev=>({...prev,[metaKey]:Date.now()}))
        }else{
          setPresentationPreviewRevision(prev=>({...prev,[metaKey]:Date.now()}))
        }
        setCode('')
        setSelected(requestedPath)
        setFileTreeSelected(requestedPath)
        setFileSaveStatus(isPdfFile(requestedPath)?'PDF 미리보기':'PowerPoint 미리보기')
        return
      }

      const r=await api('/files/read',{
        method:'POST',
        body:JSON.stringify({
          root:activeWorkspaceRoot,
          relative_path:requestedPath
        })
      })

      if(token!==fileLoadTokenRef.current) return

      const content=r.content??''
      const canonicalPath=r.relative_path||requestedPath
      const metaKey=normalizeProjectRelativePath(canonicalPath)
      if(r.mtime_ns){
        const loadedMeta={
          mtime_ns:r.mtime_ns,
          size:r.size||0,
          sha256:r.sha256||''
        }
        editorFileDiskMetaRef.current={
          ...editorFileDiskMetaRef.current,
          [metaKey]:loadedMeta
        }
        setEditorFileDiskMeta(prev=>({
          ...prev,
          [metaKey]:loadedMeta
        }))
        setEditorExternalState(prev=>{
          const next={...prev}; delete next[metaKey]; return next
        })
      }

      setOpenEditorFiles(prev=>
        prev.includes(requestedPath)
          ? prev
          : [...prev,requestedPath]
      )
      setEditorFileContents(prev=>({
        ...prev,
        [requestedPath]:content
      }))
      setEditorFileDirty(prev=>({
        ...prev,
        [requestedPath]:false
      }))

      setCode(content)
      setSelected(requestedPath)
      setFileTreeSelected(requestedPath)
      setEditorLoadErrors(prev=>{const next={...prev}; delete next[requestedPath]; return next})
      setFileSaveStatus('')
    }catch(e){
      if(token!==fileLoadTokenRef.current) return

      const message=String(e?.message||e)

      // v5.250: 파일 읽기 실패 메시지를 실제 Editor buffer에 넣지 않습니다.
      // 과거에는 이 오류 placeholder가 Ctrl+S/저장 경로를 통해 실제 .ipynb에
      // 덮어써질 수 있었습니다. 오류는 전용 상태로만 표시합니다.
      setOpenEditorFiles(prev=>
        prev.includes(requestedPath)
          ? prev
          : [...prev,requestedPath]
      )
      setEditorLoadErrors(prev=>({
        ...prev,
        [requestedPath]:{
          message,
          path:requestedPath,
          time:new Date().toISOString(),
        }
      }))
      setEditorFileDirty(prev=>({
        ...prev,
        [requestedPath]:false
      }))

      const previous=editorFileContents[requestedPath]
      setCode(previous??'')
      setSelected(requestedPath)
      setFileTreeSelected(requestedPath)
      setFileSaveStatus('파일 로드 실패')
    }finally{
      if(token===fileLoadTokenRef.current){
        setFileLoading(false)
      }
    }
  }

  const loadWorkflowDefinition=async()=>{
    try{
      const result=await api('/workflow/definition')
      setWorkflowDefinition(result)
      return result
    }catch(e){
      setWorkflowDefinition({
        ok:false,
        error:String(e)
      })
      return null
    }
  }

  const requirementKeywordDefinitions=[
    {id:'purpose',label:'목적',keywords:['agent','요약','프로그램','만들']},
    {id:'files',label:'파일 형식',keywords:['.txt','.md','.py','파일 형식','확장자']},
    {id:'output',label:'결과 형식',keywords:['한국어','json','결과','저장','.txt','.md']},
    {id:'llm',label:'LLM',keywords:['gpt-4o-mini','openai','ollama','llm']},
    {id:'ui',label:'UI',keywords:['react','vite','웹 gui','웹 ui']},
    {id:'backend',label:'Backend',keywords:['fastapi','uvicorn','backend','백엔드']},
    {id:'mcp',label:'MCP / Transport',keywords:['mcp','stdio','streamable http','transport']},
    {id:'database',label:'DB',keywords:['데이터베이스','database','postgresql','db']},
    {id:'permission',label:'권한 / 파일 접근',keywords:['권한','인증','rbac','project root','프로젝트 root','root 내부']},
    {id:'runtime',label:'실행 환경',keywords:['windows 10','windows 11','python 3.12','온프레미스','로컬 pc','local']},
    {id:'limits',label:'처리 제한',keywords:['10mb','120초','timeout','타임아웃','chunk','청크']}
  ]

  const requirementDraftKey=()=>{
    const path=String(newAgentProjectRoot||root||'')
      .trim()
      .replace(/[\\/]+$/,'')
      .toLowerCase()

    const name=String(newAgentName||'')
      .trim()
      .toLowerCase()

    const identity=path||name||'unsaved-agent'
    return `theanova.agentstudio.requirements.v1::${identity}`
  }

  const requirementConversationText=()=>{
    return (chat||[])
      .map(item=>String(item?.content||''))
      .join('\n')
      .toLowerCase()
  }

  const getRequirementKeywordStatus=()=>{
    const text=requirementConversationText()
    const firstUser=(chat||[]).find(item=>item?.role==='user')
    const confirmed=confirmedInterviewRequirements||{}

    const includesAny=(values=[])=>values.some(value=>
      text.includes(String(value).toLowerCase())
    )

    const unique=(values=[])=>[
      ...new Set(
        values
          .map(value=>String(value||'').trim())
          .filter(Boolean)
      )
    ]

    const getValue=(id)=>{
      switch(id){
        case 'purpose':{
          const raw=String(
            confirmed?.original_request
            ||firstUser?.content
            ||workflowReq
            ||''
          ).trim()

          if(!raw) return ''

          // 우측 요약은 너무 길지 않게 목적의 핵심만 표시합니다.
          if(
            includesAny(['파일','요약'])
            &&includesAny(['agent','에이전트'])
          ){
            return '프로젝트 파일 요약 Agent'
          }

          return raw.length>48
            ? `${raw.slice(0,48)}…`
            : raw
        }

        case 'files':{
          const values=
            confirmed?.file_access?.allowed_extensions?.length
              ? confirmed.file_access.allowed_extensions
              : [
                  text.includes('.txt')?'.txt':'',
                  text.includes('.md')?'.md':'',
                  text.includes('.py')?'.py':''
                ]

          return unique(values).join(', ')
        }

        case 'output':{
          const values=[]

          if(
            confirmed?.result?.ui_display
            ||includesAny(['react 웹 ui','react ui','웹 ui'])
          ){
            values.push('React UI')
          }
          if(includesAny(['한국어 텍스트','한국어'])){
            values.push('한국어')
          }
          if(includesAny(['json 구조','json'])){
            values.push('JSON API')
          }

          const formats=
            confirmed?.result?.export_formats
            ||[
              text.includes('.txt')?'TXT':'',
              text.includes('.md')?'MD':''
            ]

          const normalizedFormats=unique(formats)
            .map(value=>value.replace('.','').toUpperCase())

          if(normalizedFormats.length){
            values.push(`${normalizedFormats.join('/')} 저장`)
          }

          return unique(values).join(' · ')
        }

        case 'llm':{
          const values=[]

          const defaultModel=
            confirmed?.llm?.default_model
            ||(text.includes('gpt-4o-mini')?'gpt-4o-mini':'')

          if(defaultModel) values.push(defaultModel)

          if(
            confirmed?.llm?.ollama_supported
            ||text.includes('ollama')
          ){
            values.push('Ollama')
          }

          return unique(values).join(', ')
        }

        case 'ui':{
          if(
            String(confirmed?.ui||'').toLowerCase().includes('react')
            ||includesAny(['react + vite','react+vite','react 기반'])
          ){
            return includesAny(['vite'])?'React + Vite':'React'
          }
          return confirmed?.ui||''
        }

        case 'backend':{
          const values=[]

          if(
            String(confirmed?.backend||'').toLowerCase().includes('fastapi')
            ||text.includes('fastapi')
          ){
            values.push('FastAPI')
          }

          if(text.includes('uvicorn')){
            values.push('Uvicorn')
          }

          return unique(values).join(' + ')
        }

        case 'mcp':{
          const values=[]

          const transport=
            confirmed?.mcp?.default_transport
            ||(text.includes('stdio')?'stdio':'')

          if(transport) values.push(transport)

          if(
            confirmed?.mcp?.future_transport==='streamable_http'
            ||text.includes('streamable http')
          ){
            values.push('Streamable HTTP 확장')
          }

          return unique(values).join(' · ')
        }

        case 'database':{
          if(
            confirmed?.database?.enabled===false
            ||includesAny([
              '데이터베이스를 사용하지',
              'db 사용하지',
              '이번 버전에서는 db',
              '이번 버전에서는 데이터베이스'
            ])
          ){
            return (
              confirmed?.database?.future_extension
              ||text.includes('postgresql')
            )
              ? '미사용 · PostgreSQL 확장'
              : '미사용'
          }

          if(text.includes('postgresql')){
            return 'PostgreSQL'
          }

          return ''
        }

        case 'permission':{
          const values=[]

          if(
            confirmed?.file_access?.restrict_to_project_root
            ||includesAny([
              'project root 내부',
              '프로젝트 root 내부',
              'root 내부'
            ])
          ){
            values.push('Project Root 내부')
          }

          const extensions=
            confirmed?.file_access?.allowed_extensions||[]

          if(extensions.length){
            values.push(
              `${extensions.join('/')} 제한`
            )
          }

          if(
            includesAny([
              '사용자 인증이나 역할 기반 권한 관리',
              '별도의 사용자 인증',
              'rbac는 사용하지',
              '단일 로컬 사용자'
            ])
          ){
            values.push('로그인/RBAC 없음')
          }

          return unique(values).join(' · ')
        }

        case 'runtime':{
          const values=[]

          if(
            includesAny(['windows 10/11','windows 10','windows 11'])
          ){
            values.push('Windows 10/11')
          }

          if(
            includesAny(['python 3.12'])
          ){
            values.push('Python 3.12')
          }

          if(
            includesAny(['.venv','가상환경'])
          ){
            values.push('.venv')
          }

          if(
            includesAny(['온프레미스'])
          ){
            values.push('온프레미스')
          }

          return unique(values).join(' · ')
        }

        case 'limits':{
          const values=[]

          if(
            includesAny(['10mb','10 mb'])
          ){
            values.push('10MB')
          }

          if(
            includesAny(['120초','120초로','120 second','120s'])
          ){
            values.push('120초')
          }

          if(
            includesAny(['chunk','청크'])
          ){
            values.push('Chunking')
          }

          return unique(values).join(' · ')
        }

        default:
          return ''
      }
    }

    return requirementKeywordDefinitions.map(def=>{
      let collected=def.keywords.some(keyword=>
        text.includes(String(keyword).toLowerCase())
      )

      if(def.id==='purpose'){
        collected=Boolean(
          String(firstUser?.content||workflowReq||'').trim()
        )
      }

      if(def.id==='llm' && confirmed?.llm){
        collected=true
      }
      if(def.id==='files' && confirmed?.file_access?.allowed_extensions?.length){
        collected=true
      }
      if(def.id==='mcp' && confirmed?.mcp){
        collected=true
      }
      if(def.id==='database' && confirmed?.database){
        collected=true
      }
      if(def.id==='output' && confirmed?.result){
        collected=true
      }
      if(def.id==='ui' && confirmed?.ui){
        collected=true
      }
      if(def.id==='backend' && confirmed?.backend){
        collected=true
      }
      if(
        def.id==='permission'
        &&confirmed?.file_access?.restrict_to_project_root
      ){
        collected=true
      }

      const value=getValue(def.id)

      // 명확한 실제 값이 추출되면 해당 슬롯은 수집 완료로 간주합니다.
      if(value){
        collected=true
      }

      return {
        ...def,
        collected,
        value
      }
    })
  }


  const buildRequirementDraftSnapshot=()=>{
    return {
      version:1,
      saved_at:new Date().toISOString(),
      agent_name:newAgentName||'',
      project_root:newAgentProjectRoot||root||'',
      workflow_request:workflowReq||'',
      chat:Array.isArray(chat)?chat:[],
      confirmed_requirements:confirmedInterviewRequirements||{},
      workflow_preview:targetWorkflowPreview||null,
      workflow_quality:targetWorkflowQuality||null,
      agent_build_stage:agentBuildStage||'REQUIREMENTS'
    }
  }

  const saveRequirementDraft=()=>{
    try{
      const snapshot=buildRequirementDraftSnapshot()
      const hasUsefulData=
        snapshot.chat.some(item=>item?.role==='user')
        || Boolean(snapshot.workflow_request)
        || Object.keys(snapshot.confirmed_requirements||{}).length>0
        || Boolean(snapshot.workflow_preview)

      if(!hasUsefulData) return false

      localStorage.setItem(
        requirementDraftKey(),
        JSON.stringify(snapshot)
      )
      setRequirementDraftSavedAt(snapshot.saved_at)
      return true
    }catch(e){
      console.warn('요구사항 Draft 저장 실패',e)
      return false
    }
  }

  const restoreRequirementDraft=(keyOverride='')=>{
    try{
      const key=keyOverride||requirementDraftKey()
      const raw=localStorage.getItem(key)

      if(!raw) return false

      const snapshot=JSON.parse(raw)

      if(Array.isArray(snapshot?.chat) && snapshot.chat.length){
        setChat(snapshot.chat)
        setBuilderStarted(
          snapshot.chat.some(item=>item?.role==='user')
        )
      }

      if(snapshot?.workflow_request){
        setWorkflowReq(snapshot.workflow_request)
      }

      if(snapshot?.confirmed_requirements){
        setConfirmedInterviewRequirements(
          snapshot.confirmed_requirements
        )
      }

      if(snapshot?.workflow_preview){
        setTargetWorkflowPreview(snapshot.workflow_preview)
        setTargetWorkflowQuality(snapshot.workflow_quality||null)
        setAgentBuildStage('WORKFLOW_READY')
      }else if(snapshot?.agent_build_stage){
        setAgentBuildStage(
          snapshot.agent_build_stage==='BUILDING'
            ? 'PROJECT_CREATED'
            : snapshot.agent_build_stage
        )
      }

      if(snapshot?.agent_name && !newAgentName){
        setNewAgentName(snapshot.agent_name)
      }

      setRequirementDraftSavedAt(snapshot?.saved_at||'')
      setRequirementDraftRestored(true)
      return true
    }catch(e){
      console.warn('요구사항 Draft 복원 실패',e)
      return false
    }
  }

  const clearRequirementDraft=()=>{
    try{
      localStorage.removeItem(requirementDraftKey())
    }catch{}
    setRequirementDraftSavedAt('')
    setRequirementDraftRestored(false)
  }

  const buildRequirementRequestFromCollectedInfo=()=>{
    const userMessages=(chat||[])
      .filter(item=>item?.role==='user')
      .map(item=>String(item?.content||'').trim())
      .filter(Boolean)

    const confirmed=confirmedInterviewRequirements||{}

    if(userMessages.length){
      return userMessages.join('\n\n')
    }

    if(workflowReq?.trim()){
      return workflowReq.trim()
    }

    const rows=[]

    if(confirmed.original_request){
      rows.push(confirmed.original_request)
    }
    if(confirmed.ui){
      rows.push(`UI: ${confirmed.ui}`)
    }
    if(confirmed.backend){
      rows.push(`Backend: ${confirmed.backend}`)
    }
    if(confirmed.llm){
      rows.push(
        `LLM: ${confirmed.llm.default_provider||''} ${confirmed.llm.default_model||''}; Ollama 전환 가능`
      )
    }
    if(confirmed.file_access?.allowed_extensions?.length){
      rows.push(
        `파일 형식: ${confirmed.file_access.allowed_extensions.join(', ')}`
      )
    }
    if(confirmed.mcp){
      rows.push(
        `MCP: ${confirmed.mcp.default_transport||'stdio'}`
      )
    }
    if(confirmed.database){
      rows.push(
        `DB: ${confirmed.database.enabled?'사용':'현재 미사용'}`
      )
    }

    return rows.join('\n')
  }

  const canDesignFromCollectedInfo=()=>{
    const statuses=getRequirementKeywordStatus()
    const collectedCount=statuses.filter(x=>x.collected).length
    return Boolean(
      workflowReq?.trim()
      || (chat||[]).some(item=>item?.role==='user')
      || collectedCount>=3
      || targetWorkflowPreview
    )
  }


  const buildConfirmedRequirementsFromChat=()=>{
    const userMessages=(chat||[])
      .filter(item=>item?.role==='user')
      .map(item=>String(item?.content||'').trim())
      .filter(Boolean)

    const assistantMessages=(chat||[])
      .filter(item=>item?.role==='assistant')
      .map(item=>String(item?.content||'').trim())
      .filter(Boolean)

    const allText=[
      ...userMessages,
      ...assistantMessages
    ].join('\n').toLowerCase()

    const has=(...values)=>values.some(value=>
      allText.includes(String(value).toLowerCase())
    )

    const extensions=[
      has('.txt')?'.txt':'',
      has('.md')?'.md':'',
      has('.py')?'.py':''
    ].filter(Boolean)

    const requirements={
      original_request:userMessages[0]||workflowReq||'',
      user_answers:userMessages.slice(1),
      latest_analysis:
        [...assistantMessages]
          .reverse()
          .find(text=>text.includes('요구사항 분석 완료'))||'',

      ui:has('react')
        ? (has('vite')?'React + Vite':'React 기반 웹 GUI')
        : '',

      backend:has('fastapi')
        ? (has('uvicorn')?'FastAPI + Uvicorn':'FastAPI')
        : '',

      llm:{
        default_provider:has('openai')?'OpenAI':'',
        default_model:has('gpt-4o-mini')?'gpt-4o-mini':'',
        configurable_provider:has(
          'provider',
          '설정 파일',
          '환경변수',
          '.env'
        ),
        ollama_supported:has('ollama')
      },

      file_access:{
        allowed_extensions:
          extensions.length
            ? extensions
            : ['.txt','.md','.py'],
        restrict_to_project_root:has(
          'project root 내부',
          '프로젝트 root 내부',
          'root 내부'
        ),
        user_select_or_input:has(
          '파일을 선택',
          '파일 선택',
          '파일을 지정',
          '파일 경로'
        )
      },

      mcp:{
        default_transport:has('stdio')?'stdio':'',
        future_transport:has('streamable http')
          ? 'streamable_http'
          : '',
        transport_layer_separated:has(
          'transport 계층',
          'transport를 분리',
          'transport 계층을 분리'
        )
      },

      database:{
        enabled:!(
          has(
            '데이터베이스를 사용하지',
            'db 사용하지',
            '이번 버전에서는 db',
            '이번 버전에서는 데이터베이스'
          )
        ),
        future_extension:has('postgresql')
      },

      result:{
        ui_display:has(
          'react 웹 ui',
          'react ui',
          '웹 ui'
        ),
        language:has('한국어')?'ko':'',
        api_format:has('json')?'json':'',
        export_formats:[
          has('.txt','txt 파일')?'txt':'',
          has('.md','md 파일')?'md':''
        ].filter(Boolean)
      },

      processing:{
        max_file_size_mb:has('10mb','10 mb')?10:null,
        timeout_seconds:has('120초','120 second','120s')?120:null,
        chunking:has('chunk','청크')
      },

      runtime:{
        os:has('windows 10/11','windows 10','windows 11')
          ? 'Windows 10/11'
          : '',
        python:has('python 3.12')?'3.12':'',
        virtual_env:has('.venv','가상환경')?'.venv':'',
        deployment:has('온프레미스')?'on-premise':''
      },

      auth:{
        enabled:!(
          has(
            '별도의 사용자 인증',
            '사용자 인증이나 역할 기반 권한 관리',
            'rbac는 사용하지'
          )
        ),
        rbac:false
      }
    }

    setConfirmedInterviewRequirements(requirements)
    return requirements
  }


  const isBuildContinueCommand=(text='')=>{
    const value=String(text||'')
      .trim()
      .replace(/[.!?]+$/g,'')
      .replace(/\s+/g,' ')

    return [
      '진행',
      '진행해',
      '진행해줘',
      '이대로 진행',
      '이대로 진행해',
      '이대로 진행해줘',
      '프로젝트 생성',
      '개발 시작',
      '개발해줘',
      '만들어줘',
      '생성해줘'
    ].includes(value)
  }

  const createAgentProjectFromInterview=async()=>{
    const name=newAgentName.trim()
    const projectRoot=newAgentProjectRoot.trim()

    if(!name){
      setAgentBuildMessage('에이전트 이름을 먼저 입력하세요.')
      return false
    }

    if(!projectRoot){
      setAgentBuildMessage('프로젝트 경로를 먼저 입력하거나 경로 찾기로 선택하세요.')
      return false
    }

    const requestCreate=async(forceRecreate=false)=>{
      return await api('/projects/create-agent',{
        method:'POST',
        body:JSON.stringify({
          name,
          project_root:projectRoot,
          cache_path:newAgentCachePath,
          temp_path:newAgentTempPath,
          output_path:newAgentOutputPath,
          venv_path:newAgentVenvPath,
          models_path:newAgentModelsPath,
          force_recreate:forceRecreate
        })
      })
    }

    setAgentBuildBusy(true)
    setAgentBuildMessage('프로젝트 폴더와 프로젝트 정보를 생성하고 있습니다...')

    try{
      let result=await requestCreate(false)

      if(
        result?.ok===false
        && result?.conflict_type==='PROJECT_PATH_ALREADY_REGISTERED'
        && result?.can_recreate
      ){
        const recreate=window.confirm(
          '이미 등록된 프로젝트 경로입니다.\\n\\n'
          +'기존 DB 프로젝트 정보를 재사용하고 이 경로에 Agent를 재생성하시겠습니까?\\n\\n'
          +'[확인] 재생성\\n'
          +'[취소] 신규 Agent 설계 화면에서 경로 변경'
        )

        if(!recreate){
          setNewAgentCreateResult(result)
          setAgentBuildMessage(
            '프로젝트 재생성을 취소했습니다. 경로를 변경하려면 "신규 Agent 설계" 버튼을 이용하세요.'
          )
          return false
        }

        setAgentBuildMessage('기존 프로젝트를 재사용하여 재생성 준비 중입니다...')
        result=await requestCreate(true)
      }

      setNewAgentCreateResult(result)

      if(!result?.ok){
        throw new Error(result?.message||'프로젝트 생성에 실패했습니다.')
      }

      const resolvedRoot=result.project_root||projectRoot

      setSelectedProjectId(result.project_id||null)
      setRoot(resolvedRoot)
      setAgentBuildStage('PROJECT_CREATED')
      setAgentBuildMessage(
        result?.recreated
          ? `프로젝트 재생성 준비 완료${result.project_id?` · Project #${result.project_id}`:''}`
          : `프로젝트 생성 완료${result.project_id?` · Project #${result.project_id}`:''}`
      )

      try{ await refreshProjectList() }catch(_){}
      try{ await loadFiles(resolvedRoot) }catch(_){}

      return true
    }catch(e){
      setAgentBuildMessage(`프로젝트 생성 실패: ${String(e)}`)
      return false
    }finally{
      setAgentBuildBusy(false)
      setActiveWorkflowJobId('')
    }
  }

  const runProjectCodingStyleValidation=async(projectRoot)=>{
    const rootPath=(projectRoot||root||newAgentProjectRoot||'').trim()

    if(!rootPath){
      return null
    }

    try{
      const rows=await api(`/files?root=${encodeURIComponent(rootPath)}`)
      const fileRows=Array.isArray(rows)?rows:(rows?.files||[])
      const codeFiles=fileRows.filter(item=>{
        const path=typeof item==='string'?item:(item?.path||item?.full_path||'')
        return /\.(py|js|jsx|ts|tsx)$/i.test(path)
      }).slice(0,80)

      const results=[]

      for(const item of codeFiles){
        const path=typeof item==='string'?item:(item?.path||item?.full_path||'')
        if(!path) continue

        try{
          const file=await api(`/file?path=${encodeURIComponent(path)}`)
          const content=typeof file==='string'?file:(file?.content||'')

          const validation=await api('/coding-style/validate',{
            method:'POST',
            body:JSON.stringify({
              code:content,
              request:workflowReq||'',
              path,
              project_scope:true
            })
          })

          results.push({
            path,
            ok:validation?.ok!==false,
            violations:validation?.violations||[]
          })
        }catch(_){}
      }

      const violations=results.flatMap(row=>
        (row.violations||[]).map(item=>({
          ...item,
          path:row.path
        }))
      )

      const fail=violations.filter(item=>String(item?.severity||'').toLowerCase()==='error')
      const warning=violations.filter(item=>String(item?.severity||'').toLowerCase()==='warning')

      const report={
        checked_files:results.length,
        pass:Math.max(0,results.length-fail.length),
        warning:warning.length,
        fail:fail.length,
        violations,
        ok:fail.length===0
      }

      setCodingStyleReport(report)
      setReportGeneratedAt(new Date().toISOString())
      return report
    }catch(e){
      const report={
        checked_files:0,
        pass:0,
        warning:0,
        fail:1,
        violations:[{
          severity:'error',
          message:`코딩 스타일 검증 실행 실패: ${String(e)}`
        }],
        ok:false
      }
      setCodingStyleReport(report)
      return report
    }
  }

  const cancelAgentDevelopment=async()=>{
    const jobId=activeWorkflowJobId
    if(!jobId) return
    try{
      await api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'})
      setAgentBuildMessage('Agent 개발 실행 중지 요청을 보냈습니다.')
      setDevelopmentProgress(prev=>({...prev,active:false,stage:'실행 취소',detail:'사용자가 Agent Factory 실행을 중지했습니다.'}))
    }catch(e){
      window.alert(`Agent 개발 실행 중지 실패: ${e}`)
    }
  }

  const startAgentDevelopment=async()=>{
    const request=(
      workflowReq
      || chat.find(x=>x?.role==='user')?.content
      || ''
    ).trim()

    if(!request){
      setAgentBuildMessage('개발 요청 내용이 없습니다.')
      return
    }

    if(agentBuildStage==='REQUIREMENTS'){
      setAgentBuildMessage('먼저 대상 Agent Workflow를 설계합니다...')
      await previewTargetWorkflow(request)
      return
    }

    if(agentBuildStage==='WORKFLOW_READY'){
      setAgentBuildMessage('개발 전에 프로젝트를 먼저 생성해야 합니다.')
      return
    }

    if(agentBuildStage!=='PROJECT_CREATED'){
      return
    }

    const projectRoot=(root||newAgentProjectRoot||'').trim()

    if(!projectRoot){
      setAgentBuildMessage('프로젝트 경로가 없습니다.')
      return
    }

    // v5.166: Frontend만 새 버전이고 이전 Backend가 살아 있는 혼합 실행을 차단합니다.
    // 실제 사용자 로그에서 v5.165 UI가 v5.164 Backend의 /workflow/start를 호출한 사례가 있어
    // Agent Factory 시작 전에 Health Version을 반드시 확인합니다.
    try{
      const health=await api('/health')
      const backendVersion=String(health?.version||'').trim()
      if(backendVersion!==AGENTSTUDIO_FRONTEND_VERSION){
        const message=(
          `AgentStudio 버전이 서로 다릅니다. Frontend v${AGENTSTUDIO_FRONTEND_VERSION} / `+
          `Backend v${backendVersion||'확인 불가'}\n\n`+
          '기존 AgentStudio Backend/Frontend를 모두 종료한 뒤 현재 버전의 SYSTEM_ADMIN.cmd로 다시 실행해 주세요.'
        )
        setAgentBuildMessage(message)
        window.alert(message)
        return
      }
    }catch(e){
      const message=`Backend 버전 확인에 실패했습니다. Agent 개발을 시작하지 않습니다.\n${String(e)}`
      setAgentBuildMessage(message)
      window.alert(message)
      return
    }

    // 개발 시작을 누르면 즉시 실행 결과 탭으로 이동하여
    // Progress/최종 상태/실패 리포트를 같은 화면에서 확인합니다.
    setScreen('WORKSPACE')
    setWorkspaceTab('RUN')

    setAgentBuildBusy(true)
    setAgentBuildStage('BUILDING')
    setDevelopmentFinalStatus(null)
    setAgentBuildMessage('Agent Factory 개발 Workflow를 시작합니다...')

    const startedAt=Date.now()
    const workflowThreadId=`agent-${Date.now()}`

    setDevelopmentProgress({
      active:true,
      percent:4,
      stage:'개발 준비',
      detail:'프로젝트 경로, 요구사항, Workflow, 설정 정보를 Agent Factory에 전달할 준비를 하고 있습니다.',
      startedAt,
      elapsedSeconds:0
    })

    let progressTimer=null
    let percent=10

    try{
      setDevelopmentProgress(prev=>({
        ...prev,
        percent:10,
        stage:'Agent Factory 시작',
        detail:'설계 결과와 등록된 Coding Style을 개발 Workflow에 전달했습니다.'
      }))

      /*
       * v5.166: 긴 LangGraph 실행은 Background Job을 유지하고, 시작 전 Backend 버전도 검증합니다.
       * Backend Background Job을 시작한 뒤 짧은 /jobs/{id} 조회로 상태를 받습니다.
       * 브라우저/프록시의 장기 연결이 끊겨도 Backend 작업과 진단 파일 생성은 계속됩니다.
       */
      progressTimer=setInterval(()=>{
        const elapsedSeconds=Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )

        percent=Math.min(
          88,
          percent+Math.max(
            1,
            Math.round((88-percent)*0.055)
          )
        )

        let stage='Agent Factory 실행 중'
        let detail='요구사항을 실제 프로젝트 코드로 변환하는 Agent Factory가 실행되고 있습니다.'

        if(percent>=30){
          stage='코드 생성 / 검증 진행 중'
          detail='파일 생성·수정, Settings 생성, Coding Style 및 필수 산출물 검증을 수행하는 Workflow 응답을 기다리고 있습니다.'
        }

        if(percent>=58){
          stage='테스트 / 자동 복구 진행 중'
          detail='생성 코드의 테스트, 실패 시 디버그·재생성, 환경 구성 및 검증 결과를 기다리고 있습니다.'
        }

        if(percent>=78){
          stage='패키징 / 최종 검토 진행 중'
          detail='Agent Factory의 최종 산출물·테스트·분석 결과가 반환되기를 기다리고 있습니다.'
        }

        setDevelopmentProgress(prev=>({
          ...prev,
          percent,
          stage,
          detail,
          elapsedSeconds
        }))
      },900)

      const workflowJob=await api('/workflow/start-job',{
        method:'POST',
        body:JSON.stringify({
          thread_id:workflowThreadId,
          project_root:projectRoot,
          request,
          target_files:[],
          test_command:'python -m compileall .',
          provider,
          design_bundle:{
            ...(targetWorkflowPreview||{}),
            confirmed_requirements:buildConfirmedRequirementsFromChat(),
            interview_messages:(chat||[]).map(item=>({
              role:item?.role||'',
              content:item?.content||''
            })),
            interview_context:buildRequirementRequestFromCollectedInfo()
          }
        })
      })

      if(!workflowJob?.id){
        throw new Error('Agent Factory Background Job ID를 받지 못했습니다.')
      }
      setActiveWorkflowJobId(workflowJob.id)

      let jobState=workflowJob
      let pollNetworkFailures=0

      while(!['SUCCESS','FAILED','CANCELLED'].includes(jobState?.status)){
        await new Promise(resolve=>setTimeout(resolve,1000))

        try{
          jobState=await api(`/jobs/${workflowJob.id}`)
          pollNetworkFailures=0
        }catch(pollError){
          pollNetworkFailures+=1

          if(pollNetworkFailures<8){
            setDevelopmentProgress(prev=>({
              ...prev,
              detail:`Backend Job 상태 연결을 다시 확인하고 있습니다. 재시도 ${pollNetworkFailures}/7`
            }))
            continue
          }

          throw pollError
        }

        if(jobState?.ok===false && jobState?.error==='Job not found'){
          throw new Error(
            'Agent Factory Job을 Backend에서 찾을 수 없습니다. Backend가 실행 중 재시작되었을 가능성이 있습니다.'
          )
        }

        if(Number.isFinite(Number(jobState?.progress))){
          const backendProgress=Math.max(4,Math.min(93,Number(jobState.progress)||0))
          setDevelopmentProgress(prev=>({
            ...prev,
            percent:Math.max(prev?.percent||0,backendProgress),
            stage:'Agent Factory Background Job 실행 중',
            detail:jobState?.message||prev?.detail||'Agent Factory가 실행 중입니다.'
          }))
        }
      }

      if(jobState?.status==='FAILED'){
        const jobError=new Error(
          jobState?.message||jobState?.result?.message||'Agent Factory Background Job 실행 실패'
        )
        jobError.workflowJob=jobState
        throw jobError
      }

      if(jobState?.status==='CANCELLED'){
        throw new Error('Agent Factory Background Job이 취소되었습니다.')
      }

      const result=jobState?.result||{}

      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      setDevelopmentProgress(prev=>({
        ...prev,
        percent:94,
        stage:'개발 결과 정리',
        detail:'Agent Factory 실행 결과, 생성 파일, 테스트, 디버그 및 사용량 정보를 화면에 반영하고 있습니다.',
        elapsedSeconds:Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )
      }))

      setWorkflow(result)

      const workflowState=result?.state||{}
      const status=workflowState?.status||'STARTED'
      const finalStatus=classifyDevelopmentStatus(workflowState)

      setDevelopmentFinalStatus(finalStatus)

      setAgentBuildMessage(
        finalStatus.kind==='success'
          ? 'Agent 개발 완료'
          : finalStatus.kind==='failure'
            ? 'Agent 개발 실패'
            : finalStatus.kind==='action'
              ? '디버그 조치 필요'
              : finalStatus.kind==='waiting'
                ? '사용자 조치 대기'
                : `개발 Workflow 종료 · 상태: ${status}`
      )

      if(finalStatus.kind==='success'){
        window.alert(
          `Agent 개발이 완료되었습니다.\n\n최종 상태: ${finalStatus.status||status}`
        )
      }else if(finalStatus.kind==='failure'){
        window.alert(
          `Agent 개발에 실패했습니다.\n\n${finalStatus.detail}`
        )
      }else if(finalStatus.kind==='action'){
        window.alert(
          `Agent 개발이 아직 완료되지 않았습니다.\n\n${finalStatus.detail}`
        )
      }

      try{ await loadFiles(projectRoot) }catch(_){}
      try{ await runProjectCodingStyleValidation(projectRoot) }catch(_){}
      try{ await refreshLlmUsage(projectRoot) }catch(_){}

      setDevelopmentProgress(prev=>({
        ...prev,
        active:true,
        percent:100,
        stage:
          finalStatus.kind==='success'
            ? 'Agent 개발 완료'
            : finalStatus.kind==='failure'
              ? 'Agent 개발 실패'
              : finalStatus.kind==='action'
                ? '디버그 조치 필요'
                : finalStatus.kind==='waiting'
                  ? '사용자 조치 대기'
                  : 'Agent Factory 실행 종료',
        detail:finalStatus.detail,
        elapsedSeconds:Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )
      }))

      setScreen('WORKSPACE')
      setWorkspaceTab('RUN')

      setTimeout(()=>{
        setDevelopmentProgress(prev=>({
          ...prev,
          active:false
        }))
      },2500)
    }catch(e){
      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      const transportErrorMessage=(
        e?.network
          ? `Workflow 응답 연결 오류\nAPI: ${e?.url||'-'}`
          : String(e)
      )

      let recoveredDiagnostics=null

      // Workflow 응답 fetch가 끊겼더라도 Backend가 다시 응답할 수 있으면
      // 프로젝트에 이미 생성된 진단 파일을 즉시 복구 조회합니다.
      try{
        recoveredDiagnostics=await api(
          `/workflow/diagnostics?project_root=${encodeURIComponent(projectRoot)}&run_id=${encodeURIComponent(workflowThreadId)}`
        )
      }catch(diagError){
        console.error(
          '실패 진단 자료 재조회 실패',
          diagError
        )
      }

      const diagnosticFiles=recoveredDiagnostics?.files||{}
      const toPath=(key)=>diagnosticFiles?.[key]?.path||''

      const syntheticDiagnostics=recoveredDiagnostics
        ? {
            project_root:recoveredDiagnostics.project_root||projectRoot,
            run_id:recoveredDiagnostics.run_id||workflowThreadId,
            run_started_at:recoveredDiagnostics.run_started_at||'',
            diagnostic_generated_at:recoveredDiagnostics.diagnostic_generated_at||'',
            diagnostics_fresh:recoveredDiagnostics.diagnostics_fresh===true,
            status:recoveredDiagnostics.status||'FAILED',
            failure_stage:recoveredDiagnostics.failure_stage||'network/fetch',
            failure_reason:
              recoveredDiagnostics.failure_reason
              ||transportErrorMessage,
            actual_file_count:recoveredDiagnostics.actual_file_count||0,
            planned_file_count:recoveredDiagnostics.planned_file_count||0,
            failure_report:toPath('failure_report'),
            workflow_state:toPath('workflow_state'),
            requirements_snapshot:toPath('requirements_snapshot'),
            generated_artifacts:toPath('generated_artifacts'),
            debug_patch:toPath('debug_patch'),
            recovery_plan:toPath('recovery_plan'),
            files:diagnosticFiles,
            file_apply:recoveredDiagnostics.file_apply,
            test:recoveredDiagnostics.test,
            debug:recoveredDiagnostics.debug,
            code_plan_validation:recoveredDiagnostics.code_plan_validation||{},
            missing_required_paths:recoveredDiagnostics.missing_required_paths||[]
          }
        : {
            project_root:projectRoot,
            run_id:workflowThreadId,
            run_started_at:new Date(startedAt).toISOString(),
            diagnostic_generated_at:'',
            diagnostics_fresh:false,
            status:'FETCH_FAILED',
            failure_stage:'network/fetch',
            failure_reason:transportErrorMessage,
            actual_file_count:0,
            planned_file_count:0,
            files:{
              failure_report:{
                path:`${projectRoot}\\reports\\failure_report.md`,
                exists:null
              },
              workflow_state:{
                path:`${projectRoot}\\reports\\workflow_state.json`,
                exists:null
              },
              requirements_snapshot:{
                path:`${projectRoot}\\reports\\requirements_snapshot.json`,
                exists:null
              },
              generated_artifacts:{
                path:`${projectRoot}\\reports\\generated_artifacts.json`,
                exists:null
              },
              debug_patch:{
                path:`${projectRoot}\\debug\\debug_patch.json`,
                exists:null
              },
              recovery_plan:{
                path:`${projectRoot}\\debug\\recovery_plan.md`,
                exists:null
              },
              agent_factory_log:{
                path:`${projectRoot}\\logs\\agent_factory.log`,
                exists:null
              },
              workflow_execution_log:{
                path:`${projectRoot}\\logs\\workflow_execution.log`,
                exists:null
              }
            },
            file_apply:{executed:false,count:0},
            test:{executed:false,returncode:null},
            debug:{executed:false,count:0},
            code_plan_validation:{},
            missing_required_paths:[]
          }

      const recoveredStillRunning=(
        recoveredDiagnostics?.status==='RUNNING'
        ||recoveredDiagnostics?.status==='DIAGNOSTICS_STALE'
      )

      const failureStatus={
        kind:recoveredStillRunning?'action':'failure',
        title:recoveredStillRunning
          ? 'Backend 작업 상태를 다시 확인해야 합니다.'
          : 'Agent 개발에 실패했습니다.',
        detail:
          recoveredDiagnostics
            ? (
                recoveredDiagnostics.diagnostics_fresh===false
                  ? (
                      `상태: ${recoveredDiagnostics.status||'DIAGNOSTICS_STALE'}\n`
                      +'현재 실행의 최종 진단 파일이 아직 생성되지 않았습니다. '
                      +'이전 실행 파일을 이번 실패 원인으로 표시하지 않습니다.'
                    )
                  : (
                      `상태: ${recoveredDiagnostics.status||'UNKNOWN'}\n`
                      +`원인: ${recoveredDiagnostics.failure_reason||'진단 원인이 기록되지 않았습니다.'}`
                      +(e?.network
                        ? `\n참고: 화면 연결은 중간에 끊겼지만 Backend 진단 재조회는 성공했습니다.`
                        : '')
                    )
              )
            : (
                `${transportErrorMessage} · Backend에 연결할 수 없어 `
                +'진단 파일 존재 여부는 확인하지 못했습니다.'
              ),
        status:
          recoveredDiagnostics?.status
          ||'FETCH_FAILED'
      }

      setWorkflow({
        state:{
          status:failureStatus.status,
          error:(
            recoveredDiagnostics?.failure_reason
            ||transportErrorMessage
          ),
          patch_result:[],
          test_result:{},
          debug_history:[]
        },
        failure_diagnostics:syntheticDiagnostics
      })

      setDevelopmentFinalStatus(failureStatus)
      setAgentBuildMessage(
        recoveredStillRunning
          ? `개발 상태 재확인 필요: ${failureStatus.status}`
          : `개발 실패: ${failureStatus.status}`
      )

      window.alert(
        (recoveredStillRunning
          ? `Agent 개발의 현재 상태를 다시 확인해야 합니다.\n\n`
          : `Agent 개발에 실패했습니다.\n\n`)
        +`${failureStatus.detail}\n\n`
        +(recoveredStillRunning
          ? '실행 결과 탭에서 현재 실행 ID와 진단 파일 업데이트 시각을 확인하세요.'
          : '실행 결과 탭의 실패 진단 영역에서 로그/진단 파일 경로를 확인하세요.')
      )

      setDevelopmentProgress(prev=>({
        ...prev,
        active:false,
        percent:recoveredStillRunning?Math.max(prev?.percent||0,10):0,
        stage:recoveredStillRunning?'상태 재확인 필요':'개발 실패',
        detail:failureStatus.detail,
        elapsedSeconds:Math.max(
          0,
          Math.floor((Date.now()-startedAt)/1000)
        )
      }))

      setScreen('WORKSPACE')
      setWorkspaceTab('RUN')
    }finally{
      setAgentBuildBusy(false)
    }
  }

  const previewTargetWorkflow=async(requestText)=>{
    const request=(
      requestText
      || workflowReq
      || buildRequirementRequestFromCollectedInfo()
      || ''
    ).trim()

    if(!request){
      setTargetWorkflowError('에이전트 개발 요청 내용을 입력하세요.')
      return
    }

    setTargetWorkflowLoading(true)
    setTargetWorkflowError('')
    setWorkflowProgress({
      active:true,
      percent:5,
      stage:'요구사항 준비',
      detail:'인터뷰에서 확정된 요구사항을 Workflow 설계 입력으로 정리하고 있습니다.',
      startedAt:Date.now()
    })

    let progressTimer=null
    let percent=18

    try{
      setWorkflowProgress(prev=>({
        ...prev,
        percent:18,
        stage:'AI Workflow 설계 요청',
        detail:'요구사항과 프로젝트 정보를 AI 설계 엔진에 전달했습니다.'
      }))

      // Backend의 design_agent_factory는 현재 한 번의 LLM 호출로 전체 설계 Bundle을 만듭니다.
      // 내부 세부 단계를 거짓으로 표시하지 않고, 실제 응답 대기 상태를 점진적으로 보여줍니다.
      progressTimer=setInterval(()=>{
        percent=Math.min(82,percent+Math.max(1,Math.round((82-percent)*0.08)))

        setWorkflowProgress(prev=>({
          ...prev,
          percent,
          stage:'AI 설계 응답 대기',
          detail:
            percent<45
              ? '대상 Agent의 기능·MCP·Architecture·Workflow를 설계하고 있습니다.'
              : percent<68
                ? 'AI 설계 결과를 기다리고 있습니다. 복잡한 요구사항은 시간이 더 걸릴 수 있습니다.'
                : '설계 응답을 기다리는 중입니다. 완료되면 요구사항 반영 검사를 진행합니다.'
        }))
      },650)

      const result=await api('/workflow/preview',{
        method:'POST',
        body:JSON.stringify({
          request,
          project_root:root||newAgentProjectRoot||'',
          provider,
          interview_messages:(chat||[]).map(item=>({
            role:item?.role||'',
            content:item?.content||''
          })),
          confirmed_requirements:buildConfirmedRequirementsFromChat()
        })
      })

      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      setWorkflowProgress(prev=>({
        ...prev,
        percent:90,
        stage:'Workflow 검증',
        detail:'생성된 Workflow의 단계·분기·재시도·실패 처리와 요구사항 반영 여부를 확인하고 있습니다.'
      }))

      if(result?.ok===false){
        throw new Error(result.message||'Workflow 분석 실패')
      }

      // 브라우저가 90% 상태를 실제로 한 번 그릴 수 있도록 다음 frame까지 기다립니다.
      await new Promise(resolve=>
        requestAnimationFrame(()=>
          requestAnimationFrame(resolve)
        )
      )

      setWorkflowReq(request)
      setTargetWorkflowPreview(result)
      setTargetWorkflowQuality(result?.workflow_quality||null)
      setAgentBuildStage('WORKFLOW_READY')
      setAgentBuildMessage('대상 Agent Workflow 설계가 완료되었습니다.')
      setWorkflowView('TARGET')
      setWorkspaceTab('WORKFLOW')

      // Workflow 설계 결과까지 Draft에 보존합니다.
      setTimeout(()=>saveRequirementDraft(),0)

      setWorkflowProgress(prev=>({
        ...prev,
        active:true,
        percent:100,
        stage:'Workflow 설계 완료',
        detail:'대상 Agent Workflow와 요구사항 반영 검사가 완료되었습니다.'
      }))

      setTimeout(()=>{
        setWorkflowProgress(prev=>({
          ...prev,
          active:false
        }))
      },1800)
    }catch(e){
      if(progressTimer){
        clearInterval(progressTimer)
        progressTimer=null
      }

      setTargetWorkflowError(String(e))
      setWorkflowProgress(prev=>({
        ...prev,
        active:false,
        percent:0,
        stage:'Workflow 설계 실패',
        detail:String(e)
      }))
    }finally{
      setTargetWorkflowLoading(false)
    }
  }

  const runCmd=async()=>{
    if(!root || !command.trim()) return

    try{
      const result=await api('/jobs/command',{
        method:'POST',
        body:JSON.stringify({
          command:command.trim(),
          cwd:root
        })
      })

      setTerminal(prev=>
        (prev||'')
        + `\n[명령 작업 시작] ${command.trim()}`
        + (result?.id?`\nJob: ${result.id}`:'')
        + '\n'
      )
    }catch(e){
      setTerminal(prev=>(prev||'')+'\n[명령 실행 실패] '+String(e)+'\n')
    }
  }

  const sendChat=async()=>{
    const message=input.trim()
    if(!message || busy) return
    const requirementsDone=chat.some(item=>
      item?.role==='assistant'
      && String(item?.content||'').includes('요구사항 분석 완료')
    )

    if(requirementsDone && isBuildContinueCommand(message)){
      setInput('')
      setChat(prev=>[
        ...prev,
        {role:'user',content:message},
        {
          role:'assistant',
          content:
            agentBuildStage==='REQUIREMENTS'
              ? '확인했습니다. 요구사항을 기준으로 대상 Agent Workflow 설계를 시작합니다.'
              : agentBuildStage==='WORKFLOW_READY'
                ? 'Workflow 설계가 완료되어 있습니다. 프로젝트 생성 버튼을 눌러 다음 단계로 진행하세요.'
                : agentBuildStage==='PROJECT_CREATED'
                  ? '확인했습니다. Agent Factory 개발 Workflow를 시작합니다.'
                  : '현재 제작 Workflow를 진행하고 있습니다.'
        }
      ])

      if(agentBuildStage==='REQUIREMENTS'){
        await previewTargetWorkflow()
      }else if(agentBuildStage==='PROJECT_CREATED'){
        await startAgentDevelopment()
      }

      return
    }
    setWorkflowReq(prev=>prev?.trim()?prev:message)

    const historyBeforeSend=[...chat]
    const userMessage={role:'user',content:message}

    setChat(prev=>[...prev,userMessage])
    setInput('')
    setBusy(true)

    try{
      const result=await api('/chat/interview',{
        method:'POST',
        body:JSON.stringify({
          message,
          history:historyBeforeSend,
          provider,
          project_root:newAgentProjectRoot||root||''
        })
      })

      const answer=
        result?.answer
        || result?.message
        || '응답을 받지 못했습니다.'

      setChat(prev=>[
        ...prev,
        {role:'assistant',content:answer}
      ])

      // 응답이 누적될 때마다 수집 요구사항 Draft를 갱신합니다.
      setTimeout(()=>{
        buildConfirmedRequirementsFromChat()
        saveRequirementDraft()
      },0)
    }catch(e){
      setChat(prev=>[
        ...prev,
        {
          role:'assistant',
          content:'대화 요청 실패: '+String(e)
        }
      ])
    }finally{
      setBusy(false)
    }
  }

  const sendBuilderAnswer=async()=>{
    if(!input.trim()) return
    setBuilderStarted(true)
    await sendChat()
  }

  const goWorkspace=()=>{
    if(selectedProjectId || newAgentProjectRoot){
      if(newAgentProjectRoot) setRoot(newAgentProjectRoot)
      setScreen('WORKSPACE')
    }
  }

  const pathPreview=(value, fallback)=>value?.trim()?value:`${newAgentProjectRoot||'<프로젝트 경로>'}\\${fallback}`

  const weatherPositionStorageKey='agentstudio.weather.devicePosition.v1'

  const readStoredWeatherPosition=()=>{
    try{
      const raw=localStorage.getItem(weatherPositionStorageKey)
      if(!raw) return null
      const parsed=JSON.parse(raw)
      const latitude=Number(parsed?.latitude)
      const longitude=Number(parsed?.longitude)
      const savedAt=Number(parsed?.savedAt||0)
      if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!savedAt) return null
      if(Date.now()-savedAt>24*60*60*1000) return null
      return {latitude,longitude}
    }catch{
      return null
    }
  }

  const storeWeatherPosition=(position)=>{
    if(!position) return
    try{
      localStorage.setItem(weatherPositionStorageKey,JSON.stringify({
        latitude:Number(position.latitude),
        longitude:Number(position.longitude),
        savedAt:Date.now(),
      }))
    }catch{}
  }

  const getDeviceWeatherPosition=(force=false)=>new Promise((resolve)=>{
    if(!force){
      const cached=readStoredWeatherPosition()
      if(cached){
        resolve(cached)
        return
      }
    }

    if(!navigator.geolocation){
      resolve(null)
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position)=>{
        const value={
          latitude:position.coords.latitude,
          longitude:position.coords.longitude,
        }
        storeWeatherPosition(value)
        resolve(value)
      },
      ()=>resolve(readStoredWeatherPosition()),
      {
        enableHighAccuracy:false,
        timeout:6000,
        maximumAge:15*60*1000,
      }
    )
  })

  const refreshHomeWeather=async(forceRefresh=false)=>{
    const token=++weatherRequestTokenRef.current
    setWeatherBusy(true)
    setWeatherError('')

    try{
      let config={auto_location:false}
      try{
        config=await api('/weather/config')
      }catch{}

      let position=null
      if(config?.auto_location){
        position=await getDeviceWeatherPosition(forceRefresh)
      }

      const query=new URLSearchParams()
      if(position){
        query.set('latitude',String(position.latitude))
        query.set('longitude',String(position.longitude))
      }
      if(forceRefresh){
        query.set('force_refresh','true')
      }

      const suffix=query.toString()?`?${query.toString()}`:''
      const result=await api(`/weather/dashboard${suffix}`)
      if(token!==weatherRequestTokenRef.current) return
      setWeatherDashboard(result)
      if(Array.isArray(result?.errors)&&result.errors.length){
        setWeatherError(result.errors.join(' · '))
      }
    }catch(error){
      if(token!==weatherRequestTokenRef.current) return
      // 기존 날씨가 화면에 있다면 네트워크 오류 때문에 지우지 않습니다.
      setWeatherError(String(error?.message||error))
    }finally{
      if(token===weatherRequestTokenRef.current){
        setWeatherBusy(false)
      }
    }
  }

  useEffect(()=>{
    if(screen==='HOME'){
      refreshHomeWeather(false)
    }
  },[screen])

  const renderWeatherPeriod=(period)=><div className="home-weather-period" key={period.key||period.label}>
    <span className="home-weather-period-icon" aria-hidden="true">{period.icon||'🌡️'}</span>
    <div>
      <strong>{period.label||'-'}</strong>
      <small>{period.condition||'-'}</small>
    </div>
    <b>{period.temperature===null||period.temperature===undefined?'-':`${Math.round(Number(period.temperature))}°`}</b>
    {period.precipitation_probability!==null&&period.precipitation_probability!==undefined&&
      <em>강수 {Math.round(Number(period.precipitation_probability))}%</em>}
  </div>

  const renderHomeWeather=()=>{
    const locations=Array.isArray(weatherDashboard?.locations)?weatherDashboard.locations:[]

    return <section className="home-weather-section">
      <div className="home-weather-head">
        <div>
          <small>TODAY WEATHER</small>
          <strong>오늘의 날씨</strong>
          <span>아침 · 점심 · 저녁 · 밤</span>
        </div>
        <div className="home-weather-actions">
          <button type="button" onClick={()=>refreshHomeWeather(true)} disabled={weatherBusy}>
            {weatherBusy?'불러오는 중...':'↻ 새로고침'}
          </button>
          <button type="button" onClick={()=>location.href='/system'}>지역 설정</button>
        </div>
      </div>

      {weatherBusy&&!locations.length&&<div className="home-weather-empty">현재 지역의 오늘 날씨를 불러오고 있습니다...</div>}

      {!weatherBusy&&!locations.length&&<div className="home-weather-empty">
        <span>📍</span>
        <div>
          <strong>날씨 지역을 확인할 수 없습니다.</strong>
          <small>{weatherError||weatherDashboard?.message||'브라우저 위치 권한을 허용하거나 설정에서 기본 지역을 입력하세요.'}</small>
        </div>
      </div>}

      {locations.length>0&&<div className="home-weather-location-list">
        {locations.map((location,index)=><article className="home-weather-location-card" key={`${location.name}-${index}`}>
          <header>
            <div>
              <span>{location.source==='device'?'📍':'🌐'}</span>
              <div>
                <strong>{location.name||'지역 날씨'}</strong>
                <small>
                  {location.source==='device'?'현재 위치':'설정 지역'} · {location.date||'오늘'}
                  {location.cache?.hit?' · 저장된 데이터':''}
                </small>
              </div>
            </div>
            <div className="home-weather-daily">
              <span>{location.daily?.icon||'🌡️'}</span>
              <strong>{location.daily?.temperature_min===null||location.daily?.temperature_min===undefined?'-':Math.round(Number(location.daily.temperature_min))}° / {location.daily?.temperature_max===null||location.daily?.temperature_max===undefined?'-':Math.round(Number(location.daily.temperature_max))}°</strong>
            </div>
          </header>
          <div className="home-weather-period-grid">
            {(location.periods||[]).map(renderWeatherPeriod)}
          </div>
        </article>)}
      </div>}

      {weatherError&&locations.length>0&&<div className="home-weather-errors">
        <strong>일부 지역 날씨를 가져오지 못했습니다.</strong>
        <span>{weatherError}</span>
      </div>}

      <footer>
        날씨 데이터: {weatherDashboard?.provider||'Open-Meteo'}
        {weatherDashboard?.cache?.all_cached?' · 오늘 저장된 데이터 사용':' · 오늘 데이터 로컬 저장'}
        {' · '}위치 권한은 날씨 조회에만 사용합니다.
      </footer>
    </section>
  }

  const renderHomeScreen=()=> <div className="studio-home">
    <div className="hero-panel">
      <div className="eyebrow">THEANOVA AGENTSTUDIO</div>
      <h1>AI Agent + MCP 프로그램을<br/>대화로 설계하고 코드로 완성합니다.</h1>
      <p>처음부터 모든 설정을 알 필요가 없습니다. AgentStudio가 한 번에 하나씩 질문하고, 요구사항을 정리한 뒤 프로젝트를 생성합니다.</p>
      <div className="hero-actions">
        <button className="hero-primary" onClick={startNewProject}>＋ 신규 에이전트 만들기</button>
        <button className="hero-secondary" onClick={openProjectList}>▣ 기존 프로젝트 불러오기</button>
      </div>
    </div>

    {renderHomeWeather()}

    <div className="home-grid">
      <button className="home-card accent" onClick={startNewProject}>
        <span className="card-icon">＋</span>
        <strong>신규 생성</strong>
        <small>AI와 대화하면서 목적·MCP·기능·실행환경을 한 단계씩 결정합니다.</small>
        <span className="card-link">설계 시작 →</span>
      </button>
      <button className="home-card" onClick={openProjectList}>
        <span className="card-icon">▣</span>
        <strong>불러오기</strong>
        <small>DB 저장 프로젝트를 선택하거나, DB에 없는 기존 프로젝트 폴더를 지정해 분석하고 작업을 이어갑니다.</small>
        <span className="card-link">프로젝트 선택 →</span>
      </button>
      <button className="home-card" onClick={()=>setUsageOpen(true)}>
        <span className="card-icon">?</span>
        <strong>사용 방법</strong>
        <small>프로젝트 생성부터 MCP 연결, 코드 수정, 테스트까지 전체 흐름을 확인합니다.</small>
        <span className="card-link">가이드 보기 →</span>
      </button>
    </div>

    <div className="workflow-strip">
      <div><b>1</b><span>아이디어 설명</span><small>무엇을 만들지 말합니다.</small></div>
      <i>→</i>
      <div><b>2</b><span>AI 인터뷰</span><small>질문은 한 번에 하나씩.</small></div>
      <i>→</i>
      <div><b>3</b><span>프로젝트 생성</span><small>경로·DB·환경을 준비합니다.</small></div>
      <i>→</i>
      <div><b>4</b><span>코딩 & MCP</span><small>수정·실행·검증을 반복합니다.</small></div>
    </div>
  </div>

  const renderBuilderScreen=()=> <div className="builder-shell">
    <aside className="builder-steps">
      <button className="back-link" onClick={()=>setScreen('HOME')}>← 홈으로</button>
      <div className="builder-title">신규 Agent 설계</div>
      {[
        ['01','목적','어떤 Agent를 만들지'],
        ['02','기능','핵심 기능과 사용자 흐름'],
        ['03','MCP / Tool','필요한 외부 도구'],
        ['04','실행 환경','경로와 모델'],
        ['05','확인','프로젝트 생성']
      ].map((s,i)=><div className={`builder-step ${i===0||builderStarted?'on':''}`} key={s[0]}>
        <b>{s[0]}</b><div><strong>{s[1]}</strong><small>{s[2]}</small></div>
      </div>)}
      <div className="builder-tip">
        <strong>질문 방식</strong>
        <span>AgentStudio는 여러 질문을 한꺼번에 하지 않습니다. 답변을 확인한 뒤 다음 질문 하나를 이어갑니다.</span>
      </div>
    </aside>

    <section className="builder-chat">
      <div className="builder-chat-head">
        <div><span className="ai-avatar">AI</span><div><strong>Agent 설계 인터뷰</strong><small>{aiInterviewLabel}</small></div></div>
        <div className="builder-head-actions">
          <button
            type="button"
            className="builder-workflow-button"
            onClick={()=>{
              const request=
                workflowReq
                || buildRequirementRequestFromCollectedInfo()
                || chat.find(x=>x.role==='user')?.content
                || ''

              if(request){
                saveRequirementDraft()
                setRoot(newAgentProjectRoot||root)
                setScreen('WORKSPACE')
                previewTargetWorkflow(request)
              }else{
                setTargetWorkflowError('먼저 만들 Agent의 요구사항을 입력하세요.')
              }
            }}
          >
            ◇ Workflow 보기
          </button>
          <span className="live-dot">● 대화형 수집</span>
        </div>
      </div>
      <div className="builder-messages">
        {chat.map((m,i)=><div key={i} className={`builder-msg ${m.role}`}>
          <span>{m.role==='assistant'?'AI':'나'}</span>
          <div>{m.content}</div>
        </div>)}
        {busy&&<div className="builder-msg assistant"><span>AI</span><div>답변을 분석하고 다음 질문을 준비하고 있습니다...</div></div>}
        <div ref={builderMessagesEndRef} className="builder-messages-end" aria-hidden="true"></div>
      </div>
      <AgentBuildActionBar
        stage={agentBuildStage}
        busy={agentBuildBusy}
        message={agentBuildMessage}
        workflowEnabled={canDesignFromCollectedInfo()}
        onWorkflow={()=>previewTargetWorkflow()}
        onCreateProject={createAgentProjectFromInterview}
        onStartDevelopment={startAgentDevelopment}
        onStop={cancelAgentDevelopment}
      />

      <div className="builder-input">
        <textarea value={input} onChange={e=>setInput(e.target.value)}
          onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendBuilderAnswer()}}}
          placeholder="현재 질문에 답해주세요. Shift+Enter로 줄바꿈"/>
        <button onClick={sendBuilderAnswer} disabled={busy||!input.trim()}>답변 보내기</button>
      </div>
    </section>

    <aside className="builder-summary">
      <div className="summary-head">
        <div><strong>프로젝트 구성</strong><small>생성 전에 언제든 수정할 수 있습니다.</small></div>
      </div>

      <div className="requirement-collection-card">
        <div className="requirement-collection-head">
          <div>
            <strong>요구사항 수집 현황</strong>
            <small>
              대화에서 확인된 항목은 자동 저장됩니다.
            </small>
          </div>
          <span>
            {getRequirementKeywordStatus().filter(x=>x.collected).length}
            /{getRequirementKeywordStatus().length}
          </span>
        </div>

        <div className="requirement-keyword-grid">
          {getRequirementKeywordStatus().map(item=>
            <div
              key={item.id}
              className={`requirement-keyword ${item.collected?'collected':'pending'}`}
            >
              <i>{item.collected?'✓':'○'}</i>
              <span>{item.label}</span>
              <b>{item.collected?'수집 완료':'미수집'}</b>
            </div>
          )}
        </div>

        <div className="requirement-draft-info">
          <span>
            {requirementDraftRestored
              ? '이전 수집 정보 복원됨'
              : requirementDraftSavedAt
                ? '수집 정보 저장됨'
                : '수집 정보 저장 대기'}
          </span>
          {requirementDraftSavedAt&&
            <small>
              {new Date(requirementDraftSavedAt).toLocaleString()}
            </small>
          }
        </div>

        {canDesignFromCollectedInfo()&&
          <button
            type="button"
            className="requirement-direct-workflow-button"
            disabled={targetWorkflowLoading}
            onClick={()=>{
              saveRequirementDraft()
              setRoot(newAgentProjectRoot||root)
              setScreen('WORKSPACE')
              previewTargetWorkflow(
                buildRequirementRequestFromCollectedInfo()
              )
            }}
          >
            {targetWorkflowPreview
              ? '◇ 저장된 요구사항으로 Workflow 다시 설계'
              : '◇ 수집된 요구사항으로 바로 Workflow 설계'}
          </button>
        }

        <details className="requirement-collected-details">
          <summary>수집된 내용 보기</summary>
          <div>
            {(chat||[])
              .filter(item=>item?.role==='user')
              .map((item,index)=>
                <p key={index}>{item.content}</p>
              )}
            {!(chat||[]).some(item=>item?.role==='user')&&
              <p>아직 사용자 답변이 없습니다.</p>
            }
          </div>
        </details>
      </div>
      <label className="ux-field"><span>에이전트 이름</span><input value={newAgentName} onChange={e=>setNewAgentName(e.target.value)} placeholder="예: YouTube MCP Agent"/></label>
      <label className="ux-field required"><span>프로젝트 경로</span>
          <div className="path-input-row">
            <input value={newAgentProjectRoot} onChange={e=>setNewAgentProjectRoot(e.target.value)} placeholder="예: F:\\Source\\repos\\Theanova\\AI\\MyAgent"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentProjectRoot,newAgentProjectRoot,'프로젝트 경로')}>경로 찾기</button>
          </div>
        </label>

      <button className="path-toggle" onClick={()=>setShowPathSettings(v=>!v)}>
        <span>고급 경로 설정</span><b>{showPathSettings?'−':'＋'}</b>
      </button>
      {showPathSettings&&<div className="path-settings">
        <label className="ux-field"><span>Cache</span>
          <div className="path-input-row">
            <input value={newAgentCachePath} onChange={e=>setNewAgentCachePath(e.target.value)} placeholder="비우면 프로젝트\\cache"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentCachePath,newAgentCachePath,'Cache 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>Temp</span>
          <div className="path-input-row">
            <input value={newAgentTempPath} onChange={e=>setNewAgentTempPath(e.target.value)} placeholder="비우면 프로젝트\\temp"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentTempPath,newAgentTempPath,'Temp 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>Output</span>
          <div className="path-input-row">
            <input value={newAgentOutputPath} onChange={e=>setNewAgentOutputPath(e.target.value)} placeholder="비우면 프로젝트\\output"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentOutputPath,newAgentOutputPath,'Output 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>가상환경</span>
          <div className="path-input-row">
            <input value={newAgentVenvPath} onChange={e=>setNewAgentVenvPath(e.target.value)} placeholder="비우면 프로젝트\\venv"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentVenvPath,newAgentVenvPath,'가상환경 경로')}>경로 찾기</button>
          </div>
        </label>
        <label className="ux-field"><span>공통 모델</span>
          <div className="path-input-row">
            <input value={newAgentModelsPath} onChange={e=>setNewAgentModelsPath(e.target.value)} placeholder="비우면 프로젝트\\models"/>
            <button type="button" className="path-find-button" onClick={()=>chooseAgentFolder(setNewAgentModelsPath,newAgentModelsPath,'공용 모델 경로')}>경로 찾기</button>
          </div>
        </label>
      </div>}

      {loadedProjectAnalysis&&<div className="imported-project-analysis">
        <div className="imported-analysis-head">
          <strong>기존 프로젝트 분석 정보</strong>
          <span>DB 저장됨</span>
        </div>

        {loadedProjectAnalysis.summary&&<div className="analysis-info-block">
          <b>프로젝트 요약</b>
          <p>{loadedProjectAnalysis.summary}</p>
        </div>}

        {loadedProjectAnalysis.tech_stack?.length>0&&<div className="analysis-info-block">
          <b>기술 스택</b>
          <div className="analysis-tags">
            {loadedProjectAnalysis.tech_stack.map((x,i)=><span key={i}>{typeof x==='string'?x:JSON.stringify(x)}</span>)}
          </div>
        </div>}

        {loadedProjectAnalysis.entry_points?.length>0&&<div className="analysis-info-block">
          <b>실행 진입점</b>
          {loadedProjectAnalysis.entry_points.slice(0,8).map((x,i)=><code key={i}>{typeof x==='string'?x:JSON.stringify(x)}</code>)}
        </div>}

        {loadedProjectAnalysis.mcp_tools?.length>0&&<div className="analysis-info-block">
          <b>MCP / Tool</b>
          {loadedProjectAnalysis.mcp_tools.slice(0,10).map((x,i)=><code key={i}>{typeof x==='string'?x:JSON.stringify(x)}</code>)}
        </div>}

        {loadedProjectAnalysis.major_files?.length>0&&<details className="analysis-files">
          <summary>주요 파일 {loadedProjectAnalysis.major_files.length}개</summary>
          <div>
            {loadedProjectAnalysis.major_files.slice(0,30).map((x,i)=><code key={i}>{typeof x==='string'?x:JSON.stringify(x)}</code>)}
          </div>
        </details>}
      </div>}

      <div className="path-preview">
        <strong>생성될 경로</strong>
        {!newAgentProjectRoot.trim()&&<small className="path-preview-hint">프로젝트 경로를 입력하거나 선택하면 실제 생성 경로가 표시됩니다.</small>}
        <div><span>Cache</span><code>{pathPreview(newAgentCachePath,'cache')}</code></div>
        <div><span>Temp</span><code>{pathPreview(newAgentTempPath,'temp')}</code></div>
        <div><span>Output</span><code>{pathPreview(newAgentOutputPath,'output')}</code></div>
        <div><span>Venv</span><code>{pathPreview(newAgentVenvPath,'venv')}</code></div>
        <div><span>Models</span><code>{pathPreview(newAgentModelsPath,'models')}</code></div>
      </div>

      {selectedProjectId
        ? <button className="create-project-cta" onClick={()=>setScreen('WORKSPACE')}>
            분석된 프로젝트 작업공간 열기
          </button>
        : <button className="create-project-cta" onClick={createNewAgentProject}
            disabled={!newAgentName.trim()||!newAgentProjectRoot.trim()}>
            프로젝트 생성
          </button>}
      <small className="cta-note">
        {selectedProjectId
          ? `Project #${selectedProjectId} · 분석 정보와 프로젝트 정보가 PostgreSQL에 저장되어 있습니다.`
          : 'FastAPI를 통해 폴더를 만들고 PostgreSQL에 프로젝트 정보를 저장합니다.'}
      </small>
      {newAgentCreateResult&&<div className={newAgentCreateResult.ok?'ux-result good':'ux-result bad'}>{newAgentCreateResult.message}</div>}
    </aside>
  </div>


  const activeTerminal =
    terminalSessions.find(t=>t.id===activeTerminalId)
    || terminalSessions[0]

  const updateTerminal=(id,patch)=>{
    setTerminalSessions(prev=>prev.map(t=>t.id===id?{...t,...patch}:t))
  }

  const waitForTerminalContainer=async(id,attempts=20)=>{
    for(let i=0;i<attempts;i+=1){
      if(xtermContainersRef.current[id]){
        return xtermContainersRef.current[id]
      }
      await new Promise(resolve=>setTimeout(resolve,25))
    }
    return null
  }

  const addTerminal=async()=>{
    const project=currentProject
    const projectRoot=
      project?.project_root
      || project?.root_path
      || root
      || ''

    if(!projectRoot){
      setTerminal(prev=>(prev||'')+'\n[터미널 생성 실패] 먼저 프로젝트를 선택하세요.\n')
      return null
    }

    const n=terminalSessions.length+1
    const id=`terminal-${Date.now()}-${n}`
    const projectId=project?.id||selectedProjectId||null
    const projectName=project?.name||currentProjectName||'프로젝트'

    const next={
      id,
      name:`Terminal ${n}`,
      projectId,
      projectName,
      root:projectRoot,
      cwd:projectRoot,
      command:'',
      output:'',
      busy:false,
      processState:'starting',
      exitCode:null,
    }

    setTerminalSessions(prev=>[...prev,next])
    setActiveTerminalProjectId(projectId)
    setActiveTerminalId(id)
    setFocusOwnerSafe('terminal')

    // React가 새 terminal DOM을 실제로 mount한 뒤 xterm을 먼저 준비합니다.
    // WebSocket history/ready 메시지가 xterm 생성보다 먼저 도착하면 prompt가
    // 유실되어 빈 터미널처럼 보일 수 있으므로 연결 순서를 보장합니다.
    const container=await waitForTerminalContainer(id)
    if(!container){
      setTerminalSessions(prev=>prev.map(t=>
        t.id===id
          ? {...t,processState:'exited',exitCode:1}
          : t
      ))
      setTerminalErrors(prev=>({
        ...prev,
        [id]:{
          stage:'terminal_create',
          message:'새 터미널 화면을 초기화하지 못했습니다.',
          root:projectRoot,
          sessionId:id,
          time:new Date().toLocaleString()
        }
      }))
      return null
    }

    await ensureXtermInstance(id)

    const ws=await connectProjectTerminal(
      {
        id:projectId,
        name:projectName,
        project_root:projectRoot
      },
      id
    )

    if(!ws){
      return null
    }

    setTimeout(()=>{
      const term=xtermInstancesRef.current[id]
      fitTerminalViewport(id)
      try{
        term?.refresh(0,Math.max(0,(term?.rows||1)-1))
        term?.scrollToBottom()
        term?.focus()
      }catch{}
    },80)

    return id
  }

  const runPowerShellTextInTerminal=async(scriptText,{sourceLabel='PowerShell'}={})=>{
    const script=String(scriptText||'').replace(/\r\n|\r/g,'\n')
    if(!script.trim()){
      window.alert('실행할 PowerShell 코드가 없습니다.')
      return false
    }

    let targetId=activeTerminalId
    let target=terminalSessions.find(t=>t.id===targetId)

    if(!target||target.processState==='exited'){
      targetId=await addTerminal()
      if(!targetId) return false
      target={
        id:targetId,
        projectId:currentProject?.id||selectedProjectId||null,
        projectName:currentProject?.name||currentProjectName||'프로젝트',
        root:currentProject?.project_root||currentProject?.root_path||root||'',
        cwd:currentProject?.project_root||currentProject?.root_path||root||''
      }
    }

    await waitForTerminalContainer(targetId)
    const term=await ensureXtermInstance(targetId)
    if(!term) return false

    let ws=terminalSocketsRef.current[targetId]
    if(!ws||ws.readyState!==WebSocket.OPEN){
      const projectRoot=target.root||root||''
      ws=await connectProjectTerminal({
        id:target.projectId||selectedProjectId||null,
        name:target.projectName||currentProjectName||'프로젝트',
        project_root:projectRoot
      },targetId)
    }

    if(!ws) return false
    if(ws.readyState===WebSocket.CONNECTING){
      await new Promise(resolve=>{
        ws.addEventListener('open',resolve,{once:true})
        setTimeout(resolve,2500)
      })
    }
    if(ws.readyState!==WebSocket.OPEN){
      window.alert('PowerShell 터미널 연결이 열리지 않았습니다.')
      return false
    }

    // Show exactly what will run in the active terminal, then execute the
    // whole block as one logical PowerShell command.  Backend v5.200+ wraps
    // multi-line commands in a UTF-8 ScriptBlock, preserving backticks,
    // Korean text, variables, and Set-Location state.
    const setter=xtermSetCommandLineRef.current[targetId]
    if(typeof setter==='function'){
      setter(script,script.length)
    }else{
      term.write(script.replace(/\n/g,'\r\n'))
    }

    term.write('\r\n')
    xtermCommandBuffersRef.current[targetId]=''
    xtermCursorIndexRef.current[targetId]=0

    const history=xtermCommandHistoryRef.current[targetId]||[]
    history.push(script)
    xtermCommandHistoryRef.current[targetId]=history
    xtermHistoryIndexRef.current[targetId]=history.length

    terminalCommandBusyRef.current[targetId]=true
    setTerminalSessions(prev=>prev.map(t=>t.id===targetId?{...t,busy:true}:t))
    ws.send(serializeTerminalClientMessage({type:'command',data:script}))
    setActiveTerminalId(targetId)
    setFocusOwnerSafe('terminal')

    requestAnimationFrame(()=>{
      try{
        term.scrollToBottom()
        term.focus()
      }catch{}
    })

    setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] 터미널 실행 요청을 전송했습니다.\n`)
    return true
  }

  const runCurrentPowerShellFile=async({selectionOnly=false}={})=>{
    if(!selected?.toLowerCase?.().endsWith('.ps1')) return

    let script=code
    let label=`PowerShell 전체 실행 · ${selected}`

    if(selectionOnly){
      const editor=editorInstanceRef.current
      const selection=editor?.getSelection?.()
      const model=editor?.getModel?.()
      const selectedText=(selection&&model)
        ? model.getValueInRange(selection)
        : ''

      if(!selectedText.trim()){
        window.alert('선택된 PowerShell 코드가 없습니다.')
        return
      }
      script=selectedText
      label=`PowerShell 선택 실행 · ${selected}`
    }

    await runPowerShellTextInTerminal(script,{sourceLabel:label})
  }

  const stopPythonExecution=async()=>{
    const state=pythonExecutionState||{}
    if(!state.busy||!state.root||!state.sessionId) return null
    pythonStopRequestedRef.current=true
    try{
      if(state.kind==='sql'){
        sqlStopRequestedRef.current=true
        const result=await api('/sql/cancel',{
          method:'POST',
          body:JSON.stringify({root:state.root,connection_id:sqlProfile.connection_id||''})
        })
        const term=xtermInstancesRef.current[state.sessionId]
        term?.write?.('\r\n\x1b[33m[실행 정지] Notebook SQL 실행 중지 요청을 보냈습니다.\x1b[0m\r\n')
        return result
      }
      const result=await api('/python/stop',{
        method:'POST',
        body:JSON.stringify({root:state.root,session_id:state.sessionId})
      })
      const term=xtermInstancesRef.current[state.sessionId]
      term?.write?.('\r\n\x1b[33m[실행 정지] Python/Notebook 실행 중지 요청을 보냈습니다. 다음 실행은 새 Python 세션에서 시작됩니다.\x1b[0m\r\n')
      return result
    }catch(e){
      console.error('Notebook/Python 실행 중지 실패',e)
      return null
    }
  }

  const runCurrentPythonFile=async({selectionOnly=false}={})=>{
    const filePath=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'')
    if(!filePath.toLowerCase().endsWith('.py')) return

    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot){
      window.alert('Python 파일을 실행할 프로젝트 경로가 없습니다.')
      return
    }

    let pythonCode=code
    let mode='full'
    let sourceLabel=`Python 전체 실행 · ${filePath}`

    if(selectionOnly){
      const editor=editorInstanceRef.current
      const selection=editor?.getSelection?.()
      const model=editor?.getModel?.()
      const selectedText=(selection&&model)
        ? model.getValueInRange(selection)
        : ''

      if(!selectedText.trim()){
        window.alert('선택된 Python 코드가 없습니다.')
        return
      }

      pythonCode=selectedText
      mode='selection'
      sourceLabel=`Python 선택 실행 · ${filePath}`
    }

    if(!String(pythonCode||'').trim()){
      window.alert('실행할 Python 코드가 없습니다.')
      return
    }

    let targetId=activeTerminalId
    let target=terminalSessions.find(t=>t.id===targetId)
    if(!target||target.processState==='exited'){
      targetId=await addTerminal()
      if(!targetId) return
    }

    await waitForTerminalContainer(targetId)
    const term=await ensureXtermInstance(targetId)
    if(!term){
      window.alert('Python 실행 결과를 표시할 터미널을 준비하지 못했습니다.')
      return
    }

    const terminalSessionId=targetId||'python-default'
    pythonStopRequestedRef.current=false
    setPythonExecutionState({busy:true,root:workspaceRoot,sessionId:terminalSessionId,label:sourceLabel})
    const displayCode=selectionOnly
      ? String(pythonCode).replace(/\r\n|\r/g,'\n')
      : ''

    try{
      term.write(`\r\n\x1b[36m[${sourceLabel}]\x1b[0m\r\n`)
      if(displayCode){
        term.write(displayCode.replace(/\n/g,'\r\n'))
        term.write('\r\n')
      }
      term.write('\x1b[90m실행 중...\x1b[0m\r\n')
      term.scrollToBottom()

      const result=await api('/python/execute',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:filePath,
          code:pythonCode,
          mode,
          session_id:terminalSessionId,
        })
      })

      const stdout=String(result?.stdout||'')
      const stderr=String(result?.stderr||'')
      const trace=String(result?.traceback||'')

      if(stdout){
        term.write(stdout.replace(/\r\n|\r|\n/g,'\r\n'))
        if(!stdout.endsWith('\n')&&!stdout.endsWith('\r')) term.write('\r\n')
      }
      if(stderr){
        term.write('\x1b[33m'+stderr.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!stderr.endsWith('\n')&&!stderr.endsWith('\r')) term.write('\r\n')
      }
      if(result?.cancelled){
        term.write('\x1b[33m[실행 취소] 사용자가 Python 실행을 중지했습니다.\x1b[0m\r\n')
      }else if(!result?.ok){
        const errorText=trace||`${result?.error_type||'PythonError'}: ${result?.error_message||'실행 실패'}`
        term.write('\x1b[31m'+errorText.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!errorText.endsWith('\n')&&!errorText.endsWith('\r')) term.write('\r\n')

        const dependency=result?.dependency_diagnostic
        if(dependency?.code==='PYTHON_MODULE_NOT_FOUND'){
          const lines=[
            '',
            `[패키지 설치 필요] ${dependency.message||''}`,
            `설치 명령: ${dependency.install_command||''}`,
          ]
          if(dependency.requirements_command){
            lines.push(`requirements.txt 전체 설치: ${dependency.requirements_command}`)
          }
          lines.push('※ 에이전트 스튜디오는 프로젝트 가상환경을 자동 변경하지 않습니다.')
          term.write('\x1b[33m'+lines.join('\r\n')+'\x1b[0m\r\n')
        }
      }else if(!stdout&&!stderr){
        term.write('\x1b[90m(출력 없음)\x1b[0m\r\n')
      }

      term.write(`\x1b[90mPython: ${String(result?.interpreter||'').replace(/\x1b/g,'')} · 세션: ${selectionOnly?'유지':'초기화 후 유지'}\x1b[0m\r\n`)
      term.scrollToBottom()
      setActiveTerminalId(targetId)
      setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] ${result?.ok?'완료':'실패'}\n`)
    }catch(e){
      if(pythonStopRequestedRef.current){
        term.write('\x1b[33m[실행 취소] 사용자가 Python 실행을 중지했습니다.\x1b[0m\r\n')
      }else{
        const message=`Python 실행 실패: ${e}`
        term.write('\x1b[31m'+message.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m\r\n')
        term.scrollToBottom()
        window.alert(message)
      }
    }finally{
      setPythonExecutionState(prev=>prev.sessionId===terminalSessionId?{busy:false,root:'',sessionId:'',label:''}:prev)
      pythonStopRequestedRef.current=false
    }
  }


  const executeNotebookPythonCode=async({pythonCode,filePath,cellIndex=0,mode='selection',selectionOnly=false}={})=>{
    const normalizedPath=normalizeProjectRelativePath(filePath||selectedEditorFileRef.current||selected||'')
    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot){
      window.alert('Notebook을 실행할 프로젝트 경로가 없습니다.')
      return null
    }
    if(!String(pythonCode||'').trim()){
      window.alert('실행할 Notebook 코드가 없습니다.')
      return null
    }

    const sqlMode=looksLikeNotebookSqlCode(pythonCode)
    const executableCode=sqlMode?normalizeNotebookSqlCode(pythonCode):String(pythonCode||'')

    let targetId=activeTerminalId
    let target=terminalSessions.find(t=>t.id===targetId)
    if(!target||target.processState==='exited'){
      targetId=await addTerminal()
      if(!targetId) return null
    }

    await waitForTerminalContainer(targetId)
    const term=await ensureXtermInstance(targetId)
    if(!term){
      window.alert('Notebook 실행 결과를 표시할 터미널을 준비하지 못했습니다.')
      return null
    }

    const terminalSessionId=targetId||'python-default'
    const sourceLabel=`Notebook ${sqlMode?'SQL':(selectionOnly?'선택':'셀')} 실행 · ${normalizedPath} · Cell ${Number(cellIndex)+1}`
    pythonStopRequestedRef.current=false
    setPythonExecutionState({busy:true,root:workspaceRoot,sessionId:terminalSessionId,label:sourceLabel,kind:sqlMode?'sql':'python'})

    try{
      term.write(`\r\n\x1b[36m[${sourceLabel}]\x1b[0m\r\n`)
      if(selectionOnly||sqlMode){
        term.write(String(executableCode).replace(/\r\n|\r|\n/g,'\r\n'))
        term.write('\r\n')
      }
      term.write('\x1b[90m실행 중...\x1b[0m\r\n')
      term.scrollToBottom()

      if(sqlMode){
        if(!sqlConnectionStatus?.connected){
          const message='Notebook SQL 셀을 실행하려면 우측 DB 연결 영역에서 데이터베이스를 먼저 연결해야 합니다.'
          term.write('\x1b[31m'+message+'\x1b[0m\r\n')
          return {ok:false,stdout:'',stderr:'',error_type:'DatabaseNotConnected',error_message:message,traceback:''}
        }
        try{
          const sqlResult=await api('/sql/execute',{
            method:'POST',
            body:JSON.stringify({root:workspaceRoot,sql:executableCode,max_rows:1000})
          })
          const stdout=formatNotebookSqlResult(sqlResult)
          setSqlQueryResult(sqlResult)
          setSqlResultTab(sqlResult?.columns?.length?'DATA':'MESSAGES')
          setSqlMessages(prev=>[{
            type:'success',
            text:`Notebook SQL 셀 실행 완료 · ${sqlResult?.message||''} · ${sqlResult?.elapsed_ms||0}ms`,
            time:new Date().toLocaleTimeString()
          },...prev].slice(0,100))
          term.write('\x1b[32m'+stdout.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
          term.write(`\x1b[90mDB: ${String(sqlConnectionStatus?.profile?.name||sqlProfile?.name||sqlConnectionStatus?.db_type||sqlProfile?.db_type||'연결된 DB')} · Notebook SQL 자동 감지\x1b[0m\r\n`)
          term.scrollToBottom()
          setActiveTerminalId(targetId)
          setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] 완료\n`)
          return {ok:true,stdout,stderr:'',traceback:'',error_type:'',error_message:'',sql_result:sqlResult,execution_kind:'sql'}
        }catch(e){
          if(sqlStopRequestedRef.current){
            const message='사용자가 Notebook SQL 실행을 중지했습니다.'
            term.write('\x1b[33m[실행 취소] '+message+'\x1b[0m\r\n')
            return {ok:false,cancelled:true,error_type:'ExecutionCancelled',error_message:message,stdout:'',stderr:'',traceback:''}
          }
          const message=`Notebook SQL 실행 실패: ${e}`
          term.write('\x1b[31m'+message.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m\r\n')
          term.scrollToBottom()
          return {ok:false,stdout:'',stderr:'',error_type:'SqlExecutionError',error_message:String(e),traceback:message,execution_kind:'sql'}
        }
      }

      const result=await api('/python/execute',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:normalizedPath,
          code:executableCode,
          mode:mode==='full'?'full':'selection',
          session_id:terminalSessionId,
          capture_last_expression:true,
          notebook_mode:true,
          cell_index:Number(cellIndex),
        })
      })

      const stdout=String(result?.stdout||'')
      const stderr=String(result?.stderr||'')
      const trace=String(result?.traceback||'')
      if(stdout){
        term.write(stdout.replace(/\r\n|\r|\n/g,'\r\n'))
        if(!stdout.endsWith('\n')&&!stdout.endsWith('\r')) term.write('\r\n')
      }
      if(stderr){
        term.write('\x1b[33m'+stderr.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!stderr.endsWith('\n')&&!stderr.endsWith('\r')) term.write('\r\n')
      }
      if(!result?.ok){
        const errorText=trace||`${result?.error_type||'PythonError'}: ${result?.error_message||'실행 실패'}`
        term.write('\x1b[31m'+errorText.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m')
        if(!errorText.endsWith('\n')&&!errorText.endsWith('\r')) term.write('\r\n')

        const dependency=result?.dependency_diagnostic
        if(dependency?.code==='PYTHON_MODULE_NOT_FOUND'){
          const lines=[
            '',
            `[패키지 설치 필요] ${dependency.message||''}`,
            `설치 명령: ${dependency.install_command||''}`,
          ]
          if(dependency.requirements_command) lines.push(`requirements.txt 전체 설치: ${dependency.requirements_command}`)
          lines.push('※ 에이전트 스튜디오는 프로젝트 가상환경을 자동 변경하지 않습니다.')
          term.write('\x1b[33m'+lines.join('\r\n')+'\x1b[0m\r\n')
        }
      }else if(!stdout&&!stderr){
        term.write('\x1b[90m(출력 없음)\x1b[0m\r\n')
      }

      term.write(`\x1b[90mPython: ${String(result?.interpreter||'').replace(/\x1b/g,'')} · Notebook 세션: 유지\x1b[0m\r\n`)
      term.scrollToBottom()
      setActiveTerminalId(targetId)
      setTerminal(prev=>(prev||'')+`\n[${sourceLabel}] ${result?.ok?'완료':'실패'}\n`)
      return result
    }catch(e){
      if(pythonStopRequestedRef.current){
        term.write('\x1b[33m[실행 취소] 사용자가 Notebook 실행을 중지했습니다.\x1b[0m\r\n')
        return {ok:false,cancelled:true,error_type:'ExecutionCancelled',error_message:'사용자가 Notebook 실행을 중지했습니다.',stdout:'',stderr:'',traceback:''}
      }
      const message=`Notebook Python 실행 실패: ${e}`
      term.write('\x1b[31m'+message.replace(/\r\n|\r|\n/g,'\r\n')+'\x1b[0m\r\n')
      term.scrollToBottom()
      throw e
    }finally{
      setPythonExecutionState(prev=>prev.sessionId===terminalSessionId?{busy:false,root:'',sessionId:'',label:'',kind:''}:prev)
      pythonStopRequestedRef.current=false
    }
  }

  const stopCurrentCmdFile=async()=>{
    const executionId=cmdExecution?.executionId
    if(!executionId||!cmdExecution?.busy) return
    try{
      await api(`/files/execute-cmd/${encodeURIComponent(executionId)}/stop`,{method:'POST'})
      setTerminal(prev=>(prev||'')+'\n[CMD 실행 정지] 사용자가 실행을 중지했습니다.\n')
    }catch(e){
      window.alert(`CMD 실행 중지 실패: ${e}`)
    }finally{
      setCmdExecution({busy:false,executionId:'',path:'',pid:null})
    }
  }

  const runCurrentCmdFile=async()=>{
    const filePath=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'')
    if(!filePath.toLowerCase().endsWith('.cmd')||cmdExecution?.busy) return

    const workspaceRoot=activeWorkspaceRoot
    if(!workspaceRoot){
      window.alert('CMD 파일을 실행할 프로젝트 경로가 없습니다.')
      return
    }

    try{
      const result=await api('/files/execute-cmd',{
        method:'POST',
        body:JSON.stringify({
          root:workspaceRoot,
          relative_path:filePath
        })
      })
      const executionId=String(result?.execution_id||'')
      setCmdExecution({busy:!!executionId,executionId,path:result?.path||filePath,pid:result?.pid||null})
      setTerminal(prev=>(prev||'')+`\n[CMD 실행] ${result?.path||filePath}${result?.pid?` · PID ${result.pid}`:''}\n`)
      if(executionId){
        const poll=async()=>{
          try{
            const state=await api(`/files/execute-cmd/${encodeURIComponent(executionId)}/status`)
            if(state?.running){
              setTimeout(poll,800)
            }else{
              setCmdExecution(prev=>prev.executionId===executionId?{busy:false,executionId:'',path:'',pid:null}:prev)
            }
          }catch{
            setCmdExecution(prev=>prev.executionId===executionId?{busy:false,executionId:'',path:'',pid:null}:prev)
          }
        }
        setTimeout(poll,800)
      }
    }catch(e){
      setCmdExecution({busy:false,executionId:'',path:'',pid:null})
      window.alert(`CMD 실행 실패: ${e}`)
    }
  }

  useEffect(()=>{
    const onEditorRunShortcut=(event)=>{
      if(workspaceTab!=='CODE') return

      const path=normalizeProjectRelativePath(selectedEditorFileRef.current||selected||'').toLowerCase()

      if(event.key==='F5' && (path.endsWith('.ps1')||path.endsWith('.py')||path.endsWith('.cmd')||path.endsWith('.sql')||path.endsWith('.ipynb'))){
        event.preventDefault()
        event.stopPropagation()
        if(path.endsWith('.ps1')){
          runCurrentPowerShellFile({selectionOnly:false})
        }else if(path.endsWith('.py')){
          runCurrentPythonFile({selectionOnly:false})
        }else if(path.endsWith('.sql')){
          runSqlEditor({selectionOnly:false})
        }else if(path.endsWith('.ipynb')){
          notebookEditorControllerRef.current?.runAll?.()
        }else{
          runCurrentCmdFile()
        }
        return
      }

      if(event.key==='F8' && (path.endsWith('.ps1')||path.endsWith('.py')||path.endsWith('.sql')||path.endsWith('.ipynb'))){
        event.preventDefault()
        event.stopPropagation()
        if(path.endsWith('.sql')){
          runSqlEditor({selectionOnly:true})
        }else if(path.endsWith('.py')){
          runCurrentPythonFile({selectionOnly:true})
        }else if(path.endsWith('.ipynb')){
          notebookEditorControllerRef.current?.runSelection?.()
        }else{
          runCurrentPowerShellFile({selectionOnly:true})
        }
      }
    }

    window.addEventListener('keydown',onEditorRunShortcut,true)
    return()=>window.removeEventListener('keydown',onEditorRunShortcut,true)
  },[workspaceTab,selected,code,activeWorkspaceRoot,sqlQueryBusy,sqlConnectionStatus?.connected])

  const removeTerminal=(id)=>{
    if(terminalSessions.length===1) return

    terminalIntentionalCloseRef.current[id]=true

    const ws=terminalSocketsRef.current[id]
    try{
      if(ws){
        ws.close(1000,'user_closed_terminal')
      }
    }catch{}
    delete terminalSocketsRef.current[id]

    try{
      xtermDisposablesRef.current[id]?.dispose?.()
    }catch{}
    delete xtermDisposablesRef.current[id]

    try{
      xtermInstancesRef.current[id]?.dispose?.()
    }catch{}
    delete xtermInstancesRef.current[id]
    delete xtermContainersRef.current[id]
    delete xtermFitAddonsRef.current[id]
    delete xtermCommandBuffersRef.current[id]
    delete xtermCommandHistoryRef.current[id]
    delete xtermHistoryIndexRef.current[id]
    delete xtermCursorIndexRef.current[id]
    delete xtermPromptRef.current[id]
    delete xtermOutputParseBufferRef.current[id]
    delete xtermRequiredColsRef.current[id]
    delete xtermSetCommandLineRef.current[id]
    delete xtermKeyboardSelectionRef.current[id]
    delete terminalCwdRef.current[id]
    delete terminalRootRef.current[id]
    closeTerminalCompletion(id)

    setTerminalErrors(prev=>({
      ...prev,
      [id]:null
    }))

    setTerminalSessions(prev=>{
      const index=prev.findIndex(t=>t.id===id)
      const next=prev.filter(t=>t.id!==id)

      if(activeTerminalId===id){
        const nextActive=
          next[Math.min(index,next.length-1)]
          || next[next.length-1]
          || null

        setActiveTerminalId(nextActive?.id||'')
        setActiveTerminalProjectId(nextActive?.projectId||null)
      }

      return next
    })
  }

  const startRenameTerminal=(terminal)=>{
    setTerminalNameEditId(terminal.id)
    setTerminalNameDraft(terminal.name)
  }

  const saveTerminalName=(id)=>{
    const name=(terminalNameDraft||'').trim()
    if(name){
      updateTerminal(id,{name})
    }
    setTerminalNameEditId(null)
    setTerminalNameDraft('')
  }

  const runTerminalSession=async(id)=>{
    await sendTerminalInput(id)
  }


  const askCodeEditorLLM=async()=>{
    const prompt=codeEditPrompt.trim()
    if(!prompt) return

    const projectMode=codeEditScope==='PROJECT'

    if(!root){
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:'먼저 작업할 프로젝트를 선택해주세요.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    if(!projectMode&&!selected){
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:'파일 단위 작업에서는 먼저 수정할 파일을 선택해주세요.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    if(!projectMode&&editorLoadErrors[selected]){
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:'현재 파일은 불러오기에 실패한 상태입니다. 원본 보호를 위해 LLM 코드 수정도 차단했습니다. 파일을 다시 불러온 뒤 시도해주세요.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    if(!projectMode&&isBinaryPreviewFile(selected)){
      const presentation=isPresentationFile(selected)
      setCodeEditChat(prev=>[
        ...prev,
        {role:'user',content:prompt},
        {
          role:'assistant',
          content:presentation
            ? 'PPT/PPTX는 바이너리 문서이므로 파일 단위 코드 수정 대상이 아닙니다. 원본을 보존한 채 PDF 미리보기로 열립니다.'
            : 'PDF는 바이너리 문서이므로 파일 단위 코드 수정 대상이 아닙니다. PDF는 미리보기 전용으로 열립니다.'
        }
      ])
      setCodeEditPrompt('')
      return
    }

    const targetPath=selected
    const currentCode=
      targetPath
        ? (editorFileContents[targetPath] ?? code ?? '')
        : ''

    setCodeEditChat(prev=>[
      ...prev,
      {
        role:'user',
        content:
          `${projectMode?'[프로젝트]':'[파일]'} ${prompt}`
      }
    ])
    scrollCodeEditChatToBottom('smooth')

    setCodeEditPrompt('')
    setCodeEditBusy(true)
    setCodeEditProposal(null)
    setCodeDiffReview(null)

    try{
      if(projectMode){
        const result=await api('/ai/project-edit',{
          method:'POST',
          body:JSON.stringify({
            root,
            instruction:prompt,
            max_context_files:10
          })
        })

        const changedFiles=
          Array.isArray(result.files)
            ? result.files
            : []

        if(!changedFiles.length){
          throw new Error(
            'Backend에서 생성/수정된 프로젝트 파일이 반환되지 않았습니다.'
          )
        }

        // 프로젝트 단위 작업은 Backend가 실제 파일까지 저장합니다.
        // 이미 열려 있는 탭은 새 내용으로 즉시 동기화합니다.
        setEditorFileContents(prev=>{
          const next={...prev}

          for(const file of changedFiles){
            if(file?.path){
              next[file.path]=file.content??''
            }
          }

          return next
        })

        setEditorFileDirty(prev=>{
          const next={...prev}

          for(const file of changedFiles){
            if(file?.path){
              next[file.path]=false
            }
          }

          return next
        })

        await loadFiles()

        const primary=
          result.primary_file
          || changedFiles[0]?.path
          || ''

        if(primary){
          // 프로젝트 결과 대표 파일을 코드 편집기에 자동 활성화
          setWorkspaceTab('CODE')
          setFocusOwnerSafe('editor')

          setOpenEditorFiles(prev=>
            prev.includes(primary)
              ? prev
              : [...prev,primary]
          )

          const primaryResult=
            changedFiles.find(f=>f.path===primary)

          if(primaryResult){
            setSelected(primary)
            setFileTreeSelected(primary)
            setCode(primaryResult.content??'')
          }else{
            await openFile(primary)
          }

          setTimeout(()=>{
            try{ editorInstanceRef.current?.focus() }catch{}
          },0)
        }

        const created=Number(result.created_count||0)
        const updated=Number(result.updated_count||0)

        setCodeEditChat(prev=>[
          ...prev,
          {
            role:'assistant',
            content:
              `${result.summary||'프로젝트 코딩 작업을 완료했습니다.'} `
              +`신규 파일 ${created}개, 수정 파일 ${updated}개를 프로젝트에 저장했습니다.`
          }
        ])

        return
      }

      // FILE mode
      const result=await api('/ai/edit',{
        method:'POST',
        body:JSON.stringify({
          root,
          path:targetPath,
          instruction:prompt,
          content:currentCode,
          active_cell_index:isNotebookFile(targetPath)
            ? notebookEditorControllerRef.current?.getActiveCellIndex?.()
            : null
        })
      })

      const proposedCode =
        result.code
        || result.content
        || result.updated_code
        || result.result
        || ''

      if(!proposedCode){
        throw new Error(
          'Backend에서 수정된 코드가 반환되지 않았습니다.'
        )
      }

      const explanation =
        result.message
        || '코드 수정 제안을 만들었습니다.'

      // FILE 모드에서는 AI 응답을 즉시 원본 Editor에 덮어쓰지 않습니다.
      // 우측 `AI 변경 제안` 탭에서 먼저 코드를 검토한 뒤 Apply -> Diff -> 적용
      // 순서로 사용자가 명시적으로 반영하도록 합니다.
      setCodeEditProposal({
        path:targetPath,
        code:proposedCode,
        displayCode:result.cell_code||proposedCode,
        editScope:result.edit_scope||'file',
        activeCellIndex:result.active_cell_index??null,
        contextBudget:result.context_budget||null,
        baseCode:currentCode,
        explanation,
        instruction:prompt,
        createdAt:new Date().toISOString()
      })
      setCodeDiffReview(null)
      setCodeRightPanelTab('PROPOSAL')
      setWorkspaceRightCollapsed(false)
      setWorkspaceTab('CODE')

      setCodeEditChat(prev=>[
        ...prev,
        {
          role:'assistant',
          content:
            explanation
            +' 우측 `AI 변경 제안` 탭에서 코드를 확인한 뒤 Apply를 눌러 현재 소스와 비교할 수 있습니다.'
        }
      ])

    }catch(e){
      let readableError=String(e?.message||e)
      if(e?.responseBody){
        try{
          const parsed=JSON.parse(e.responseBody)
          const detail=parsed?.detail||parsed
          if(detail?.code==='CONTEXT_BUDGET_EXCEEDED'||detail?.code==='MODEL_CONTEXT_OVERFLOW'){
            readableError=detail.message||'LLM Context 길이를 초과했습니다.'
            if(detail.active_cell_index!==undefined){
              readableError+=` 대상 Notebook Cell ${Number(detail.active_cell_index)+1}.`
            }
            if(detail.prompt_chars){
              readableError+=` 요청 Context 약 ${Number(detail.prompt_chars).toLocaleString('ko-KR')}자.`
            }
          }else if(typeof detail?.message==='string'){
            readableError=detail.message
          }else if(typeof detail==='string'){
            readableError=detail
          }
        }catch{}
      }
      setCodeEditChat(prev=>[
        ...prev,
        {
          role:'assistant',
          content:
            `${projectMode?'프로젝트 코딩':'코드 수정'} 실패: `
            +readableError
        }
      ])
    }finally{
      setCodeEditBusy(false)
    }
  }

  const openCodeEditDiffReview=async()=>{
    if(!codeEditProposal?.code||!codeEditProposal?.path) return

    const proposalPath=codeEditProposal.path

    if(!openEditorFilesRef.current?.includes(proposalPath)){
      try{ await openFile(proposalPath) }catch{}
    }else{
      activateEditorFile(proposalPath)
    }

    const currentContent=
      editorFileContents[proposalPath]
      ?? (selectedEditorFileRef.current===proposalPath?code:'')
      ?? codeEditProposal.baseCode
      ?? ''

    setCodeDiffReview({
      path:proposalPath,
      original:currentContent,
      modified:codeEditProposal.code,
      explanation:codeEditProposal.explanation||'',
      instruction:codeEditProposal.instruction||''
    })
    setWorkspaceTab('CODE')
  }

  const applyCodeEditProposal=()=>{
    if(!codeDiffReview?.modified||!codeDiffReview?.path) return

    const targetPath=codeDiffReview.path
    const nextCode=codeDiffReview.modified

    setSelected(targetPath)
    setFileTreeSelected(targetPath)
    setCode(nextCode)

    setOpenEditorFiles(prev=>
      prev.includes(targetPath)?prev:[...prev,targetPath]
    )

    setEditorFileContents(prev=>({
      ...prev,
      [targetPath]:nextCode
    }))

    setEditorFileDirty(prev=>({
      ...prev,
      [targetPath]:true
    }))

    setCodeEditChat(prev=>[
      ...prev,
      {
        role:'assistant',
        content:'Diff에서 확인한 AI 변경안을 현재 편집기에 머지했습니다. 아직 디스크에는 저장하지 않았습니다. Ctrl+S로 저장하세요.'
      }
    ])

    setCodeDiffReview(null)
    setCodeEditProposal(null)
  }

  const cancelCodeDiffReview=()=>{
    setCodeDiffReview(null)
  }

  const discardCodeEditProposal=()=>{
    setCodeDiffReview(null)
    setCodeEditProposal(null)
    setCodeRightPanelTab('FILES')
    setCodeEditChat(prev=>[
      ...prev,
      {role:'assistant',content:'AI 변경 제안을 취소했습니다.'}
    ])
  }


  const buildProjectTree=(fileList,dirList=[])=>{
    const rootNode={name:'',path:'',type:'folder',children:{}}

    for(const raw of dirList){
      const parts=String(raw).replace(/\\/g,'/').split('/').filter(Boolean)
      let node=rootNode

      parts.forEach((part,index)=>{
        const path=parts.slice(0,index+1).join('/')

        if(!node.children[part]){
          node.children[part]={
            name:part,
            path,
            type:'folder',
            children:{}
          }
        }else{
          node.children[part].type='folder'
        }

        node=node.children[part]
      })
    }

    for(const raw of fileList){
      const parts=String(raw).replace(/\\/g,'/').split('/').filter(Boolean)
      let node=rootNode

      parts.forEach((part,index)=>{
        const path=parts.slice(0,index+1).join('/')
        const isLast=index===parts.length-1

        if(!node.children[part]){
          node.children[part]={
            name:part,
            path,
            type:isLast?'file':'folder',
            children:{}
          }
        }

        if(!isLast){
          node.children[part].type='folder'
        }

        node=node.children[part]
      })
    }

    const sortNode=(node)=>{
      const items=Object.values(node.children||{})
      items.sort((a,b)=>{
        if(a.type!==b.type) return a.type==='folder'?-1:1
        return a.name.localeCompare(b.name,'ko')
      })
      node.sortedChildren=items
      items.forEach(sortNode)
      return node
    }

    return sortNode(rootNode)
  }

  const projectTree=buildProjectTree(files,projectDirs)

  const toggleTreeFolder=(path)=>{
    setFileTreeExpanded(prev=>({...prev,[path]:!prev[path]}))
  }

  const resolveFileCreateParent=()=>{
    const selectedPath=normalizeProjectRelativePath(fileTreeSelected)
    if(!selectedPath) return ''

    const fileSet=new Set(files.map(normalizeProjectRelativePath))
    const dirSet=new Set(projectDirs.map(normalizeProjectRelativePath))

    if(dirSet.has(selectedPath)) return selectedPath
    if(fileSet.has(selectedPath)){
      return selectedPath.split('/').slice(0,-1).join('/')
    }

    // The rendered tree itself is built from canonical `/` paths. If a folder
    // was selected just before an async tree refresh, preserve that selected
    // nested path instead of silently falling back to project root.
    const findNode=(node,path)=>{
      if(!node) return null
      if(node.path===path) return node
      for(const child of node.sortedChildren||[]){
        const found=findNode(child,path)
        if(found) return found
      }
      return null
    }
    const selectedNode=findNode(projectTree,selectedPath)
    return selectedNode?.type==='folder' ? selectedPath : ''
  }

  const createProjectFolder=async()=>{
    if(!root) return

    const parent=resolveFileCreateParent()

    const name=window.prompt('새 폴더 이름을 입력하세요.')
    if(!name?.trim()) return

    const relativePath=[parent,name.trim()].filter(Boolean).join('/')

    try{
      await api('/files/folder',{
        method:'POST',
        body:JSON.stringify({
          root,
          relative_path:relativePath
        })
      })

      await loadFiles()
      setFileTreeExpanded(prev=>({
        ...prev,
        [parent]:true,
        [relativePath]:true
      }))
      setFileTreeSelected(relativePath)
      setFileTreeSelectedPaths([normalizeProjectRelativePath(relativePath)])
    }catch(e){
      window.alert('폴더 생성 실패: '+String(e))
    }
  }

  const createProjectFile=async()=>{
    if(!root||fileCreateLoading||fileCreateBusyRef.current) return

    const parent=resolveFileCreateParent()

    const name=window.prompt(
      '새 파일 이름을 입력하세요.',
      'new_file.py'
    )

    if(!name?.trim()) return
    fileCreateBusyRef.current=true

    const relativePath=[parent,name.trim()]
      .filter(Boolean)
      .join('/')

    setFileCreateLoading(true)

    try{
      const result=await api('/files/create',{
        method:'POST',
        body:JSON.stringify({
          root,
          relative_path:relativePath
        })
      })

      if(!result?.ok||!result?.exists||!result?.relative_path){
        throw new Error('Backend 응답은 성공했지만 실제 디스크 파일 검증에 실패했습니다.')
      }

      const canonicalPath=result.relative_path
      await loadFiles()

      setFileTreeExpanded(prev=>({
        ...prev,
        [normalizeProjectRelativePath(parent)]:true
      }))

      setFileTreeSelected(canonicalPath)
      setFileTreeSelectedPaths([normalizeProjectRelativePath(canonicalPath)])
      if(result?.mtime_ns){
        const createdKey=normalizeProjectRelativePath(canonicalPath)
        const createdMeta={
          mtime_ns:result.mtime_ns,
          size:result.size||0,
          sha256:result.sha256||''
        }
        editorFileDiskMetaRef.current={
          ...editorFileDiskMetaRef.current,
          [createdKey]:createdMeta
        }
        setEditorFileDiskMeta(prev=>({
          ...prev,
          [createdKey]:createdMeta
        }))
      }

      // Backend에서 실제 디스크 생성과 검증이 끝난 뒤에만 Editor tab을 엽니다.
      if(canonicalPath){
        try{
          await openFile(canonicalPath)
        }catch(openError){
          console.error(
            '새 파일 자동 열기 실패:',
            openError
          )
        }
      }
    }catch(e){
      window.alert('파일 생성 실패: '+String(e))
    }finally{
      setFileCreateLoading(false)
      fileCreateBusyRef.current=false
    }
  }



  const migrateOpenEditorPathAfterRename=(oldPath,newPath)=>{
    if(!oldPath||!newPath||oldPath===newPath) return

    const oldNorm=String(oldPath).replace(/\\/g,'/')
    const newNorm=String(newPath).replace(/\\/g,'/')

    const remap=(path)=>{
      const normalized=String(path||'').replace(/\\/g,'/')

      if(normalized===oldNorm){
        return newNorm
      }

      // 폴더 이름 변경 시 열린 하위 파일들의 경로도 함께 이동
      if(normalized.startsWith(oldNorm+'/')){
        return newNorm+normalized.slice(oldNorm.length)
      }

      return path
    }

    setOpenEditorFiles(prev=>{
      const mapped=prev.map(remap)

      return mapped.filter(
        (path,index,array)=>
          array.indexOf(path)===index
      )
    })

    setEditorFileContents(prev=>{
      const next={}

      for(const [path,content] of Object.entries(prev)){
        next[remap(path)]=content
      }

      return next
    })

    setEditorFileDirty(prev=>{
      const next={}

      for(const [path,dirty] of Object.entries(prev)){
        next[remap(path)]=dirty
      }

      return next
    })

    setSelected(prev=>remap(prev))
    setFileTreeSelected(prev=>remap(prev))

    setEditorTabMenu(prev=>
      prev
        ? {
            ...prev,
            path:remap(prev.path)
          }
        : prev
    )
  }


  const beginRenameTreeItem=(node)=>{
    setFileTreeSelected(node.path)
    setFileTreeRename({
      path:node.path,
      value:node.name
    })
  }

  const saveTreeRename=async()=>{
    if(!fileTreeRename?.path) return

    const oldPath=fileTreeRename.path
    const nextName=fileTreeRename.value.trim()

    if(!nextName) return

    const currentName=
      oldPath
        .replace(/\\/g,'/')
        .split('/')
        .filter(Boolean)
        .pop()
      || ''

    // 이름이 실제로 바뀌지 않았다면 API 호출 없이 편집 종료
    if(nextName===currentName){
      setFileTreeRename(null)
      return
    }

    try{
      const result=await api('/files/rename',{
        method:'POST',
        body:JSON.stringify({
          root,
          relative_path:oldPath,
          new_name:nextName
        })
      })

      const newPath=result.new_relative_path||''

      if(newPath){
        // 파일 시스템 이름 변경과 열린 코드 탭 상태를 동일하게 맞춤
        migrateOpenEditorPathAfterRename(
          oldPath,
          newPath
        )
      }

      setFileTreeSelected(newPath)
      setFileTreeSelectedPaths(newPath?[normalizeProjectRelativePath(newPath)]:[])
      setFileTreeRename(null)

      await loadFiles()

      // 현재 열려 있던 파일이라면 같은 편집 내용을 유지한 채
      // 새 경로 탭이 계속 활성 상태가 되도록 함
      if(
        newPath
        && selected===oldPath
      ){
        setSelected(newPath)
      }
    }catch(e){
      window.alert('이름 변경 실패: '+String(e))
    }
  }

  const getSelectedProjectFiles=()=>{
    const fileSet=new Set(files.map(normalizeProjectRelativePath))
    return (fileTreeSelectedPaths.length?fileTreeSelectedPaths:[fileTreeSelected])
      .map(normalizeProjectRelativePath)
      .filter(path=>path&&fileSet.has(path))
  }

  const selectProjectTreeNode=(node,event)=>{
    const path=normalizeProjectRelativePath(node.path)
    if(!path) return
    setFocusOwnerSafe('tree')

    if(node.type==='folder'){
      setFileTreeSelected(path)
      setFileTreeSelectedPaths([path])
      fileTreeSelectionAnchorRef.current=path
      toggleTreeFolder(path)
      return
    }

    const ordered=files.map(normalizeProjectRelativePath).filter(Boolean)
    if(event?.shiftKey && fileTreeSelectionAnchorRef.current){
      const anchor=fileTreeSelectionAnchorRef.current
      const a=ordered.indexOf(anchor)
      const b=ordered.indexOf(path)
      if(a>=0&&b>=0){
        const [start,end]=a<=b?[a,b]:[b,a]
        const range=ordered.slice(start,end+1)
        setFileTreeSelectedPaths(range)
        setFileTreeSelected(path)
        return
      }
    }

    if(event?.ctrlKey||event?.metaKey){
      setFileTreeSelectedPaths(prev=>{
        const current=new Set(prev.map(normalizeProjectRelativePath).filter(Boolean))
        if(current.has(path)) current.delete(path)
        else current.add(path)
        const next=[...current]
        setFileTreeSelected(next.includes(path)?path:(next[next.length-1]||''))
        return next
      })
      fileTreeSelectionAnchorRef.current=path
      return
    }

    setFileTreeSelected(path)
    setFileTreeSelectedPaths([path])
    fileTreeSelectionAnchorRef.current=path
    setWorkspaceTab('CODE')
    openFile(path)
  }

  const requestProjectFilesDelete=(paths=null)=>{
    const fileSet=new Set(files.map(normalizeProjectRelativePath))
    const candidates=(paths||getSelectedProjectFiles())
      .map(normalizeProjectRelativePath)
      .filter(path=>path&&fileSet.has(path))
    const targets=[...new Set(candidates)]
    setFileTreeContextMenu(null)
    if(!targets.length) return
    const dirtyCount=targets.filter(path=>!!editorFileDirty[path]).length
    setFileDeleteConfirm({
      paths:targets,
      deleting:false,
      error:'',
      dirtyCount
    })
  }

  const confirmProjectFilesDelete=async()=>{
    const pending=fileDeleteConfirm
    if(!pending||pending.deleting) return
    setFileDeleteConfirm(prev=>prev?{...prev,deleting:true,error:''}:prev)
    try{
      const result=await api('/files/delete',{
        method:'POST',
        body:JSON.stringify({root,relative_paths:pending.paths})
      })
      const deleted=[...(result?.deleted||[]),...(result?.missing||[])]
        .map(normalizeProjectRelativePath)
      closeEditorFiles(deleted)
      setFileTreeSelectedPaths([])
      setFileTreeSelected('')
      editorFileDiskMetaRef.current={...editorFileDiskMetaRef.current}
      for(const path of deleted) delete editorFileDiskMetaRef.current[path]
      setEditorFileDiskMeta(prev=>{
        const next={...prev}; for(const path of deleted) delete next[path]; return next
      })
      setEditorExternalState(prev=>{
        const next={...prev}; for(const path of deleted) delete next[path]; return next
      })
      setExternalFileNotifications(prev=>prev.filter(item=>!deleted.includes(item.path)))
      await loadFiles(root)
      setFileDeleteConfirm(null)
      if(result?.lock_recovered){
        const released=[]
        if((result?.released_sqlite_connections||[]).length) released.push('SQL Workspace SQLite 연결')
        if((result?.reset_python_sessions||[]).length) released.push('Python/Notebook 실행 세션')
        if(released.length){
          window.alert(`${released.join(' 및 ')}을 종료해 DB 파일 잠금을 해제한 뒤 삭제했습니다.`)
        }
      }
    }catch(e){
      let message=String(e)
      try{
        const payload=JSON.parse(String(e?.responseBody||''))
        const detail=payload?.detail
        if(detail&&typeof detail==='object'&&detail.message){
          message=String(detail.message)
          if(detail.original_error) message+=`\n\n${String(detail.original_error)}`
        }else if(typeof detail==='string'&&detail){
          message=detail
        }
      }catch{}
      setFileDeleteConfirm(prev=>prev?{...prev,deleting:false,error:message}:prev)
    }
  }

  const openProjectFileContextMenu=(node,event)=>{
    event.preventDefault()
    event.stopPropagation()
    if(node.type!=='file') return
    const path=normalizeProjectRelativePath(node.path)
    const current=new Set(fileTreeSelectedPaths.map(normalizeProjectRelativePath))
    let paths
    if(current.has(path)&&current.size){
      paths=[...current]
    }else{
      paths=[path]
      setFileTreeSelected(path)
      setFileTreeSelectedPaths(paths)
      fileTreeSelectionAnchorRef.current=path
    }
    setFocusOwnerSafe('tree')
    setFileTreeContextMenu({x:event.clientX,y:event.clientY,paths})
  }

  useEffect(()=>{
    const onKeyDown=(event)=>{
      if(event.key==='Delete' && focusOwnerRef.current==='tree'){
        const targets=getSelectedProjectFiles()
        if(targets.length){
          event.preventDefault()
          event.stopPropagation()
          requestProjectFilesDelete(targets)
        }
      }
      if(event.key==='Escape'){
        setFileTreeContextMenu(null)
      }
    }
    const closeMenu=()=>setFileTreeContextMenu(null)
    window.addEventListener('keydown',onKeyDown,true)
    window.addEventListener('mousedown',closeMenu)
    return()=>{
      window.removeEventListener('keydown',onKeyDown,true)
      window.removeEventListener('mousedown',closeMenu)
    }
  },[files,fileTreeSelectedPaths,fileTreeSelected,editorFileDirty,root])

  const renderProjectTreeNode=(node,depth=0)=>{
    const isFolder=node.type==='folder'
    const expanded=!!fileTreeExpanded[node.path]
    const selectedNode=fileTreeSelectedPaths.map(normalizeProjectRelativePath).includes(normalizeProjectRelativePath(node.path))
      || (!fileTreeSelectedPaths.length && normalizeProjectRelativePath(fileTreeSelected)===normalizeProjectRelativePath(node.path))

    return <div key={node.path} className="tree-node">
      <div
        className={selectedNode?'tree-row selected':'tree-row'}
        style={{paddingLeft:`${depth*14+6}px`}}
        onClick={(e)=>{
          e.stopPropagation()
          selectProjectTreeNode(node,e)
        }}
        onDoubleClick={(e)=>{
          e.stopPropagation()
          if(isFolder){
            toggleTreeFolder(node.path)
          }else{
            setFileTreeSelected(node.path)
            setFileTreeSelectedPaths([normalizeProjectRelativePath(node.path)])
            fileTreeSelectionAnchorRef.current=normalizeProjectRelativePath(node.path)
            setWorkspaceTab('CODE')
            openFile(node.path)
          }
        }}
        onContextMenu={(e)=>openProjectFileContextMenu(node,e)}
      >
        <span
          className={isFolder?'tree-toggle visible':'tree-toggle'}
          onClick={(e)=>{
            if(!isFolder) return
            e.stopPropagation()
            toggleTreeFolder(node.path)
          }}
        >
          {isFolder?(expanded?'−':'+'):''}
        </span>

        <span className={isFolder?'tree-icon folder':'tree-icon file'}>
          {isFolder?(expanded?'📂':'📁'):'📄'}
        </span>

        {fileTreeRename?.path===node.path ? (
          <input
            className="tree-rename-input"
            value={fileTreeRename.value}
            autoFocus
            onClick={(e)=>e.stopPropagation()}
            onDoubleClick={(e)=>e.stopPropagation()}
            onChange={(e)=>setFileTreeRename({
              ...fileTreeRename,
              value:e.target.value
            })}
            onBlur={()=>{
              setFileTreeRename(null)
            }}
            onKeyDown={(e)=>{
              if(e.key==='Enter'){
                e.preventDefault()
                e.stopPropagation()
                saveTreeRename()
                return
              }

              if(e.key==='Escape'){
                e.preventDefault()
                e.stopPropagation()
                setFileTreeRename(null)
              }
            }}
          />
        ) : (
          <span className="tree-name">{node.name}</span>
        )}

        <button
          type="button"
          className="tree-rename-button tree-rename-pencil"
          title="이름 변경"
          aria-label={`${node.name} 이름 변경`}
          onMouseDown={(e)=>{
            e.preventDefault()
            e.stopPropagation()
          }}
          onClick={(e)=>{
            e.preventDefault()
            e.stopPropagation()
            beginRenameTreeItem(node)
          }}
          onDoubleClick={(e)=>{
            e.stopPropagation()
          }}
        >
          ✎
        </button>
      </div>

      {isFolder && expanded && node.sortedChildren?.map((child)=>
        renderProjectTreeNode(child,depth+1)
      )}
    </div>
  }


  const toggleProjectFavorite=async(project,e=null)=>{
    if(e) e.stopPropagation()
    try{
      const result=await api(`/projects/${project.id}/favorite`,{
        method:'POST',
        body:JSON.stringify({
          is_favorite:!project.is_favorite
        })
      })

      if(result.ok){
        setProjectList(prev=>prev.map(p=>
          p.id===project.id
            ? {...p,is_favorite:result.is_favorite}
            : p
        ))
      }
    }catch(err){
      console.error('즐겨찾기 변경 실패',err)
    }
  }


  const renderProjectLibraryScreen=()=> <div className="nav-page-shell">
    <div className="nav-page-head">
      <div>
        <div className="eyebrow">PROJECT LIBRARY</div>
        <h2>프로젝트 관리</h2>
        <p>저장된 프로젝트를 조회하고 최근 프로젝트와 즐겨찾기를 관리합니다.</p>
        <div className="project-library-db-status">
          <div>{projectListLoading?'DB 프로젝트 목록 불러오는 중...':projectListStatus}</div>
          <div>연결 경로: Frontend → FastAPI → PostgreSQL</div>
          {projectListLogPath&&<code>{projectListLogPath}</code>}
        </div>
      </div>
      <div className="nav-page-actions">
        <button type="button" onClick={refreshProjectList}>DB 새로고침</button>
        <button type="button" onClick={openProjectList}>프로젝트 불러오기</button>
        <button type="button" className="primary" onClick={startNewProject}>＋ 새 Agent</button>
      </div>
    </div>

    <div className="nav-page-grid">
      <section className="nav-page-card">
        <SectionTitle title={`전체 프로젝트 (${projectList.length})`}/>
        <div className="nav-project-list">
          {projectList.length===0&&<div className="empty-mini">저장된 프로젝트가 없습니다.</div>}
          {projectList.map(p=><button
            key={p.id}
            className={selectedProjectId===p.id?'nav-project-row active':'nav-project-row'}
            onClick={()=>loadProject(p.id)}
          >
            <span className="project-icon">▣</span>
            <div>
              <strong>{p.name}</strong>
              <small>{p.project_root}</small>
            </div>
            <span className={p.is_favorite?'nav-favorite active':'nav-favorite'}>★</span>
          </button>)}
        </div>
      </section>

      <section className="nav-page-card">
        <SectionTitle title="최근 프로젝트"/>
        <div className="nav-project-list">
          {projectList
            .filter(p=>p.last_opened_at)
            .sort((a,b)=>new Date(b.last_opened_at)-new Date(a.last_opened_at))
            .slice(0,10)
            .map(p=><button
              key={p.id}
              className="nav-project-row"
              onClick={()=>loadProject(p.id)}
            >
              <span className="project-icon">◷</span>
              <div>
                <strong>{p.name}</strong>
                <small>{new Date(p.last_opened_at).toLocaleString()}</small>
              </div>
            </button>)}
        </div>
      </section>

      <section className="nav-page-card">
        <SectionTitle title="즐겨찾기"/>
        <div className="nav-project-list">
          {projectList.filter(p=>p.is_favorite).length===0
            ? <div className="empty-mini">즐겨찾기 프로젝트가 없습니다.</div>
            : projectList.filter(p=>p.is_favorite).map(p=><button
                key={p.id}
                className="nav-project-row"
                onClick={()=>loadProject(p.id)}
              >
                <span className="project-icon">★</span>
                <div>
                  <strong>{p.name}</strong>
                  <small>{p.project_root}</small>
                </div>
              </button>)}
        </div>
      </section>
    </div>
  </div>

  const renderMcpScreen=()=> <div className="nav-page-shell">
    <div className="nav-page-head">
      <div>
        <div className="eyebrow">MCP / TOOL</div>
        <h2>MCP 도구 관리</h2>
        <p>MCP 서버와 등록된 도구를 확인하고 동기화합니다.</p>
      </div>
      <div className="nav-page-actions">
        <button className="primary" onClick={openMcpAddDialog}>＋ MCP 연결 추가</button>
        <button onClick={refreshMcp}>새로고침</button>
      </div>
    </div>

    <div className="nav-page-grid two">
      <section className="nav-page-card">
        <SectionTitle title={`MCP 서버 (${mcpServers.length})`}/>
        <div className="nav-project-list">
          {mcpServers.length===0&&<div className="empty-mini">등록된 MCP 서버가 없습니다.</div>}
          {mcpServers.map((s,i)=><div className="nav-project-row static mcp-server-row" key={s.id||i}>
            <span className="project-icon">◉</span>
            <div>
              <strong>{s.name||'MCP Server'}</strong>
              <small>{s.endpoint||''}</small>
              <small>{s.status?`상태: ${s.status}`:'상태 확인 필요'}</small>
            </div>
            <button type="button" className="mcp-sync-button" onClick={()=>syncMcpServer(s.id)}>Tool 동기화</button>
          </div>)}
        </div>
      </section>

      <section className="nav-page-card">
        <SectionTitle title={`MCP 도구 (${mcpTools.length})`}/>
        <div className="nav-project-list">
          {mcpTools.length===0&&<div className="empty-mini">등록된 MCP 도구가 없습니다.</div>}
          {mcpTools.map((t,i)=><div className="nav-project-row static" key={t.id||i}>
            <span className="project-icon">⌘</span>
            <div><strong>{t.name||String(t)}</strong><small>{t.category||'MCP Tool'}</small></div>
          </div>)}
        </div>
      </section>
    </div>
  </div>

  const renderToolsScreen=()=> <div className="nav-page-shell">
    <div className="nav-page-head">
      <div>
        <div className="eyebrow">TOOLS</div>
        <h2>도구 / 실행 관리</h2>
        <p>프로젝트 실행, 터미널, 코드 편집 및 작업 상태를 관리합니다.</p>
      </div>
      <div className="nav-page-actions">
        <button className="primary" onClick={goWorkspace}>작업공간 열기</button>
      </div>
    </div>
    <div className="nav-page-grid two">
      <section className="nav-page-card">
        <SectionTitle title="빠른 실행"/>
        <button className="nav-big-action" onClick={goWorkspace}>▣ 작업공간 열기</button>
        <button className="nav-big-action" onClick={()=>setWorkspaceTab('RUN')}>▶ 실행 결과</button>
      </section>
      <section className="nav-page-card">
        <SectionTitle title="현재 프로젝트"/>
        <h3>{currentProjectName}</h3>
        <code>{currentProjectPath||'프로젝트가 선택되지 않았습니다.'}</code>
      </section>
    </div>
  </div>


  const changeProjectFilter=async(filter)=>{
    setProjectFilter(filter)
    await refreshProjectList()
  }

  const classifyDevelopmentStatus=(workflowState={})=>{
    const status=String(workflowState?.status||'').toUpperCase()
    const testReturncode=(
      workflowState?.test_result?.returncode
      ??workflowState?.package_result?.test_returncode
      ??workflowState?.test_returncode
      ??null
    )
    const artifactOk=workflowState?.build_artifact_validation?.ok===true
    const launcherOk=(
      workflowState?.launcher_generation_result?.ok===true
      ||workflowState?.package_result?.launcher_generation?.ok===true
    )
    const appliedFiles=Array.isArray(workflowState?.patch_result)
      ? workflowState.patch_result.length
      : 0

    const errorText=String(
      workflowState?.error
      ||workflowState?.last_error
      ||workflowState?.message
      ||''
    ).trim()

    // substring 포함 여부가 아니라 정확한 최종 상태만 성공으로 인정합니다.
    // CODE_PLAN_INCOMPLETE 안의 "COMPLETE" 때문에 성공으로 오판하던 버그를 차단합니다.
    const successfulFinalStatuses=new Set([
      'COMPLETED',
      'SUCCESS'
    ])

    const failedStatuses=new Set([
      'FAILED',
      'ERROR',
      'INCOMPLETE',
      'CODE_PLAN_INCOMPLETE',
      'REPAIR_PLAN_INCOMPLETE',
      'TEST_REPAIR_PLAN_FAILED',
      'TEST_REPAIR_PLAN_INCOMPLETE',
      'BUILD_FAILED',
      'TEST_FAILED',
      'PACKAGE_FAILED',
      'LAUNCHER_GENERATION_FAILED',
      'FILE_APPLY_FAILED',
      'FAILED_NO_ARTIFACTS',
      'REQUIREMENT_COVERAGE_FAILED',
      'BUILD_ARTIFACT_STALLED',
      'DEBUG_STOPPED',
      'ABORTED'
    ])

    const waitingStatuses=new Set([
      'DEBUG_PATCH_READY',
      'WAITING_APPROVAL',
      'APPROVAL_REQUIRED',
      'CHECKPOINT',
      'PAUSED',
      'WAITING',
      'REVIEW_REQUIRED'
    ])

    if(successfulFinalStatuses.has(status)){
      const missingEvidence=[]

      if(testReturncode!==0){
        missingEvidence.push(
          testReturncode===null
            ? '테스트 실행 결과가 없습니다.'
            : `테스트 ReturnCode=${testReturncode}`
        )
      }

      if(!artifactOk){
        missingEvidence.push('최종 산출물 검증이 완료되지 않았습니다.')
      }

      if(!launcherOk){
        missingEvidence.push('SYSTEM_ADMIN.cmd 실행 진입점 검증이 완료되지 않았습니다.')
      }

      if(appliedFiles<=0){
        missingEvidence.push('실제 생성/수정된 파일이 확인되지 않았습니다.')
      }

      if(missingEvidence.length===0){
        return {
          kind:'success',
          title:'Agent 개발이 완료되었습니다.',
          detail:
            `파일 ${appliedFiles}개 생성/수정, `
            +`테스트 통과(ReturnCode=0), `
            +'SYSTEM_ADMIN.cmd 생성 및 최종 산출물 검증까지 완료되었습니다.',
          status
        }
      }

      return {
        kind:'failure',
        title:'Agent 개발 완료 조건을 충족하지 못했습니다.',
        detail:missingEvidence.join(' '),
        status:'INCOMPLETE'
      }
    }

    if(
      failedStatuses.has(status)
      ||testReturncode>0
    ){
      return {
        kind:'failure',
        title:'Agent 개발에 실패했습니다.',
        detail:
          errorText
          ||(
            testReturncode>0
              ? `테스트가 실패했습니다. ReturnCode=${testReturncode}`
              : `Workflow 상태: ${status||'FAILED'}`
          ),
        status
      }
    }

    if(waitingStatuses.has(status)){
      return {
        kind:status==='DEBUG_PATCH_READY'?'action':'waiting',
        title:
          status==='DEBUG_PATCH_READY'
            ? '디버그 패치가 준비되었습니다.'
            : '사용자 조치를 기다리고 있습니다.',
        detail:
          status==='DEBUG_PATCH_READY'
            ? '개발이 완료된 상태가 아닙니다. 생성된 디버그 패치를 검토하거나 Workflow를 재개해야 합니다.'
            : 'Workflow가 완료되지 않았습니다. 승인·검토·재개 등 다음 조치가 필요합니다.',
        status
      }
    }

    return {
      kind:'info',
      title:'Agent Factory 실행이 종료되었습니다.',
      detail:`완료 여부를 확정할 수 없는 상태입니다: ${status||'UNKNOWN'}`,
      status
    }
  }



  const renderDevelopmentProgress=()=>(
    developmentProgress.active
      ? <div className="development-progress-card">
          <div className="development-progress-head">
            <div>
              <span className="development-progress-pulse">●</span>
              <div>
                <strong>{developmentProgress.stage}</strong>
                <small>{developmentProgress.detail}</small>
              </div>
            </div>

            <div className="development-progress-stats">
              <b>{developmentProgress.percent}%</b>
              <span>{developmentProgress.elapsedSeconds}s</span>
            </div>
          </div>

          <div
            className="development-progress-track"
            role="progressbar"
            aria-label="Agent 개발 진행률"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={developmentProgress.percent}
          >
            <div
              className="development-progress-fill"
              style={{width:`${developmentProgress.percent}%`}}
            />
          </div>

          <div className="development-progress-stages">
            {[
              ['준비',4],
              ['Factory',10],
              ['코드/검증',30],
              ['테스트/복구',58],
              ['패키징',78],
              ['완료',100]
            ].map(([label,threshold])=><span
              key={label}
              className={
                developmentProgress.percent>=threshold
                  ? 'done'
                  : ''
              }
            >
              <i></i>{label}
            </span>)}
          </div>
        </div>
      : null
  )


  const copyDiagnosticPath=async(path)=>{
    if(!path) return
    try{
      await navigator.clipboard.writeText(path)
    }catch(e){
      window.prompt('전체 경로를 복사하세요.',path)
    }
  }

  const formatDiagnosticTime=(value)=>{
    if(!value) return '-'
    try{
      const date=new Date(value)
      if(Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString('ko-KR',{hour12:false})
    }catch(_){
      return String(value)
    }
  }

  const renderFailureDiagnostics=()=>{
    const d=workflow?.failure_diagnostics||workflow?.state?.failure_diagnostics
    if(!d) return null
    if(developmentFinalStatus?.kind==='success') return null

    const diagnosticsProjectRoot=(
      d.project_root
      ||String(d.failure_report||'').replace(
        /[\\/]+reports[\\/]+failure_report\.md$/i,
        ''
      )
    )

    return <div className="failure-diagnostics-card">
      <div className="failure-diagnostics-head">
        <div>
          <span>!</span>
          <div>
            <strong>
              {(d.diagnostics_fresh===false||d.status==='RUNNING'||d.status==='DIAGNOSTICS_STALE')
                ? '현재 실행의 진단 자료를 확인하고 있습니다.'
                : '실패 진단 자료가 생성되었습니다.'}
            </strong>
            <small>
              {(d.diagnostics_fresh===false||d.status==='RUNNING'||d.status==='DIAGNOSTICS_STALE')
                ? '이전 실행의 실패 파일을 현재 실행 결과로 사용하지 않습니다.'
                : '실패 원인과 재시도 자료를 프로젝트 폴더에 저장했습니다.'}
            </small>
          </div>
        </div>
        <b>{d.status||'FAILED'}</b>
      </div>

      <div className="failure-diagnostics-run-info">
        <div><span>실행 ID</span><strong title={d.run_id||''}>{d.run_id||'-'}</strong></div>
        <div><span>실행 시작</span><strong>{formatDiagnosticTime(d.run_started_at)}</strong></div>
        <div><span>진단 생성</span><strong>{formatDiagnosticTime(d.diagnostic_generated_at)}</strong></div>
        <div>
          <span>현재 실행 자료</span>
          <strong className={d.diagnostics_fresh===false?'no':'ok'}>
            {d.diagnostics_fresh===false?'아님 / 대기':'맞음'}
          </strong>
        </div>
      </div>

      <div className="failure-diagnostics-summary">
        <div><span>실패 단계</span><strong>{d.failure_stage||'-'}</strong></div>
        <div><span>실제 Agent 파일</span><strong>{d.actual_file_count||0}개</strong></div>
        <div><span>계획 파일</span><strong>{d.planned_file_count||0}개</strong></div>
      </div>

      {(()=>{
        const cp=d.code_plan_validation||{}
        const missing=(
          cp.missing_required_paths
          ||d.missing_required_paths
          ||[]
        )
        if(
          !Object.keys(cp).length
          &&missing.length===0
        ) return null

        return <div className="failure-code-plan">
          <div className="failure-code-plan-head">
            <strong>Code Plan 완전성</strong>
            <b className={missing.length===0?'ok':'no'}>
              {missing.length===0
                ? '필수 파일 포함 완료'
                : `필수 파일 ${missing.length}개 누락`}
            </b>
          </div>
          <div className="failure-code-plan-stats">
            <span>Required <b>{cp.required_count??'-'}개</b></span>
            <span>기존 존재 <b>{cp.existing_count??'-'}개</b></span>
            <span>Plan 변경 <b>{cp.planned_change_count??'-'}개</b></span>
            <span>자동 보강 <b>{cp.supplement_rounds??0}회</b></span>
          </div>
          {missing.length>0
            ? <div className="failure-code-plan-missing">
                {missing.map(path=><code key={path}>{path}</code>)}
              </div>
            : null}
        </div>
      })()}

      <div className="failure-execution-state">
        <div>
          <span>파일 적용</span>
          <strong className={d.file_apply?.executed?'ok':'no'}>
            {d.file_apply?.executed
              ? `실행됨 · ${d.file_apply?.count||0}개`
              : '실행되지 않음'}
          </strong>
        </div>
        <div>
          <span>테스트</span>
          <strong className={d.test?.executed?'ok':'no'}>
            {d.test?.executed
              ? `실행됨 · ReturnCode ${d.test?.returncode??'-'}`
              : '실행되지 않음'}
          </strong>
        </div>
        <div>
          <span>디버그/복구</span>
          <strong className={d.debug?.executed?'ok':'no'}>
            {d.debug?.executed
              ? `실행됨 · ${d.debug?.count||0}회`
              : '실행되지 않음'}
          </strong>
        </div>
      </div>

      <div className="failure-diagnostics-reason">
        <span>실패 원인</span>
        <p>{d.failure_reason||'원인 정보가 없습니다.'}</p>
      </div>

      {(()=>{
        const fa=d.file_apply_validation||{}
        const failure=fa.failure||{}
        const recoveries=fa.focused_recoveries||[]
        if(!Object.keys(fa).length) return null
        if(!failure.target&&!recoveries.length&&fa.ok!==false) return null
        return <div className="failure-file-apply-details">
          <div className="failure-file-apply-details-head">
            <strong>Patch 적용 상세</strong>
            <small>문자열 일치 실패와 자동 복구 시도를 구분해서 표시합니다.</small>
          </div>
          {failure.target?<div className="failure-file-apply-target">
            <span>실패 대상</span>
            <code>{failure.target}</code>
            <small>Change {Number(failure.change_index??-1)+1} · Replacement {Number(failure.replacement_index??-1)+1}</small>
          </div>:null}
          {recoveries.length>0?<div className="failure-file-apply-recoveries">
            {recoveries.map((item,index)=><div key={`${item.target||'recovery'}-${index}`}>
              <b>자동 복구 {index+1}</b>
              <code>{item.target||'-'}</code>
              <span>{item.strategy||'focused recovery'}</span>
            </div>)}
          </div>:null}
        </div>
      })()}

      {(()=>{
        const details=d.build_artifact_validation?.placeholder_details||[]
        if(!details.length) return null
        return <div className="failure-placeholder-details">
          <div className="failure-placeholder-details-head">
            <strong>Placeholder 상세 위치</strong>
            <small>실제로 미구현으로 판정된 줄만 표시합니다.</small>
          </div>
          {details.map((item,index)=><div className="failure-placeholder-file" key={`${item.path||'file'}-${index}`}>
            <code>{item.path||'-'}</code>
            {(item.findings||[]).map((finding,i)=><div className="failure-placeholder-finding" key={`${finding.line||i}-${i}`}>
              <b>Line {finding.line??'-'}</b>
              <span>{finding.reason||'placeholder'}</span>
              <code>{finding.snippet||''}</code>
            </div>)}
          </div>)}
        </div>
      })()}

      {diagnosticsProjectRoot&&
        <div className="failure-diagnostics-root">
          <div className="failure-diagnostics-root-head">
            <strong>기준 프로젝트 폴더</strong>
            <button
              type="button"
              className="failure-file-copy-button"
              onClick={()=>copyDiagnosticPath(diagnosticsProjectRoot)}
            >
              경로 복사
            </button>
          </div>
          <code title={diagnosticsProjectRoot}>{diagnosticsProjectRoot}</code>
        </div>
      }

      <div className="failure-diagnostics-files">
        <strong>진단 / 로그 파일</strong>
        <small>경로를 생략하지 않고 전체 표시합니다. 필요한 경로는 ‘경로 복사’ 버튼으로 복사할 수 있습니다.</small>
        {[
          ['실패 리포트','failure_report',d.failure_report],
          ['Workflow State','workflow_state',d.workflow_state],
          ['요구사항 Snapshot','requirements_snapshot',d.requirements_snapshot],
          ['생성 산출물','generated_artifacts',d.generated_artifacts],
          ['Debug Patch','debug_patch',d.debug_patch],
          ['복구 계획','recovery_plan',d.recovery_plan],
          ['Agent Factory Log','agent_factory_log',''],
          ['Workflow Log','workflow_execution_log',''],
          ['Test Log','test_log',''],
          ['Debug Log','debug_log','']
        ].map(([label,key,fallback])=>{
          const info=d.files?.[key]
          const path=info?.path||fallback
          if(!path) return null

          return <div key={label} className="failure-file-row">
            <div className="failure-file-row-head">
              <span className="failure-file-label">{label}</span>
              <b className={
                info?.exists===true
                  ? 'exists'
                  : info?.exists===false
                    ? 'missing'
                    : 'unknown'
              }>
                {info?.exists===true
                  ? '✓ 있음'
                  : info?.exists===false
                    ? '× 없음'
                    : '? 확인 불가'}
              </b>
              <button
                type="button"
                className="failure-file-copy-button"
                onClick={()=>copyDiagnosticPath(path)}
                title="전체 경로 복사"
              >
                경로 복사
              </button>
            </div>
            <code className="failure-file-path" title={path}>{path}</code>
            <small className="failure-file-modified">
              마지막 업데이트: {formatDiagnosticTime(info?.modified_at)}
              {info?.size?` · ${Number(info.size).toLocaleString()} bytes`:''}
            </small>
          </div>
        })}
      </div>
    </div>
  }


  const renderDevelopmentFinalStatus=()=>{
    if(!developmentFinalStatus) return null

    const item=developmentFinalStatus

    return <div className={`development-final-status ${item.kind}`}>
      <div className="development-final-status-icon">
        {item.kind==='success'
          ? '✓'
          : item.kind==='failure'
            ? '!'
            : item.kind==='action'
              ? '↻'
              : item.kind==='waiting'
                ? '…'
                : 'i'}
      </div>

      <div className="development-final-status-body">
        <div className="development-final-status-head">
          <strong>{item.title}</strong>
          <span>{item.status||'UNKNOWN'}</span>
        </div>
        <p>{item.detail}</p>

        {(item.kind==='action'||item.kind==='waiting')&&
          <small>
            이 상태에서는 개발이 완료된 것으로 판단하지 않습니다.
          </small>
        }
      </div>

      <button
        type="button"
        className="development-final-status-close"
        onClick={()=>setDevelopmentFinalStatus(null)}
        title="상태 메시지 닫기"
      >
        ×
      </button>
    </div>
  }


  const refreshLlmUsage=async(
    projectRootOverride='',
    scopeOverride='',
    dateOverride='',
    monthOverride=''
  )=>{
    const target=(
      projectRootOverride
      || root
      || newAgentProjectRoot
      || ''
    ).trim()
    const scope=scopeOverride||llmUsageScope||'today'
    const selectedDate=dateOverride||llmUsageDate||localIsoDate()
    const selectedMonth=monthOverride||llmUsageMonth||localIsoMonth()
    const query=new URLSearchParams({
      project_root:target,
      scope,
      date:selectedDate,
      month:selectedMonth,
    })

    try{
      const result=await api(`/usage/summary?${query.toString()}`)
      setLlmUsageSummary(result)
      return result
    }catch(e){
      console.error('LLM 사용량 조회 실패',e)
      return null
    }
  }


  const refreshLlmCatalog=async()=>{
    setLlmCatalogLoading(true)
    setLlmCatalogError('')
    try{
      const [catalogResult,historyResult]=await Promise.all([
        api('/llm/catalog'),
        api('/llm/history?days=10&limit=500'),
      ])
      setLlmCatalog(catalogResult)
      setLlmHistory(historyResult)
      return {catalog:catalogResult,history:historyResult}
    }catch(e){
      console.error('LLM 요청/응답 기록 조회 실패',e)
      setLlmCatalogError(String(e?.message||e))
      return null
    }finally{
      setLlmCatalogLoading(false)
    }
  }

  const formatTokenCount=(value)=>
    Number(value||0).toLocaleString('ko-KR')

  const formatUsd=(value)=>{
    const amount=Number(value||0)
    return `$${amount.toFixed(amount<0.01?6:4)}`
  }

  const renderLlmUsagePanel=(reportMode=false)=>{
    const projectUsage=llmUsageSummary?.project||{}
    const studioUsage=llmUsageSummary?.studio||llmUsageSummary?.daily||{}
    const studioLabel=llmUsageSummary?.period_label||'AgentStudio 오늘 전체'

    return <div className={
      reportMode
        ? 'llm-usage-dashboard report-usage'
        : 'llm-usage-dashboard'
    }>
      <div className="llm-usage-title">
        <div>
          <small>{reportMode?'LLM COST ANALYSIS':'PAID LLM USAGE'}</small>
          <strong>유료 토큰 / 비용</strong>
        </div>
        <button type="button" onClick={()=>refreshLlmUsage()}>
          ↻ 새로고침
        </button>
      </div>

      <div className="llm-usage-filter">
        <label>
          <span>AgentStudio 조회</span>
          <select
            value={llmUsageScope}
            onChange={e=>setLlmUsageScope(e.target.value)}
          >
            <option value="today">오늘 전체</option>
            <option value="all">전체 누적</option>
            <option value="month">월별 선택</option>
            <option value="day">일별 선택</option>
          </select>
        </label>
        {llmUsageScope==='month'&&<label>
          <span>월</span>
          <input
            type="month"
            value={llmUsageMonth}
            onChange={e=>setLlmUsageMonth(e.target.value)}
          />
        </label>}
        {llmUsageScope==='day'&&<label>
          <span>날짜</span>
          <input
            type="date"
            value={llmUsageDate}
            onChange={e=>setLlmUsageDate(e.target.value)}
          />
        </label>}
        <small>{studioLabel}</small>
      </div>

      <div className="llm-usage-groups">
        <div className="llm-usage-group">
          <b>현재 Agent / 프로젝트 (오늘)</b>
          <div><span>Input</span><strong>{formatTokenCount(projectUsage.input_tokens)}</strong></div>
          <div><span>Cached Input</span><strong>{formatTokenCount(projectUsage.cached_input_tokens)}</strong></div>
          <div><span>Output</span><strong>{formatTokenCount(projectUsage.output_tokens)}</strong></div>
          <div><span>Total</span><strong>{formatTokenCount(projectUsage.total_tokens)}</strong></div>
          <div className="cost"><span>총 추정 비용</span><strong>{formatUsd(projectUsage.cost_usd)}</strong></div>
        </div>

        <div className="llm-usage-group daily">
          <b>{studioLabel}</b>
          <div><span>Input</span><strong>{formatTokenCount(studioUsage.input_tokens)}</strong></div>
          <div><span>Cached Input</span><strong>{formatTokenCount(studioUsage.cached_input_tokens)}</strong></div>
          <div><span>Output</span><strong>{formatTokenCount(studioUsage.output_tokens)}</strong></div>
          <div><span>Total</span><strong>{formatTokenCount(studioUsage.total_tokens)}</strong></div>
          <div className="cost"><span>선택 기간 총 추정 비용</span><strong>{formatUsd(studioUsage.cost_usd)}</strong></div>
        </div>
      </div>

      <small className="llm-usage-note">
        {llmUsageSummary?.pricing_note
          || 'API token usage를 기준으로 추정 비용을 계산합니다.'}
      </small>
    </div>
  }


  useEffect(()=>{
    if(
      screen==='WORKSPACE'
      && (
        workspaceTab==='RUN'
        || workspaceTab==='REPORT'
        || workspaceTab==='ARCHITECTURE'
      )
    ){
      refreshLlmUsage()
    }
    if(screen==='WORKSPACE'&&workspaceTab==='LLM'){
      refreshLlmCatalog()
    }
  },[screen,workspaceTab,root,llmUsageScope,llmUsageDate,llmUsageMonth])


  const getWorkflowReportState=()=>{
    const state=workflow?.state||workflow||{}
    const packageResult=state?.package_result||{}
    const testResult=state?.test_result||{}
    const targetWorkflow=state?.target_agent_workflow
      || targetWorkflowPreview?.target_agent_workflow
      || {}
    const requirementSpec=state?.requirement_spec
      || targetWorkflowPreview?.requirement_spec
      || {}
    const capabilityPlan=state?.capability_plan
      || targetWorkflowPreview?.capability_plan
      || {}
    const toolMcpPlan=state?.tool_mcp_plan
      || targetWorkflowPreview?.tool_mcp_plan
      || {}
    const architecture=state?.agent_architecture
      || targetWorkflowPreview?.agent_architecture
      || {}

    return {
      state,
      status:state?.status||'NOT_STARTED',
      packageResult,
      testResult,
      targetWorkflow,
      requirementSpec,
      capabilityPlan,
      toolMcpPlan,
      architecture,
      settingsPlan:state?.settings_plan||packageResult?.settings_plan||{},
      settingsValidation:state?.settings_validation_result||packageResult?.settings_validation||{},
      settingsGeneration:state?.settings_generation_result||{},
      createdFiles:packageResult?.created_files||[],
      modifiedFiles:packageResult?.modified_files||[],
      debugHistory:state?.debug_history||[],
      debugIteration:Number(state?.debug_iteration||0),
      testCommand:packageResult?.test_command||state?.test_command||'python -m compileall .',
      testReturncode:
        packageResult?.test_returncode
        ?? testResult?.returncode
        ?? null
    }
  }

  const renderWorkspaceScreen=()=> <div
    ref={workspaceLayoutRef}
    className={`ux-workspace workspace-panel-layout ${workspaceLeftCollapsed?'workspace-left-collapsed':''} ${workspaceRightCollapsed?'workspace-right-collapsed':''} ${workspaceResizeSide?'workspace-resizing':''}`}
    style={{
      '--workspace-left-user-width':`${workspaceLeftWidth}px`,
      '--workspace-right-user-width':`${workspaceRightWidth}px`,
      '--workspace-bottom-user-height':`${workspaceBottomHeight}px`,
    }}
  >
    {projectLoadProgress.active&&<div className={projectLoadProgress.failed?'project-load-progress failed':'project-load-progress'}>
      <div className="project-load-progress-head">
        <strong>{projectLoadProgress.message}</strong>
        <span>{projectLoadProgress.percent}%</span>
      </div>
      <div className="project-load-progress-track">
        <div className="project-load-progress-fill" style={{width:`${projectLoadProgress.percent}%`}} />
      </div>
    </div>}
    <aside className="workspace-project-panel" aria-hidden={workspaceLeftCollapsed}>
      {workspaceTab==='DESIGN'?<>
        <div className="design-left-panel">
          <div className="unified-design-title">신규 Agent 설계</div>

          {[
            ['01','목적','어떤 Agent를 만들지'],
            ['02','기능','핵심 기능과 사용자 흐름'],
            ['03','MCP / Tool','필요한 외부 도구'],
            ['04','실행 환경','경로와 모델'],
            ['05','확인','프로젝트 생성']
          ].map((s,i)=><div
            className={`builder-step ${i===0||builderStarted?'on':''}`}
            key={s[0]}
          >
            <b>{s[0]}</b>
            <div>
              <strong>{s[1]}</strong>
              <small>{s[2]}</small>
            </div>
          </div>)}

          <div className="builder-tip">
            <strong>질문 방식</strong>
            <span>
              AgentStudio는 여러 질문을 한꺼번에 하지 않습니다.
              답변을 확인한 뒤 다음 질문 하나를 이어갑니다.
            </span>
          </div>
        </div>
      </>:<>

      <div className="panel-title-row">
        <strong>프로젝트</strong>
        <button onClick={startNewProject}>＋ 새 프로젝트</button>
      </div>
      <input className="project-search" value={projectSearch}
        onChange={e=>setProjectSearch(e.target.value)} placeholder="프로젝트 검색..."/>
      <div className="project-filter-tabs">
        <button
          className={projectFilter==='ALL'?'active':''}
          onClick={()=>changeProjectFilter('ALL')}
        >전체</button>
        <button
          className={projectFilter==='RECENT'?'active':''}
          onClick={()=>changeProjectFilter('RECENT')}
        >최근</button>
        <button
          className={projectFilter==='FAVORITE'?'active':''}
          onClick={()=>changeProjectFilter('FAVORITE')}
        >즐겨찾기</button>
      </div>

      <div className={projectListLoading?'project-list-status loading':'project-list-status'}>
        <div>
          {projectListLoading?'DB 프로젝트 목록 불러오는 중...':projectListStatus}
        </div>
        <div className="project-db-path">
          연결 경로: Frontend → FastAPI → PostgreSQL
          <br/>
          API 주소: {runtimeInfo().apiBase}
        </div>
        {projectListLogPath&&<div className="project-log-path">
          <strong>로그 전체 경로</strong>
          <code>{projectListLogPath}</code>
        </div>}
      </div>
      <div className="project-list-scroll">
        {filteredProjects.length===0&&<div className="empty-mini">
          {projectListLoading
            ? 'DB 프로젝트 목록을 불러오는 중입니다.'
            : projectList.length===0
              ? 'DB에 저장된 프로젝트가 없습니다.'
              : projectFilter==='RECENT'
                ? '최근 사용 기록이 있는 프로젝트가 없습니다.'
                : projectFilter==='FAVORITE'
                  ? '즐겨찾기 프로젝트가 없습니다.'
                  : '조건에 맞는 프로젝트가 없습니다.'}
        </div>}
        {filteredProjects.map(p=><button key={p.id}
          className={selectedProjectId===p.id?'project-list-item active':'project-list-item'}
          onClick={()=>loadProject(p.id)}>
          <span className="project-icon">▣</span>
          <div className="project-item-main">
            <strong>{p.name}</strong>
            <small>{p.project_root}</small>
            {p.last_opened_at&&<em>
              최근 {new Date(p.last_opened_at).toLocaleString()}
            </em>}
          </div>
          <span
            className={p.is_favorite?'project-favorite active':'project-favorite'}
            title={p.is_favorite?'즐겨찾기 해제':'즐겨찾기 추가'}
            onClick={e=>toggleProjectFavorite(p,e)}
          >★</span>
        </button>)}
      </div>
      <div className="project-git-card">
        <div className="project-git-head">
          <strong>Git 연결</strong>
          <button
            type="button"
            onClick={()=>loadGitInfo()}
            disabled={gitInfoLoading||!root}
            title="Git 상태 새로고침"
          >
            {gitInfoLoading?'...':'↻'}
          </button>
        </div>

        {!root&&<div className="project-git-empty">프로젝트를 선택하세요.</div>}

        {root&&!gitInfo&&
          <div className="project-git-empty">
            Git 정보를 확인하는 중입니다.
          </div>
        }

        {gitInfo&&gitInfo.is_git===false&&
          <div className="project-git-empty">
            <span className="git-dot off"/>
            {gitInfo.message||'Git 저장소가 아닙니다.'}
          </div>
        }

        {gitInfo?.is_git===true&&<>
          <div className="project-git-row">
            <span>상태</span>
            <strong className={gitInfo.clean?'git-ok':'git-warn'}>
              {gitInfo.clean?'Clean':`${gitInfo.changed_count}개 변경`}
            </strong>
          </div>

          <div className="project-git-row">
            <span>브랜치</span>
            <code title={gitInfo.branch||''}>{gitInfo.branch||'-'}</code>
          </div>

          <div className="project-git-row">
            <span>HEAD</span>
            <code>{gitInfo.head||'-'}</code>
          </div>

          <div className="project-git-row">
            <span>동기화</span>
            <strong>
              {gitInfo.sync_status==='up-to-date'&&'최신'}
              {gitInfo.sync_status==='ahead'&&`Ahead ${gitInfo.ahead}`}
              {gitInfo.sync_status==='behind'&&`Behind ${gitInfo.behind}`}
              {gitInfo.sync_status==='diverged'&&`Ahead ${gitInfo.ahead} / Behind ${gitInfo.behind}`}
            </strong>
          </div>

          <div className="project-git-origin">
            <span>origin</span>
            <code title={gitInfo.origin||''}>
              {gitInfo.origin||'원격 저장소 없음'}
            </code>
          </div>
        </>}

        {gitInfo?.is_git===true&&<>
          <div className="git-commit-box">
            <input
              value={gitCommitMessage}
              onChange={e=>setGitCommitMessage(e.target.value)}
              placeholder="커밋 메시지"
              disabled={!!gitActionBusy}
            />
          </div>

          <div className="git-action-grid">
            <button type="button" onClick={()=>runGitAction('status')} disabled={!!gitActionBusy}>상태</button>
            <button type="button" onClick={()=>runGitAction('fetch')} disabled={!!gitActionBusy}>Fetch</button>
            <button type="button" onClick={()=>runGitAction('pull')} disabled={!!gitActionBusy}>Pull</button>
            <button type="button" onClick={()=>runGitAction('add')} disabled={!!gitActionBusy}>Add</button>
            <button type="button" onClick={()=>runGitAction('commit')} disabled={!!gitActionBusy}>Commit</button>
            <button type="button" onClick={()=>runGitAction('push')} disabled={!!gitActionBusy}>Push</button>
            <button type="button" className="primary" onClick={()=>runGitAction('sync')} disabled={!!gitActionBusy}>
              {gitActionBusy==='sync'?'업로드 중...':'수정파일 올리기'}
            </button>
            <button type="button" onClick={()=>runGitAction('log')} disabled={!!gitActionBusy}>로그</button>
            <button type="button" onClick={()=>runGitAction('diff')} disabled={!!gitActionBusy}>Diff</button>
          </div>

          {gitActionResult&&<div className={gitActionResult.ok?'git-action-result ok':'git-action-result failed'}>
            <strong>
              {gitActionResult.ok?'Git 작업 완료':'Git 작업 실패'}
              {gitActionResult.action?` · ${gitActionResult.action}`:''}
            </strong>
            {gitActionResult.stdout&&<pre>{gitActionResult.stdout}</pre>}
            {gitActionResult.stderr&&<pre>{gitActionResult.stderr}</pre>}
          </div>}
        </>}

      </div>

      <div className="quick-start-box">
        <SectionTitle title="빠른 시작"/>
        <button onClick={startNewProject}>＋ 새 Agent 만들기</button>
        <button onClick={()=>{setScreen('MCP');refreshMcp()}}>◉ MCP 도구 확인</button>
        <button onClick={()=>location.href='/system'}>⚙ 시스템 진단</button>
      </div>
    
      </>}
    </aside>

    {!workspaceLeftCollapsed&&<div
      className={`workspace-panel-resizer workspace-panel-resizer-left ${workspaceResizeSide==='left'?'active':''}`}
      role="separator"
      aria-orientation="vertical"
      aria-label="좌측 영역 너비 조절"
      title="드래그하여 좌측 영역 너비 조절"
      onPointerDown={event=>beginWorkspacePanelResize('left',event)}
    />}

    <main className={`workspace-main workspace-tab-${workspaceTab.toLowerCase()} ${
      ['RUN','REPORT','ARCHITECTURE','LLM'].includes(workspaceTab)
        ? 'compact-workspace result-only-workspace'
        : workspaceTab==='CODE'&&!isBinaryPreviewFile(selected)
          ? 'workspace-with-bottom-tools code-tools-workspace'
          : 'workspace-clean-design'
    } ${workspaceBottomCollapsed?'workspace-bottom-collapsed':''} ${workspaceBottomResizing?'workspace-bottom-resizing':''}`}>
      <div className="workspace-tabs workspace-tabs-with-panel-controls">
        <button
          type="button"
          className={`workspace-panel-toggle workspace-panel-toggle-left ${workspaceLeftCollapsed?'collapsed':''}`}
          onClick={()=>setWorkspaceLeftCollapsed(v=>!v)}
          title={workspaceLeftCollapsed?'좌측 영역 열기':'좌측 영역 닫기'}
          aria-label={workspaceLeftCollapsed?'좌측 영역 열기':'좌측 영역 닫기'}
          aria-pressed={!workspaceLeftCollapsed}
        >
          <span aria-hidden="true">{workspaceLeftCollapsed?'▶':'◀'}</span>
        </button>
        <div className="workspace-tab-list">
          {[
            ['DESIGN','에이전트 설계'],
            ['WORKFLOW','워크플로우'],
            ['CODE','코드 편집'],
            ['RUN','실행 결과'],
            ['REPORT','분석 리포트'],
            ['ARCHITECTURE','아키텍처'],
            ['LLM','LLM 리스트']
          ].map(([k,t])=><button key={k}
            className={workspaceTab===k?'active':''}
            onClick={()=>setWorkspaceTab(k)}>{t}</button>)}
        </div>
        <button
          type="button"
          className={`workspace-panel-toggle workspace-panel-toggle-right ${workspaceRightCollapsed?'collapsed':''}`}
          onClick={()=>setWorkspaceRightCollapsed(v=>!v)}
          title={workspaceRightCollapsed?'우측 영역 열기':'우측 영역 닫기'}
          aria-label={workspaceRightCollapsed?'우측 영역 열기':'우측 영역 닫기'}
          aria-pressed={!workspaceRightCollapsed}
        >
          <span aria-hidden="true">{workspaceRightCollapsed?'◀':'▶'}</span>
        </button>
      </div>

      <div className={
        ['RUN','REPORT','ARCHITECTURE','LLM'].includes(workspaceTab)
          ? 'workspace-top-pane compact-result-pane'
          : 'workspace-top-pane'
      }>
        {workspaceTab==='DESIGN'&&<div className="unified-agent-design">
          <section className="unified-design-chat">
            <div className="builder-chat-head">
              <div>
                <span className="ai-avatar">AI</span>
                <div>
                  <strong>Agent 설계 인터뷰</strong>
                  <small>{aiInterviewLabel}</small>
                </div>
              </div>

              <div className="builder-head-actions">
                <button
                  type="button"
                  className="builder-workflow-button"
                  onClick={()=>{
                    const request=
                      workflowReq
                      ||buildRequirementRequestFromCollectedInfo()
                      ||chat.find(x=>x.role==='user')?.content
                      ||''

                    if(request){
                      saveRequirementDraft()
                      setRoot(newAgentProjectRoot||root)
                      setWorkspaceTab('WORKFLOW')
                      setWorkflowView('TARGET')
                      previewTargetWorkflow(request)
                    }else{
                      setTargetWorkflowError(
                        '먼저 만들 Agent의 요구사항을 입력하세요.'
                      )
                    }
                  }}
                >
                  ◇ Workflow 보기
                </button>
                <span className="live-dot">● 대화형 수집</span>
              </div>
            </div>

            <div className="builder-messages unified">
              {chat.map((m,i)=><div
                key={i}
                className={`builder-msg ${m.role}`}
              >
                <span>{m.role==='assistant'?'AI':'나'}</span>
                <div>{m.content}</div>
              </div>)}

              {busy&&<div className="builder-msg assistant">
                <span>AI</span>
                <div>답변을 분석하고 다음 질문을 준비하고 있습니다...</div>
              </div>}

              <div
                ref={builderMessagesEndRef}
                className="builder-messages-end"
                aria-hidden="true"
              />
            </div>

            <div className="builder-input unified">
              <textarea
                value={input}
                onChange={e=>setInput(e.target.value)}
                onKeyDown={e=>{
                  if(e.key==='Enter'&&!e.shiftKey){
                    e.preventDefault()
                    sendBuilderAnswer()
                  }
                }}
                placeholder="현재 질문에 답해주세요. Shift+Enter로 줄바꿈"
              />
              <button
                onClick={sendBuilderAnswer}
                disabled={busy||!input.trim()}
              >
                답변 보내기
              </button>
            </div>
          </section>
        </div>}

        {workspaceTab==='WORKFLOW'&&<div className="workflow-page visual-workflow-page">
          <div className="workflow-page-head visual">
            <div>
              <span className="workflow-eyebrow">THEANOVA AGENT FACTORY MAP</span>
              <h2>Workflow 설계도</h2>
              <p>단계를 나열하는 화면이 아니라, Agent가 어떻게 설계되고 움직이는지 한눈에 보는 구조도입니다.</p>
            </div>
            <button type="button" onClick={loadWorkflowDefinition}>↻ 새로고침</button>
          </div>

          <div className="workflow-view-tabs visual">
            <button
              type="button"
              className={workflowView==='STUDIO'?'active':''}
              onClick={()=>setWorkflowView('STUDIO')}
            >
              <span>◇</span>
              <div><strong>AgentStudio 제작 흐름</strong><small>Agent Factory 전체 공정</small></div>
            </button>
            <button
              type="button"
              className={workflowView==='TARGET'?'active target':''}
              onClick={()=>setWorkflowView('TARGET')}
            >
              <span>⇢</span>
              <div><strong>개발 대상 Agent 흐름</strong><small>실제 업무 수행 Workflow</small></div>
            </button>
          </div>

          {workflowView==='STUDIO'&&<div className="workflow-canvas-card visual-factory-canvas">
            <div className="workflow-section-head visual">
              <div>
                <span className="section-visual-icon">◇</span>
                <div>
                  <strong>THEANOVA AgentStudio 제작 Workflow</strong>
                  <small>자연어 요구를 실행 가능한 Agent 프로그램으로 만드는 전체 제작 공정</small>
                </div>
              </div>
              <span className="workflow-type-badge">AGENT FACTORY</span>
            </div>

            <FactoryWorkflowDiagram definition={workflowDefinition}/>
          </div>}

          {workflowView==='TARGET'&&<div className="workflow-canvas-card visual-target-canvas">
            <div className="workflow-section-head visual">
              <div>
                <span className="section-visual-icon target">⇢</span>
                <div>
                  <strong>{targetWorkflowPreview?.target_agent_workflow?.name||'개발 대상 Agent Workflow'}</strong>
                  <small>실제 사용자가 Agent를 실행했을 때 처리되는 업무 순서</small>
                </div>
              </div>
              <span className="workflow-type-badge target">TARGET AGENT</span>
            </div>

            <div className="target-workflow-request visual">
              <div className="target-request-icon">✦</div>
              <textarea
                value={workflowReq}
                onChange={e=>setWorkflowReq(e.target.value)}
                placeholder="예: 유튜브 영상을 자동 업로드하는 에이전트를 만들어줘"
              />
              <button
                type="button"
                onClick={()=>previewTargetWorkflow()}
                disabled={targetWorkflowLoading||!workflowReq.trim()}
              >
                {targetWorkflowLoading
                  ? '분석 중...'
                  : agentBuildStage==='WORKFLOW_READY'
                    ? '◇ Workflow 다시 설계'
                    : '◇ Workflow 설계'}
              </button>
            </div>

            {workflowProgress.active&&<div className="workflow-progress-card">
              <div className="workflow-progress-head">
                <div>
                  <span className="workflow-progress-pulse">●</span>
                  <div>
                    <strong>{workflowProgress.stage}</strong>
                    <small>{workflowProgress.detail}</small>
                  </div>
                </div>
                <b>{workflowProgress.percent}%</b>
              </div>

              <div
                className="workflow-progress-track"
                role="progressbar"
                aria-label="Workflow 설계 진행률"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={workflowProgress.percent}
              >
                <div
                  className="workflow-progress-fill"
                  style={{width:`${workflowProgress.percent}%`}}
                />
              </div>

              <div className="workflow-progress-stages">
                {[
                  ['요구사항',5],
                  ['AI 설계',18],
                  ['응답 대기',45],
                  ['검증',90],
                  ['완료',100]
                ].map(([label,threshold])=><span
                  key={label}
                  className={
                    workflowProgress.percent>=threshold
                      ? 'done'
                      : ''
                  }
                >
                  <i></i>{label}
                </span>)}
              </div>
            </div>}

            {targetWorkflowError&&<div className="workflow-error">{targetWorkflowError}</div>}

            {targetWorkflowQuality&&<div className={`workflow-quality-bar ${targetWorkflowQuality.warning?'warning':'ok'}`}>
              <div>
                <span>{targetWorkflowQuality.warning?'!':'✓'}</span>
                <div>
                  <strong>Workflow 요구사항 반영 검사</strong>
                  <small>
                    단계 {targetWorkflowQuality.step_count}개 ·
                    분기 {targetWorkflowQuality.has_branch?'있음':'없음'} ·
                    재시도 {targetWorkflowQuality.has_retry?'있음':'없음'} ·
                    실패처리 {targetWorkflowQuality.has_failure_policy?'있음':'없음'}
                  </small>
                </div>
              </div>
              {targetWorkflowQuality.warning&&<b>{targetWorkflowQuality.warning}</b>}
            </div>}

            <TargetWorkflowDiagram workflow={targetWorkflowPreview?.target_agent_workflow}/>
          </div>}
        </div>}

        <div className={
          workspaceTab==='CODE'
            ? 'full-code-pane persistent-code-editor visible'
            : 'full-code-pane persistent-code-editor hidden'
        }>
          <div className="file-path-bar">{selected||'파일을 선택하세요.'}</div>
          
          <div className="code-editor-stack">
<div className="code-file-tabs-shell">
            <button
              type="button"
              className={
                focusOwner==='editor'
                  ? 'editor-focus-indicator active editor-files-menu-trigger'
                  : 'editor-focus-indicator editor-files-menu-trigger'
              }
              title="열린 파일 관리"
              onClick={(e)=>{
                e.stopPropagation()
                const rect=e.currentTarget.getBoundingClientRect()
                setEditorTabMenu(null)
                setEditorFilesMenu(prev=>
                  prev
                    ? null
                    : {
                        x:rect.left,
                        y:rect.bottom+3
                      }
                )
              }}
            >
              편집 <span className="editor-files-menu-caret">▾</span>
            </button>

            <button
              type="button"
              className="code-file-tabs-nav left"
              title="이전 열린 파일 보기"
              aria-label="열린 파일 탭을 왼쪽으로 스크롤"
              onClick={()=>scrollEditorTabs(-1)}
            >
              ‹
            </button>

            <div
              className="code-file-tabs"
              ref={editorTabsScrollRef}
              onWheel={(event)=>{
                if(Math.abs(event.deltaY)<=Math.abs(event.deltaX)) return
                event.currentTarget.scrollLeft+=event.deltaY
                event.preventDefault()
              }}
            >
              {openEditorFiles.map(path=>{
                const fileName=
                  path.replace(/\\/g,'/').split('/').pop()||path
                const active=selected===path
                const dirty=!!editorFileDirty[path]
                const pinned=pinnedEditorFiles.includes(path)

                return (
                  <div
                    key={path}
                    data-editor-path={path}
                    className={[
                      'code-file-tab',
                      active?'active':'',
                      pinned?'pinned':''
                    ].filter(Boolean).join(' ')}
                    title={getEditorFileFullPath(path)}
                    onContextMenu={(e)=>{
                      e.preventDefault()

                      setEditorTabMenu({
                        path,
                        x:e.clientX,
                        y:e.clientY
                      })
                    }}
                  >
                    <button
                      type="button"
                      className="code-file-tab-select"
                      onClick={()=>activateEditorFile(path)}
                    >
                      <span className="code-file-tab-name">
                        {fileName}
                      </span>
                      {dirty&&
                        <span
                          className="code-file-tab-dirty"
                          title="저장되지 않은 변경"
                        >
                          ●
                        </span>
                      }
                      {editorExternalState[normalizeProjectRelativePath(path)]&&
                        <span
                          className="code-file-tab-external"
                          title={editorExternalState[normalizeProjectRelativePath(path)]==='deleted'?'외부에서 파일이 삭제되었습니다.':'외부 변경이 감지되었습니다.'}
                        >
                          ↻
                        </span>
                      }
                    </button>
                    <button
                      type="button"
                      className={
                        pinned
                          ? 'code-file-tab-pin pinned'
                          : 'code-file-tab-pin'
                      }
                      onClick={(e)=>{
                        e.stopPropagation()
                        toggleEditorFilePin(path)
                      }}
                      title={pinned?'핀 고정 해제':'핀 고정'}
                      aria-pressed={pinned}
                    >
                      📌
                    </button>
                    <button
                      type="button"
                      className="code-file-tab-close"
                      onClick={(e)=>{
                        e.stopPropagation()
                        closeEditorFile(path)
                      }}
                      title="파일 닫기"
                    >
                      ×
                    </button>
                  </div>
                )
              })}
              {openEditorFiles.length===0&&
                <div className="code-file-tab-empty">
                  열린 파일이 없습니다.
                </div>
              }
            </div>

            <button
              type="button"
              className="code-file-tabs-nav right"
              title="다음 열린 파일 보기"
              aria-label="열린 파일 탭을 오른쪽으로 스크롤"
              onClick={()=>scrollEditorTabs(1)}
            >
              ›
            </button>

            <div className="code-file-actions-fixed">
              {selected?.toLowerCase?.().endsWith('.ps1')&&
                <div className="powershell-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button"
                    title="F5 · 현재 PowerShell 파일 전체 내용을 터미널에서 실행"
                    onClick={()=>runCurrentPowerShellFile({selectionOnly:false})}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button selection"
                    title="F8 · 현재 Editor에서 선택한 PowerShell 코드만 터미널에서 실행"
                    onClick={()=>runCurrentPowerShellFile({selectionOnly:true})}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {activeTerminal?.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={()=>interruptTerminal(activeTerminalId)}>■ 실행 정지</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.py')&&
                <div className="powershell-editor-actions python-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button python"
                    title="F5 · 현재 Python 파일 전체 Editor 내용을 프로젝트 Python 환경에서 실행"
                    onClick={()=>runCurrentPythonFile({selectionOnly:false})}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button python selection"
                    title="F8 · 현재 Editor에서 선택한 Python 코드만 지속형 Python 세션에서 실행"
                    onClick={()=>runCurrentPythonFile({selectionOnly:true})}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {pythonExecutionState.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={stopPythonExecution}>■ 실행 정지</button>}
                </div>
              }
              {isNotebookFile(selected)&&!editorLoadErrors[selected]&&
                <div className="powershell-editor-actions notebook-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button python"
                    title="F5 · Notebook의 모든 Python Code 셀을 위에서부터 순서대로 실행"
                    onClick={()=>notebookEditorControllerRef.current?.runAll?.()}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button python selection"
                    title="현재 선택된 Notebook Code 셀 전체 실행"
                    onClick={()=>notebookEditorControllerRef.current?.runActiveCell?.()}
                  >
                    ▶ 셀 실행
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button python selection"
                    title="F8 · 현재 Notebook Code 셀에서 선택한 Python 코드만 실행"
                    onClick={()=>notebookEditorControllerRef.current?.runSelection?.()}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {pythonExecutionState.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={()=>notebookEditorControllerRef.current?.stopExecution?.()}>■ 실행 정지</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.cmd')&&
                <div className="powershell-editor-actions cmd-editor-actions">
                  <button
                    type="button"
                    className="powershell-run-button cmd"
                    title="F5 · 현재 CMD 파일 실행"
                    onClick={runCurrentCmdFile}
                    disabled={cmdExecution.busy}
                  >
                    {cmdExecution.busy?'실행 중…':'▶ 실행'} <span className="editor-run-shortcut">F5</span>
                  </button>
                  {cmdExecution.busy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={stopCurrentCmdFile}>■ 실행 정지</button>}
                </div>
              }
              {selected?.toLowerCase?.().endsWith('.sql')&&
                <div className="powershell-editor-actions sql-editor-actions">
                  <span className={sqlConnectionStatus?.connected?'sql-connection-chip connected':'sql-connection-chip'}>
                    {sqlConnectionStatus?.connected?'● DB 연결됨':'○ DB 연결 필요'}
                  </span>
                  <button
                    type="button"
                    className="powershell-run-button sql"
                    title="F5 · 현재 SQL 파일 전체 실행"
                    onClick={()=>runSqlEditor({selectionOnly:false})}
                    disabled={sqlQueryBusy}
                  >
                    ▶ 전체 실행 <span className="editor-run-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="powershell-run-button sql selection"
                    title="F8 · 현재 선택한 SQL만 실행"
                    onClick={()=>runSqlEditor({selectionOnly:true})}
                    disabled={sqlQueryBusy}
                  >
                    ▣ 선택 실행 <span className="editor-run-shortcut">F8</span>
                  </button>
                  {sqlQueryBusy&&<button type="button" className="powershell-run-button execution-stop-button" onClick={stopSqlExecution}>■ 실행 정지</button>}
                </div>
              }
            </div>
          </div>

          {editorFilesMenu&&
            <div
              className="editor-tab-context-menu editor-files-actions-menu"
              style={{
                left:editorFilesMenu.x,
                top:editorFilesMenu.y
              }}
              onMouseDown={e=>e.stopPropagation()}
            >
              <button
                type="button"
                onClick={closeAllEditorFiles}
                disabled={openEditorFiles.length===0}
              >
                열린 파일 모두 닫기
              </button>
              <button
                type="button"
                onClick={closeUnpinnedEditorFiles}
                disabled={!openEditorFiles.some(
                  path=>!pinnedEditorFiles.includes(path)
                )}
              >
                핀 고정되지 않은 파일 모두 닫기
              </button>
            </div>
          }


          {editorTabMenu&&
            <div
              className="editor-tab-context-menu"
              style={{
                left:editorTabMenu.x,
                top:editorTabMenu.y
              }}
              onMouseDown={e=>e.stopPropagation()}
            >
              <button
                type="button"
                onClick={()=>
                  toggleEditorFilePin(
                    editorTabMenu.path
                  )
                }
              >
                {pinnedEditorFiles.includes(editorTabMenu.path)
                  ? '핀 고정 해제'
                  : '핀 고정'}
              </button>
              <button
                type="button"
                onClick={()=>
                  copyEditorFileFullPath(
                    editorTabMenu.path
                  )
                }
              >
                전체 경로 복사
              </button>
            </div>
          }

{editorLoadErrors[selected]
            ? <div className="editor-load-error-shell">
                <div className="editor-load-error-card">
                  <span className="editor-load-error-icon">!</span>
                  <div>
                    <strong>파일을 불러오지 못했습니다.</strong>
                    <p>{editorLoadErrors[selected]?.message||'파일 읽기 오류가 발생했습니다.'}</p>
                    <code>{selected}</code>
                    <small>오류 내용은 파일 본문에 넣지 않았으며 저장도 차단되어 원본 파일을 보호합니다.</small>
                    <button type="button" onClick={()=>openFile(selected)}>↻ 다시 불러오기</button>
                  </div>
                </div>
              </div>
            : codeDiffReview
            ? <div className="code-diff-review-shell">
                <div className="code-diff-review-toolbar">
                  <div>
                    <strong>AI 변경 비교</strong>
                    <span>{codeDiffReview.path}</span>
                  </div>
                  <div className="code-diff-review-actions">
                    <button type="button" className="apply" onClick={applyCodeEditProposal}>변경 적용</button>
                    <button type="button" onClick={cancelCodeDiffReview}>취소</button>
                  </div>
                </div>
                <DiffEditor
                  className="main-monaco-editor code-diff-editor"
                  height="100%"
                  original={codeDiffReview.original}
                  modified={codeDiffReview.modified}
                  language={getEditorLanguage(codeDiffReview.path)}
                  theme="vs-dark"
                  options={{
                    readOnly:true,
                    originalEditable:false,
                    renderSideBySide:true,
                    automaticLayout:true,
                    minimap:{enabled:false},
                    fontSize:13,
                    scrollBeyondLastLine:false,
                    renderOverviewRuler:true
                  }}
                />
              </div>
            : isPdfFile(selected)
              ? <PdfViewer
                  filePath={selected}
                  projectRoot={root||activeWorkspaceRoot}
                  revision={pdfPreviewRevision[normalizeProjectRelativePath(selected)]||0}
                />
              : isPresentationFile(selected)
              ? <PresentationViewer
                  filePath={selected}
                  projectRoot={root||activeWorkspaceRoot}
                  revision={presentationPreviewRevision[normalizeProjectRelativePath(selected)]||0}
                />
              : isNotebookFile(selected)
              ? <NotebookEditor
                  value={code}
                  filePath={selected}
                  projectRoot={root}
                  onChange={v=>updateActiveEditorCode(v)}
                  onExecutePython={executeNotebookPythonCode}
                  onStopPython={stopPythonExecution}
                  controllerRef={notebookEditorControllerRef}
                  onEditorFocus={()=>setFocusOwnerSafe('editor')}
                />
              : <Editor
            beforeMount={(monaco)=>{
              const ts=monaco.languages.typescript
              const sharedCompilerOptions={
                target:ts.ScriptTarget.ES2022 ?? ts.ScriptTarget.Latest,
                allowNonTsExtensions:true,
                allowJs:true,
                checkJs:false,
                moduleResolution:ts.ModuleResolutionKind.NodeJs ?? ts.ModuleResolutionKind.Node10,
                module:ts.ModuleKind.ESNext ?? ts.ModuleKind.CommonJS,
                jsx:ts.JsxEmit.ReactJSX ?? ts.JsxEmit.React,
                esModuleInterop:true,
                allowSyntheticDefaultImports:true
              }

              ts.typescriptDefaults.setEagerModelSync(true)
              ts.javascriptDefaults.setEagerModelSync(true)
              ts.typescriptDefaults.setCompilerOptions(sharedCompilerOptions)
              ts.javascriptDefaults.setCompilerOptions(sharedCompilerOptions)
              ts.typescriptDefaults.setDiagnosticsOptions({
                noSyntaxValidation:false,
                noSemanticValidation:true,
                noSuggestionDiagnostics:false
              })
              ts.javascriptDefaults.setDiagnosticsOptions({
                noSyntaxValidation:false,
                noSemanticValidation:true,
                noSuggestionDiagnostics:false
              })
            }}
            onMount={(editor,monaco)=>{
              editorInstanceRef.current=editor

              const model=editor.getModel()
              const expectedLanguage=getEditorLanguage(selected)
              if(model&&expectedLanguage){
                monaco.editor.setModelLanguage(model,expectedLanguage)
              }

              editor.onDidFocusEditorText(()=>{
                setFocusOwnerSafe('editor')
              })

              editor.onDidBlurEditorText(()=>{
                if(focusOwnerRef.current!=='terminal'){
                  focusOwnerRef.current='editor'
                }
              })
            }}
            className="main-monaco-editor"
            height="100%"
            path={getEditorModelPath(root,selected)}
            language={getEditorLanguage(selected)}
            value={code}
            onChange={v=>updateActiveEditorCode(v)}
            theme="vs-dark"
            options={{
              minimap:{enabled:false},
              fontSize:13,
              automaticLayout:true,
              tabSize:2,
              insertSpaces:true,
              detectIndentation:true,
              formatOnPaste:true,
              bracketPairColorization:{enabled:true},
              guides:{bracketPairs:true},
              suggestOnTriggerCharacters:true,
              quickSuggestions:{other:true,comments:false,strings:true}
            }}
          />}

          </div>
        </div>

        {workspaceTab==='RUN'&&(()=>{
          const r=getWorkflowReportState()
          const testPassed=r.testReturncode===0
          const testKnown=r.testReturncode!==null&&r.testReturncode!==undefined

          return <div className="execution-dashboard">
            <div className="dashboard-hero execution">
              <div>
                <span className="dashboard-eyebrow">AGENT FACTORY EXECUTION</span>
                <h2>실행 결과</h2>
                <p>Agent 제작 Workflow의 실행·테스트·파일 변경·디버그 상태를 실시간으로 확인합니다.</p>
              </div>
              <StatusBadge status={r.status}/>
            </div>

            {renderDevelopmentFinalStatus()}
            {renderFailureDiagnostics()}
            {renderDevelopmentProgress()}

            <div className="metric-grid execution-metrics">
              <MetricCard
                label="개발 상태"
                value={r.status}
                sub="현재 Workflow 상태"
                tone={String(r.status).includes('COMPLETED')?'success':'info'}
                icon="◆"
              />
              <MetricCard
                label="테스트"
                value={testKnown?(testPassed?'PASS':'FAIL'):'대기'}
                sub={`Exit Code ${testKnown?r.testReturncode:'-'}`}
                tone={testKnown?(testPassed?'success':'danger'):'default'}
                icon="▶"
              />
              <MetricCard
                label="생성 파일"
                value={`${r.createdFiles.length}개`}
                sub={`수정 ${r.modifiedFiles.length}개`}
                tone="info"
                icon="＋"
              />
              <MetricCard
                label="디버그"
                value={`${r.debugIteration}회`}
                sub={r.debugIteration?'자동 복구 수행':'재시도 없음'}
                tone={r.debugIteration?'warning':'default'}
                icon="↻"
              />
            </div>

            {renderLlmUsagePanel(false)}

            <div className="execution-main-grid">
              <ReportSection
                icon="▶"
                title="테스트 실행"
                subtitle="최종 실행 명령과 결과"
              >
                <KeyValueGrid items={[
                  {label:'명령',value:r.testCommand},
                  {label:'Exit Code',value:testKnown?r.testReturncode:'-'},
                  {label:'상태',value:testKnown?(testPassed?'성공':'실패'):'미실행'}
                ]}/>
                {r.testResult?.output&&
                  <pre className="execution-log">{r.testResult.output}</pre>}
              </ReportSection>

              <ReportSection
                icon="▤"
                title="파일 변경"
                subtitle="AgentStudio가 실제로 만든 파일"
              >
                <FileChangeList
                  created={r.createdFiles}
                  modified={r.modifiedFiles}
                />
              </ReportSection>
            </div>

            <div className="execution-main-grid lower">
              <ReportSection
                icon="↻"
                title="디버그 / 복구"
                subtitle="테스트 실패 시 자동 수정 기록"
              >
                {r.debugHistory.length
                  ? <div className="debug-history-list">
                      {r.debugHistory.map((item,index)=>
                        <div className="debug-history-item" key={index}>
                          <span>{String(index+1).padStart(2,'0')}</span>
                          <pre>{typeof item==='string'?item:JSON.stringify(item,null,2)}</pre>
                        </div>
                      )}
                    </div>
                  : <div className="report-empty-mini">디버그 기록이 없습니다.</div>
                }
              </ReportSection>

              <ReportSection
                icon="⌘"
                title="터미널"
                subtitle="현재 프로젝트 터미널 출력"
              >
                <pre className="execution-terminal-preview">
                  {activeTerminal?.output||'터미널 출력이 아직 없습니다.'}
                </pre>
              </ReportSection>
            </div>
          </div>
        })()}

        {workspaceTab==='REPORT'&&(()=>{
          const r=getWorkflowReportState()
          const style=codingStyleReport||{
            checked_files:0,
            pass:0,
            warning:0,
            fail:0,
            violations:[],
            ok:true
          }

          const goal=
            r.requirementSpec?.goal
            || workflowReq
            || '요구사항 정보 없음'

          const capabilities=
            r.capabilityPlan?.capabilities||[]

          const mcpDecisions=
            r.toolMcpPlan?.decisions||[]

          return <div className="analysis-report-dashboard">
            <div className="dashboard-hero report">
              <div>
                <span className="dashboard-eyebrow">AGENT DEVELOPMENT REPORT</span>
                <h2>분석 리포트</h2>
                <p>요구사항부터 Architecture, MCP, Workflow, 코드 품질, 최종 완료 상태까지 한 번에 확인합니다.</p>
              </div>
              <div className="report-hero-actions">
                <button
                  type="button"
                  onClick={()=>runProjectCodingStyleValidation(root||newAgentProjectRoot)}
                >
                  ↻ 코딩 스타일 재검증
                </button>
                <StatusBadge status={r.status}/>
              </div>
            </div>

            <div className="metric-grid report-metrics">
              <MetricCard
                label="Workflow 단계"
                value={`${(r.targetWorkflow?.steps||[]).length}개`}
                sub={`분기 ${(r.targetWorkflow?.branches||[]).length}개`}
                icon="⇢"
                tone="info"
              />
              <MetricCard
                label="MCP / Tool"
                value={`${mcpDecisions.length}개`}
                sub="연결 판단 결과"
                icon="⚙"
              />
              <MetricCard
                label="코딩 스타일"
                value={style.fail===0?'PASS':'FAIL'}
                sub={`경고 ${style.warning} · 오류 ${style.fail}`}
                icon="✓"
                tone={style.fail===0?(style.warning?'warning':'success'):'danger'}
              />
              <MetricCard
                label="최종 상태"
                value={r.status}
                sub={reportGeneratedAt?`검증 ${new Date(reportGeneratedAt).toLocaleTimeString()}`:'아직 검증 전'}
                icon="★"
                tone={String(r.status).includes('COMPLETED')?'success':'info'}
              />
            </div>

            {renderFailureDiagnostics()}
            {renderLlmUsagePanel(true)}

            <div className="report-layout">
              <ReportSection
                icon="✦"
                title="요구사항"
                subtitle="인터뷰에서 확정된 Agent 목표"
                className="span-2"
              >
                <div className="requirement-goal-box">{goal}</div>
                <KeyValueGrid items={[
                  {
                    label:'Acceptance Criteria',
                    value:`${(r.requirementSpec?.acceptance_criteria||[]).length}개`
                  },
                  {
                    label:'제약 조건',
                    value:`${(r.requirementSpec?.constraints||[]).length}개`
                  }
                ]}/>
              </ReportSection>

              <ReportSection
                icon="⬡"
                title="Agent Architecture"
                subtitle="구성 요소와 인터페이스"
              >
                <KeyValueGrid items={[
                  {label:'Components',value:`${(r.architecture?.components||[]).length}개`},
                  {label:'Interfaces',value:`${(r.architecture?.interfaces||[]).length}개`},
                  {label:'Persistence',value:`${(r.architecture?.persistence||[]).length}개`},
                  {label:'Security',value:`${(r.architecture?.security||[]).length}개`}
                ]}/>
              </ReportSection>

              <ReportSection
                icon="⇢"
                title="대상 Agent Workflow"
                subtitle="실제 업무 처리 순서"
                className="span-2"
              >
                <WorkflowMiniMap workflow={r.targetWorkflow}/>
              </ReportSection>

              <ReportSection
                icon="⚙"
                title="MCP / Tool"
                subtitle="Capability별 연결 방식"
              >
                {mcpDecisions.length
                  ? <div className="mcp-decision-list">
                      {mcpDecisions.map((item,index)=>
                        <div className="mcp-decision-row" key={index}>
                          <span>{item.execution_type||'none'}</span>
                          <div>
                            <strong>{item.capability||`Capability ${index+1}`}</strong>
                            <small>{item.reason||''}</small>
                          </div>
                        </div>
                      )}
                    </div>
                  : <div className="report-empty-mini">MCP / Tool 판단 정보가 없습니다.</div>
                }
              </ReportSection>

              <ReportSection
                icon="✣"
                title="Capabilities"
                subtitle="Agent가 가져야 할 기능"
              >
                {capabilities.length
                  ? <div className="capability-chip-list">
                      {capabilities.map((item,index)=>
                        <span key={index}>{typeof item==='string'?item:JSON.stringify(item)}</span>
                      )}
                    </div>
                  : <div className="report-empty-mini">Capability 정보가 없습니다.</div>
                }
              </ReportSection>

              <ReportSection
                icon="⚙"
                title="Settings Generator"
                subtitle="생성 대상 Agent의 설정 화면/API 생성 상태"
                className="span-2"
              >
                {r.settingsPlan?.enabled
                  ? <div className="settings-generator-report">
                      <div className="settings-generator-summary">
                        <div>
                          <span>설정 카테고리</span>
                          <strong>{(r.settingsPlan?.categories||[]).length}개</strong>
                        </div>
                        <div>
                          <span>Secret 보호</span>
                          <strong>{r.settingsPlan?.security?.never_return_secret_plaintext?'ON':'확인 필요'}</strong>
                        </div>
                        <div>
                          <span>생성 상태</span>
                          <strong>{r.settingsGeneration?.enabled===false?'불필요':'생성 대상'}</strong>
                        </div>
                        <div>
                          <span>검증</span>
                          <strong>{r.settingsValidation?.ok===true?'PASS':r.settingsValidation?.ok===false?'FAIL':'대기'}</strong>
                        </div>
                      </div>

                      <div className="settings-category-list">
                        {(r.settingsPlan?.categories||[]).map((category,index)=>
                          <div className="settings-category-card" key={category.id||index}>
                            <strong>{category.label||category.id||`설정 ${index+1}`}</strong>
                            <div>
                              {(category.fields||[]).map((field,fieldIndex)=>
                                <span key={field.key||fieldIndex}>
                                  {field.label||field.key}
                                  {field.secret&&<b>SECRET</b>}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {r.settingsValidation?.checks?.length>0&&
                        <div className="settings-validation-list">
                          {r.settingsValidation.checks.map((item,index)=>
                            <div className={item.ok?'ok':'fail'} key={index}>
                              <span>{item.ok?'✓':'!'}</span>
                              <code>{item.path||item.type}</code>
                            </div>
                          )}
                        </div>
                      }
                    </div>
                  : <div className="report-empty-mini">
                      이 Agent에는 별도 Settings UI가 필요하지 않은 것으로 설계되었습니다.
                    </div>
                }
              </ReportSection>

              <ReportSection
                icon="▤"
                title="코드 생성 결과"
                subtitle="실제 생성 및 수정 파일"
                className="span-2"
              >
                <FileChangeList
                  created={r.createdFiles}
                  modified={r.modifiedFiles}
                />
              </ReportSection>

              <ReportSection
                icon="✓"
                title="Coding Style Validation"
                subtitle="등록한 코딩 규칙 적용 여부"
                className="span-2 coding-style-report"
              >
                <div className="style-score-grid">
                  <div className="style-score success">
                    <span>PASS</span>
                    <strong>{style.pass}</strong>
                  </div>
                  <div className="style-score warning">
                    <span>WARNING</span>
                    <strong>{style.warning}</strong>
                  </div>
                  <div className="style-score danger">
                    <span>FAIL</span>
                    <strong>{style.fail}</strong>
                  </div>
                  <div className="style-score info">
                    <span>FILES</span>
                    <strong>{style.checked_files}</strong>
                  </div>
                </div>

                {style.violations?.length
                  ? <div className="style-violation-list">
                      {style.violations.slice(0,80).map((item,index)=>
                        <div className={`style-violation-row ${String(item.severity||'warning').toLowerCase()}`} key={index}>
                          <span>{String(item.severity||'warning').toUpperCase()}</span>
                          <code>{item.path||'-'}</code>
                          <strong>{item.rule_id||''}</strong>
                          <p>{item.message||''}</p>
                        </div>
                      )}
                    </div>
                  : <div className="style-clean-result">
                      <span>✓</span>
                      <div>
                        <strong>코딩 스타일 위반이 없습니다.</strong>
                        <small>검사된 파일 기준으로 Error/Warning이 발견되지 않았습니다.</small>
                      </div>
                    </div>
                }
              </ReportSection>

              <ReportSection
                icon="★"
                title="최종 완료 상태"
                subtitle="Agent Factory 완료 조건"
                className="span-2 final-status-section"
              >
                <div className={`final-status-card ${String(r.status).includes('COMPLETED')?'completed':'pending'}`}>
                  <span>{String(r.status).includes('COMPLETED')?'★':'…'}</span>
                  <div>
                    <strong>{r.status}</strong>
                    <small>
                      {String(r.status).includes('COMPLETED')
                        ? '코드 생성 · 테스트 · 패키지 · 최종 검토가 완료되었습니다.'
                        : 'Agent Factory Workflow가 아직 최종 완료 상태가 아닙니다.'}
                    </small>
                  </div>
                </div>
              </ReportSection>
            </div>
          </div>
        })()}

        {workspaceTab==='ARCHITECTURE'&&(()=>{
          const r=getWorkflowReportState()
          return <div className="analysis-report-dashboard architecture-dashboard">
            <div className="dashboard-hero report architecture-hero">
              <div>
                <span className="dashboard-eyebrow">ARCHITECTURE VISUALIZATION</span>
                <h2>아키텍처</h2>
                <p>신규 에이전트 구조와 THEANOVA AgentStudio 플랫폼 구조를 한 화면에서 비교합니다.</p>
              </div>
              <div className="report-hero-actions">
                <button type="button" onClick={()=>setWorkspaceTab('REPORT')}>↔ 분석 리포트 보기</button>
                <StatusBadge status={r.status} />
              </div>
            </div>

            <div className="metric-grid report-metrics">
              <MetricCard label="구성 요소" value={`${(r.architecture?.components||[]).length}개`} sub="신규 에이전트" icon="⬢" tone="info" />
              <MetricCard label="인터페이스" value={`${(r.architecture?.interfaces||[]).length}개`} sub="연결 지점" icon="⇄" tone="default" />
              <MetricCard label="영속성" value={`${(r.architecture?.persistence||[]).length}개`} sub="DB / 상태 저장" icon="💾" tone="warning" />
              <MetricCard label="보안" value={`${(r.architecture?.security||[]).length}개`} sub="권한 / Secret / Guardrail" icon="🔐" tone="success" />
            </div>

            <GeneratedAgentArchitecturePanel report={r} />
            <AgentStudioArchitecturePanel />
          </div>
        })()}

        {workspaceTab==='LLM'&&<LlmCatalogPanel
          catalog={llmCatalog}
          history={llmHistory}
          loading={llmCatalogLoading}
          error={llmCatalogError}
          onRefresh={refreshLlmCatalog}
        />}
      </div>

      {workspaceTab==='CODE'&&!isBinaryPreviewFile(selected)&&<div className={`workspace-bottom-control-rail ${workspaceBottomCollapsed?'collapsed':''}`}>
        {!workspaceBottomCollapsed&&<div
          className="workspace-bottom-resizer workspace-bottom-resizer-inline"
          role="separator"
          aria-orientation="horizontal"
          aria-label="하단 영역 높이 조절"
          title="위아래로 드래그하여 LLM 대화형 코드 편집/터미널 영역 높이 조절"
          onPointerDown={beginWorkspaceBottomResize}
        ><span /></div>}
        <button
          type="button"
          className={`workspace-panel-toggle workspace-panel-toggle-bottom workspace-panel-toggle-bottom-rail ${workspaceBottomCollapsed?'collapsed':''}`}
          onClick={()=>setWorkspaceBottomCollapsed(v=>!v)}
          title={workspaceBottomCollapsed?'하단 LLM/터미널 영역 열기':'하단 LLM/터미널 영역 닫기'}
          aria-label={workspaceBottomCollapsed?'하단 영역 열기':'하단 영역 닫기'}
          aria-pressed={!workspaceBottomCollapsed}
        >
          <span aria-hidden="true">{workspaceBottomCollapsed?'▲':'▼'}</span>
        </button>
      </div>}

      <div className={
        workspaceTab==='CODE'&&!isBinaryPreviewFile(selected)&&!workspaceBottomCollapsed
          ? `workspace-bottom-grid fixed-bottom-tools persistent-code-tools visible ${isSqlFile?'sql-workspace-bottom':''}`
          : 'workspace-bottom-grid fixed-bottom-tools persistent-code-tools hidden'
      }>
        {isSqlFile&&<section className="sql-results-pane">
          <div className="sql-results-tabs">
            <button type="button" className={sqlResultTab==='DATA'?'active':''} onClick={()=>setSqlResultTab('DATA')}>Data Output{sqlQueryResult?.columns?.length?` (${sqlQueryResult.row_count||0})`:''}</button>
            <button type="button" className={sqlResultTab==='MESSAGES'?'active':''} onClick={()=>setSqlResultTab('MESSAGES')}>Messages{sqlMessages.length?` (${sqlMessages.length})`:''}</button>
            <div className="sql-result-summary">
              {sqlQueryBusy?'SQL 실행 중...':sqlQueryResult?.message||'SQL을 실행하면 결과가 여기에 표시됩니다.'}
            </div>
          </div>
          <div className="sql-results-body">
            {sqlResultTab==='DATA'
              ? (sqlQueryResult?.columns?.length
                  ? <div className="sql-data-table-wrap">
                      <table className="sql-data-table">
                        <thead><tr><th className="row-index">#</th>{sqlQueryResult.columns.map((column,index)=><th key={`${column}-${index}`}>{column}</th>)}</tr></thead>
                        <tbody>{(sqlQueryResult.rows||[]).map((row,rowIndex)=><tr key={rowIndex}><td className="row-index">{rowIndex+1}</td>{row.map((cell,cellIndex)=><td key={cellIndex} title={cell===null?'NULL':String(cell)}>{cell===null?<span className="sql-null">NULL</span>:String(cell)}</td>)}</tr>)}</tbody>
                      </table>
                    </div>
                  : <div className="sql-result-empty">조회 결과가 없습니다. SELECT 문을 실행하면 표 형태로 표시됩니다.</div>)
              : <div className="sql-message-list">
                  {sqlMessages.length
                    ? sqlMessages.map((item,index)=><div className={`sql-message ${item.type||'info'}`} key={`${item.time}-${index}`}><span>{item.time}</span><p>{item.text}</p></div>)
                    : <div className="sql-result-empty">실행 메시지가 없습니다.</div>}
                </div>}
          </div>
        </section>}
        <section className={`editor-pane ux-editor-pane llm-code-chat-panel ${isSqlFile?'sql-chat-pane':''}`}>
          <div className="pane-title ux-pane-title">
            <strong>LLM 대화형 코드 편집</strong>
            <div>
              <span>{selected ? selected.split(/[\\/]/).pop() : '파일 선택 필요'}</span>

              {selected&&editorFileDirty[selected]&&
                <span className="file-save-status dirty" title="저장되지 않은 변경">●</span>
              }

              {fileSaveStatus==='저장 중'&&
                <span className="file-save-status saving">저장 중...</span>
              }

              {fileSaveStatus==='저장 완료'&&!editorFileDirty[selected]&&
                <span className="file-save-status saved">저장 완료</span>
              }

              {fileSaveStatus==='저장 실패'&&
                <span className="file-save-status failed">저장 실패</span>
              }

              <button onClick={saveFile} disabled={!selected||isBinaryPreviewFile(selected)}>상단 코드 저장</button>
            </div>
          </div>

          <div className="code-llm-side chat-only">
            <div className="code-llm-head">
              <div>
                <MiniBadge>AI</MiniBadge>
                <strong>
                  {codeEditScope==='PROJECT'
                    ? '프로젝트 전체 코딩'
                    : '선택된 파일과 대화하며 코드 수정'}
                </strong>
              </div>
              <small>
                {codeEditScope==='PROJECT'
                  ? `현재 대상 프로젝트: ${currentProjectName}`
                  : selected
                    ? `현재 대상 파일: ${selected}`
                    : '파일 단위 작업은 먼저 파일을 선택하세요.'}
              </small>
            </div>

            <div className="code-llm-chat" ref={codeEditChatRef}>
              {codeEditChat.map((m,i)=><div
                key={i}
                className={`code-edit-message ${m.role}`}
              >
                <span>{m.role==='assistant'?'AI':'나'}</span>
                <div>{m.content}</div>
              </div>)}

              {codeEditBusy&&<div className="code-edit-message assistant">
                <span>AI</span>
                <div>
                  {codeEditScope==='PROJECT'
                    ? '프로젝트 구조를 분석하고 필요한 파일 생성/수정을 진행하고 있습니다...'
                    : '현재 상단 편집기의 코드를 기준으로 수정안을 생성하고 있습니다...'}
                </div>
              </div>}

              {codeEditProposal&&<div className="code-edit-proposal proposal-ready-note">
                <div className="proposal-head">
                  <strong>AI 변경 제안 준비됨</strong>
                  <span>{codeEditProposal.path?.split(/[\\/]/).pop()||''}</span>
                </div>
                <p>우측 `AI 변경 제안` 탭에서 코드를 확인하고 Apply로 Diff 비교를 시작하세요.</p>
                <div className="proposal-actions">
                  <button className="apply" onClick={()=>{setCodeRightPanelTab('PROPOSAL');setWorkspaceRightCollapsed(false)}}>
                    우측 제안 보기
                  </button>
                </div>
              </div>}
            </div>

            <div className="code-llm-input">
              <select
                className="code-edit-scope-select"
                value={codeEditScope}
                onChange={e=>setCodeEditScope(e.target.value)}
                disabled={codeEditBusy}
                title="코드 작업 범위"
              >
                <option value="FILE">파일 단위</option>
                <option value="PROJECT">프로젝트 단위</option>
              </select>

              <textarea
                value={codeEditPrompt}
                onFocus={()=>setFocusOwnerSafe('code-chat')}
                onPointerDown={()=>setFocusOwnerSafe('code-chat')}
                onChange={e=>setCodeEditPrompt(e.target.value)}
                placeholder={
                  codeEditScope==='PROJECT'
                    ? '예: 유튜브 등록 에이전트를 만들어줘. 필요한 신규 파일도 생성해줘.'
                    : selected
                      ? '예: print hello 를 찍어줘.'
                      : '파일 단위 작업은 먼저 수정할 파일을 선택하세요.'
                }
                disabled={
                  codeEditBusy
                  || !root
                  || (codeEditScope==='FILE'&&!selected)
                }
                onKeyDown={e=>{
                  if(e.key!=='Enter') return

                  // 한글 IME 조합 중 Enter는 전송하거나 줄바꿈 처리하지 않습니다.
                  if(e.nativeEvent?.isComposing) return

                  // 파일 단위 / 프로젝트 단위 모두 Shift+Enter 또는 Alt+Enter로
                  // 현재 커서 위치에 한 줄을 추가합니다. 브라우저/OS별 Alt+Enter
                  // 기본 동작 차이를 없애기 위해 직접 개행을 삽입합니다.
                  if(e.shiftKey||e.altKey){
                    e.preventDefault()
                    e.stopPropagation()
                    const target=e.currentTarget
                    const start=Number(target.selectionStart??codeEditPrompt.length)
                    const end=Number(target.selectionEnd??start)
                    const next=`${codeEditPrompt.slice(0,start)}\n${codeEditPrompt.slice(end)}`
                    const caret=start+1
                    setCodeEditPrompt(next)
                    requestAnimationFrame(()=>{
                      try{
                        target.focus()
                        target.setSelectionRange(caret,caret)
                      }catch(_){}
                    })
                    return
                  }

                  e.preventDefault()
                  e.stopPropagation()
                  askCodeEditorLLM()
                }}
                title="Enter: 실행 · Shift+Enter / Alt+Enter: 줄바꿈"
              />

              <button
                onClick={askCodeEditorLLM}
                disabled={
                  codeEditBusy
                  || !root
                  || (codeEditScope==='FILE'&&!selected)
                  || !codeEditPrompt.trim()
                }
              >
                {codeEditScope==='PROJECT'
                  ? '프로젝트 코딩'
                  : '파일 수정'}
              </button>
            </div>
          </div>
        </section>

        <TerminalPanel
          hiddenForSql={isSqlFile}
          sessions={terminalSessions}
          activeTerminalId={activeTerminalId}
          activeTerminal={activeTerminal}
          errors={terminalErrors}
          terminalNameEditId={terminalNameEditId}
          terminalNameDraft={terminalNameDraft}
          activeTerminalProjectId={activeTerminalProjectId}
          projectTerminalSessions={projectTerminalSessions}
          completion={terminalCompletion}
          completionRef={terminalCompletionRef}
          onDismissError={sessionId=>setTerminalErrors(prev=>({...prev,[sessionId]:null}))}
          onNameDraftChange={setTerminalNameDraft}
          onSaveName={saveTerminalName}
          onCancelRename={()=>{ setTerminalNameEditId(null); setTerminalNameDraft('') }}
          onSelectTerminal={terminal=>{
            setFocusOwnerSafe('terminal')
            setActiveTerminalId(terminal.id)
            setTimeout(()=>focusXterm(terminal.id,{force:true}),0)
          }}
          onStartRename={startRenameTerminal}
          onRemoveTerminal={removeTerminal}
          onRestartTerminal={restartTerminalSession}
          onInterruptTerminal={interruptTerminal}
          onClearTerminal={clearTerminalView}
          onAddTerminal={addTerminal}
          onBindTerminalContainer={(terminal,el)=>{
            if(!el) return
            xtermContainersRef.current[terminal.id]=el
            setTimeout(async()=>{
              await ensureXtermInstance(terminal.id)
              if(
                activeTerminalId===terminal.id
                && terminal.processState!=='exited'
                && canAutoFocusTerminal()
              ){
                focusXterm(terminal.id)
              }
            },0)
          }}
          onTerminalMouseDown={terminal=>{
            if(terminal.processState==='exited') return
            setFocusOwnerSafe('terminal')
          }}
          onTerminalClick={terminal=>{
            if(terminal.processState==='exited') return
            setFocusOwnerSafe('terminal')
            focusXterm(terminal.id,{force:true})
          }}
          onCompletionHover={index=>{
            const current=terminalCompletionRef.current
            if(current?.sessionId===activeTerminalId){
              setTerminalCompletionState({...current,selectedIndex:index})
            }
          }}
          onApplyCompletion={applyTerminalCompletion}
        />
      </div>
    </main>

    {!workspaceRightCollapsed&&<div
      className={`workspace-panel-resizer workspace-panel-resizer-right ${workspaceResizeSide==='right'?'active':''}`}
      role="separator"
      aria-orientation="vertical"
      aria-label="우측 영역 너비 조절"
      title="드래그하여 우측 영역 너비 조절"
      onPointerDown={event=>beginWorkspacePanelResize('right',event)}
    />}

    <aside
      className={`workspace-info-panel ${workspaceTab==='DESIGN'?'design-info-panel':''}`}
      aria-hidden={workspaceRightCollapsed}
    >
      {workspaceTab==='DESIGN'&&<>
        <div className="info-card unified-project-config">
          <div className="summary-head">
            <div>
              <strong>프로젝트 구성</strong>
              <small>생성 전에 언제든 수정할 수 있습니다.</small>
            </div>
          </div>



          <label className="ux-field">
            <span>에이전트 이름</span>
            <input
              value={newAgentName}
              onChange={e=>setNewAgentName(e.target.value)}
              placeholder="예: YouTube MCP Agent"
            />
          </label>

          <label className="ux-field required">
            <span>프로젝트 경로</span>
            <div className="path-input-row">
              <input
                value={newAgentProjectRoot}
                onChange={e=>setNewAgentProjectRoot(e.target.value)}
                placeholder="예: F:\\Source\\repos\\Theanova\\AI\\MyAgent"
              />
              <button
                type="button"
                className="path-find-button"
                onClick={()=>
                  chooseAgentFolder(
                    setNewAgentProjectRoot,
                    newAgentProjectRoot,
                    '프로젝트 경로'
                  )
                }
              >
                경로 찾기
              </button>
            </div>
          </label>

          <button
            className="path-toggle"
            onClick={()=>setShowPathSettings(v=>!v)}
          >
            <span>고급 경로 설정</span>
            <b>{showPathSettings?'−':'＋'}</b>
          </button>

          {showPathSettings&&<div className="path-settings">
            {[
              ['Cache',newAgentCachePath,setNewAgentCachePath,'Cache 경로'],
              ['Temp',newAgentTempPath,setNewAgentTempPath,'Temp 경로'],
              ['Output',newAgentOutputPath,setNewAgentOutputPath,'Output 경로'],
              ['가상환경',newAgentVenvPath,setNewAgentVenvPath,'가상환경 경로'],
              ['공통 모델',newAgentModelsPath,setNewAgentModelsPath,'공용 모델 경로']
            ].map(([label,value,setter,title])=>
              <label className="ux-field" key={label}>
                <span>{label}</span>
                <div className="path-input-row">
                  <input
                    value={value}
                    onChange={e=>setter(e.target.value)}
                    placeholder="비우면 기본 경로 사용"
                  />
                  <button
                    type="button"
                    className="path-find-button"
                    onClick={()=>chooseAgentFolder(setter,value,title)}
                  >
                    경로 찾기
                  </button>
                </div>
              </label>
            )}
          </div>}

          <div className="path-preview compact">
            <strong>생성될 경로</strong>
            <div><span>Cache</span><code>{pathPreview(newAgentCachePath,'cache')}</code></div>
            <div><span>Temp</span><code>{pathPreview(newAgentTempPath,'temp')}</code></div>
            <div><span>Output</span><code>{pathPreview(newAgentOutputPath,'output')}</code></div>
            <div><span>Venv</span><code>{pathPreview(newAgentVenvPath,'venv')}</code></div>
            <div><span>Models</span><code>{pathPreview(newAgentModelsPath,'models')}</code></div>
          </div>
        </div>

        <div className="info-card right-agent-build-card">
          <SectionTitle title="Agent 제작 진행"/>
          <AgentBuildActionBar
            stage={agentBuildStage}
            busy={agentBuildBusy}
            message={agentBuildMessage}
            workflowEnabled={canDesignFromCollectedInfo()}
            onWorkflow={()=>{
              setWorkspaceTab('WORKFLOW')
              setWorkflowView('TARGET')
              previewTargetWorkflow()
            }}
            onCreateProject={createAgentProjectFromInterview}
            onStartDevelopment={startAgentDevelopment}
            onStop={cancelAgentDevelopment}
            compact
          />
          {renderDevelopmentFinalStatus()}
          {renderDevelopmentProgress()}
        </div>
        <div className="info-card requirement-collection-wrapper">
          <div className="requirement-collection-card active-design">
            <div className="requirement-collection-head">
              <div>
                <strong>요구사항 수집 현황</strong>
                <small>이미 확인된 내용은 다시 묻지 않고 Workflow 설계에 재사용합니다.</small>
              </div>
              <span>
                {getRequirementKeywordStatus().filter(x=>x.collected).length}
                /{getRequirementKeywordStatus().length}
              </span>
            </div>

            <div className="requirement-value-list">
              {getRequirementKeywordStatus().map(item=>
                <div
                  key={item.id}
                  className={`requirement-value-row ${item.collected?'collected':'pending'}`}
                  title={
                    item.collected
                      ? `${item.label}: ${item.value||'수집 완료'}`
                      : `${item.label}: 아직 미수집`
                  }
                >
                  <i>{item.collected?'✓':'○'}</i>
                  <span className="requirement-value-label">{item.label}</span>
                  <em>:</em>
                  <strong className="requirement-value-text">
                    {item.value||'미수집'}
                  </strong>
                  <b>
                    {item.collected?'완료':'미수집'}
                  </b>
                </div>
              )}
            </div>

            <div className="requirement-draft-info">
              <span>
                {requirementDraftRestored
                  ? '✓ 이전 요구사항 복원됨'
                  : requirementDraftSavedAt
                    ? '✓ 요구사항 자동 저장됨'
                    : '○ 요구사항 수집 중'}
              </span>
              {requirementDraftSavedAt&&
                <small>{new Date(requirementDraftSavedAt).toLocaleString()}</small>
              }
            </div>

            <div className="requirement-collection-actions">
              <button
                type="button"
                className="requirement-direct-workflow-button"
                disabled={!canDesignFromCollectedInfo()||targetWorkflowLoading}
                onClick={()=>{
                  saveRequirementDraft()
                  setRoot(newAgentProjectRoot||root)
                  setWorkspaceTab('WORKFLOW')
                  setWorkflowView('TARGET')
                  previewTargetWorkflow(
                    buildRequirementRequestFromCollectedInfo()
                  )
                }}
              >
                {targetWorkflowPreview
                  ? '◇ 저장된 요구사항으로 Workflow 다시 설계'
                  : '◇ 수집된 요구사항으로 바로 Workflow 설계'}
              </button>
            </div>

            <details className="requirement-collected-details">
              <summary>수집된 사용자 답변 보기</summary>
              <div>
                {(chat||[])
                  .filter(item=>item?.role==='user')
                  .map((item,index)=>
                    <p key={index}>{item.content}</p>
                  )}
                {!(chat||[]).some(item=>item?.role==='user')&&
                  <p>아직 사용자 답변이 없습니다.</p>
                }
              </div>
            </details>
          </div>
        </div>

      </>}

      {workspaceTab!=='DESIGN'&&workspaceTab!=='CODE'&&<>
      <div className="info-card">
        <div className="info-card-head"><strong>프로젝트 정보</strong><MiniBadge tone="green">활성</MiniBadge></div>
        <h3>{currentProjectName}</h3>
        <code>{currentProjectPath||'경로 미지정'}</code>
      </div>

      <div className="info-card">
        <SectionTitle title="프로젝트 요약"/>
        <p>{workspaceSummary}</p>
        {loadedProjectAnalysis?.tech_stack?.length>0&&<>
          <strong className="sub-label">기술 스택</strong>
          <div className="analysis-tags">
            {loadedProjectAnalysis.tech_stack.slice(0,8).map((x,i)=><span key={i}>{typeof x==='string'?x:JSON.stringify(x)}</span>)}
          </div>
        </>}
      </div>

      <div className="info-card">
        <SectionTitle title={`MCP 도구 (${mcpTools.length})`} action={<button onClick={openMcpAddDialog}>＋ 추가</button>}/>
        <div className="tool-list">
          {mcpTools.slice(0,8).map((t,i)=><div className="tool-row" key={i}>
            <span className="tool-status">●</span>
            <div><strong>{t.name||String(t)}</strong><small>{t.category||'MCP Tool'}</small></div>
          </div>)}
          {mcpTools.length===0&&<small className="muted">등록된 MCP 도구가 없습니다.</small>}
        </div>
      </div>

      </>}
      {workspaceTab==='WORKFLOW'&&
      <div className="info-card right-agent-build-card">
        <SectionTitle title="Agent 제작 진행"/>
        <AgentBuildActionBar
          stage={agentBuildStage}
          busy={agentBuildBusy}
          message={agentBuildMessage}
          workflowEnabled={canDesignFromCollectedInfo()}
          onWorkflow={()=>{
            setWorkspaceTab('WORKFLOW')
            setWorkflowView('TARGET')
            previewTargetWorkflow()
          }}
          onCreateProject={createAgentProjectFromInterview}
          onStartDevelopment={startAgentDevelopment}
          onStop={cancelAgentDevelopment}
          compact
        />
      </div>}

      {workspaceTab==='CODE'&&
      <div className="code-right-panel-shell">
        <div className={`code-right-panel-tabs ${isSqlFile?'sql-tabs':''}`} role="tablist" aria-label="코드 편집 우측 패널">
          <button
            type="button"
            className={codeRightPanelTab==='FILES'?'active':''}
            onClick={()=>setCodeRightPanelTab('FILES')}
          >프로젝트 파일</button>
          <button
            type="button"
            className={codeRightPanelTab==='PROPOSAL'?'active':''}
            onClick={()=>setCodeRightPanelTab('PROPOSAL')}
          >
            AI 변경 제안
            {codeEditProposal&&<span className="code-proposal-badge">1</span>}
          </button>
          <button
            type="button"
            className={codeRightPanelTab==='SQL_DB'?'active':''}
            onClick={()=>{setCodeRightPanelTab('SQL_DB');loadSqlWorkspaceStatus()}}
          >
            DB 연결
            <span className={sqlConnectionStatus?.connected?'sql-tab-dot connected':'sql-tab-dot'}></span>
          </button>
        </div>

        {codeRightPanelTab==='FILES'&&
        <div className="info-card files-card project-tree-card code-tab-panel">
          <div className="project-tree-head">
            <strong>프로젝트 파일 ({files.length})</strong>
            <div className="project-tree-actions">
              <button
                type="button"
                className="project-tree-icon-button"
                onClick={createProjectFolder}
                title="새 폴더"
                aria-label="새 폴더"
              >
                <span aria-hidden="true">📁</span>
              </button>
              <button
                type="button"
                className={
                  fileCreateLoading
                    ? 'project-tree-icon-button file-action-loading'
                    : 'project-tree-icon-button'
                }
                onClick={createProjectFile}
                disabled={fileCreateLoading}
                title={fileCreateLoading?'파일 생성 중':'새 파일'}
                aria-label="새 파일"
              >
                <span aria-hidden="true">
                  {fileCreateLoading?'…':'📄'}
                </span>
              </button>
              <button
                type="button"
                className="project-tree-icon-button"
                disabled={!root||!fileTreeSelected}
                onClick={()=>{
                  if(!root||!fileTreeSelected) return
                  const parts=fileTreeSelected.replace(/\\/g,'/').split('/')
                  beginRenameTreeItem({
                    path:fileTreeSelected,
                    name:parts[parts.length-1],
                    type:projectDirs.includes(fileTreeSelected)?'folder':'file'
                  })
                }}
                title={!root?'프로젝트를 먼저 선택하세요':(!fileTreeSelected?'이름을 변경할 파일/폴더를 선택하세요':'이름 변경')}
                aria-label="이름 변경"
              >
                <span aria-hidden="true">✎</span>
              </button>
            </div>
          </div>

          <div className="project-tree-help">
            클릭: 파일 열기 · Ctrl/Shift: 멀티 선택 · DEL: 삭제 · 우클릭: 메뉴 · ✎: 이름 변경
          </div>

          <div className="project-tree-view">
            {projectTree.sortedChildren?.length
              ? projectTree.sortedChildren.map(node=>renderProjectTreeNode(node,0))
              : <div className="empty-mini">프로젝트 파일이 없습니다.</div>}
          </div>

          {fileTreeContextMenu&&
            <div
              className="project-tree-context-menu"
              style={{left:fileTreeContextMenu.x,top:fileTreeContextMenu.y}}
              onMouseDown={e=>e.stopPropagation()}
            >
              <button
                type="button"
                className="danger"
                onClick={()=>requestProjectFilesDelete(fileTreeContextMenu.paths)}
              >파일 삭제</button>
            </div>
          }
        </div>}

        {codeRightPanelTab==='SQL_DB'&&
        <div className="info-card sql-connection-panel code-tab-panel">
          <div className="sql-connection-panel-head">
            <div>
              <strong>데이터베이스 연결</strong>
              <small>프로젝트별 연결 설정을 유지합니다.</small>
            </div>
            <span className={sqlConnectionStatus?.connected?'sql-status connected':'sql-status'}>
              {sqlConnectionStatus?.connected?'● 연결됨':'○ 연결 안됨'}
            </span>
          </div>

          <div className="sql-profile-manager">
            <label className="sql-field sql-saved-connection-select">
              <span>저장된 DB 연결</span>
              <select
                value={sqlProfile.connection_id||''}
                onChange={e=>selectSqlWorkspaceConnection(e.target.value)}
                disabled={sqlConnectionBusy}
              >
                <option value="">+ 새 DB 연결 만들기</option>
                {sqlConnections.map(item=><option value={item.connection_id} key={item.connection_id}>
                  {item.connected?'●':'○'} {item.name} · {String(item.db_type||'').toUpperCase()}
                </option>)}
              </select>
            </label>
            <div className="sql-profile-manager-actions">
              <button type="button" onClick={()=>newSqlWorkspaceConnection(sqlProfile.db_type)} disabled={sqlConnectionBusy}>+ 새 연결</button>
              <button type="button" className="danger" onClick={deleteSqlWorkspaceConnection} disabled={sqlConnectionBusy||!sqlProfile.connection_id}>저장 연결 삭제</button>
            </div>
            {!!sqlConnections.length&&<div className="sql-saved-connection-chips">
              {sqlConnections.map(item=><button
                type="button"
                key={`chip-${item.connection_id}`}
                className={`${item.connected?'connected ':''}${sqlProfile.connection_id===item.connection_id?'active':''}`.trim()}
                onClick={()=>selectSqlWorkspaceConnection(item.connection_id)}
                title={`${item.name} · ${String(item.db_type||'').toUpperCase()}${item.connected?' · 연결됨':' · 연결 안됨'}`}
              >
                <span>{item.connected?'●':'○'}</span>
                <b>{item.name}</b>
                <em>{String(item.db_type||'').toUpperCase()}</em>
              </button>)}
            </div>}
          </div>

          <label className="sql-field">
            <span>연결 이름</span>
            <input
              value={sqlProfile.name||''}
              onChange={e=>setSqlProfile(prev=>({...prev,name:e.target.value}))}
              placeholder="예: 운영 MSSQL / 개발 PostgreSQL / Supabase / Firestore / Redis"
            />
            {sqlProfile.connection_id&&<small className="muted">저장된 PostgreSQL/Supabase/Firestore/Redis/MSSQL/Oracle/SQLite3 연결 이름을 수정할 수 있습니다. 접속 정보와 저장 비밀번호는 변경하지 않습니다.</small>}
          </label>
          {sqlProfile.connection_id&&<div className="sql-profile-manager-actions">
            <button type="button" onClick={renameSqlWorkspaceConnection} disabled={sqlConnectionBusy||!String(sqlProfile.name||'').trim()}>연결 이름 변경 저장</button>
          </div>}

          <label className="sql-field">
            <span>DB 종류</span>
            <select value={sqlProfile.db_type} onChange={e=>{
              const nextType=e.target.value
              setSqlSupabaseConnectionUrl('')
              setSqlConnectionImport({busy:false,db_type:'',source_name:'',message:'',error:''})
              setSqlProfile(prev=>{
                const previousDefaultName=sqlProfileForType(prev.db_type||'postgresql').name
                const nextDefaultName=sqlProfileForType(nextType).name
                return {
                  ...sqlProfileForType(nextType),
                  connection_id:prev.connection_id||'',
                  name:(!prev.name||prev.name===previousDefaultName)?nextDefaultName:prev.name,
                  credential_saved:prev.db_type===nextType?!!prev.credential_saved:false,
                  password:''
                }
              })
              if(nextType==='sqlite3') loadSqliteProjectStatus({quiet:true})
            }}>
              <option value="postgresql">PostgreSQL</option>
              <option value="supabase">Supabase (PostgreSQL)</option>
              <option value="firestore">Google Cloud Firestore</option>
              <option value="redis">Redis (Key-Value)</option>
              <option value="mssql">MSSQL</option>
              <option value="oracle">Oracle</option>
              <option value="sqlite3">SQLite3</option>
            </select>
          </label>

          {sqlProfile.db_type==='firestore'
            ? <>
                <div className="sql-connection-import-card firestore-import-card">
                  <div>
                    <strong>Firestore Service Account JSON 자동 등록</strong>
                    <small>Google Cloud/Firebase Service Account JSON을 분석해 Project ID와 JSON 파일 경로를 자동 등록합니다. Private Key 내용은 설정에 복사하지 않습니다.</small>
                  </div>
                  <button type="button" onClick={()=>importSqlConnectionFile('firestore')} disabled={sqlConnectionImport.busy}>
                    {sqlConnectionImport.busy&&sqlConnectionImport.db_type==='firestore'?'분석 중...':'Service Account JSON 찾기 / 로드'}
                  </button>
                  {sqlConnectionImport.db_type==='firestore'&&sqlConnectionImport.message&&<p className="ok">{sqlConnectionImport.message}</p>}
                  {sqlConnectionImport.db_type==='firestore'&&sqlConnectionImport.error&&<p className="error">{sqlConnectionImport.error}</p>}
                </div>
                <label className="sql-field">
                  <span>Google Cloud Project ID</span>
                  <input value={sqlProfile.project_id||''} onChange={e=>setSqlProfile(prev=>({...prev,project_id:e.target.value}))} placeholder="예: my-firebase-project"/>
                </label>
                <label className="sql-field">
                  <span>Firestore Database ID</span>
                  <input value={sqlProfile.database||''} onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))} placeholder="(default)"/>
                </label>
                <label className="sql-field">
                  <span>Service Account JSON 경로</span>
                  <input value={sqlProfile.service_account_json||''} onChange={e=>setSqlProfile(prev=>({...prev,service_account_json:e.target.value}))} placeholder="serviceAccountKey.json · 비워두면 GOOGLE_APPLICATION_CREDENTIALS/ADC 사용"/>
                </label>
                <div className="sql-connection-info">
                  <div><span>드라이버</span><code>google-cloud-firestore</code></div>
                  <div><span>구조</span><code>Collection → Document → Field</code></div>
                  <small>Service Account JSON 파일 자체의 내용은 AgentStudio 설정에 저장하지 않고 파일 경로만 저장합니다.</small>
                </div>
              </>
            : sqlProfile.db_type==='redis'
            ? <>
                <div className="sql-connection-import-card">
                  <div>
                    <strong>Redis 연결 파일 자동 등록</strong>
                    <small>Python/JSON/.env 파일에서 Redis 연결 정보를 분석합니다. Python 파일은 실행하지 않고 AST로만 읽습니다.</small>
                  </div>
                  <button type="button" onClick={()=>importSqlConnectionFile('redis')} disabled={sqlConnectionImport.busy}>
                    {sqlConnectionImport.busy&&sqlConnectionImport.db_type==='redis'?'분석 중...':'파일 찾기 / 로드'}
                  </button>
                  {sqlConnectionImport.db_type==='redis'&&sqlConnectionImport.message&&<p className="ok">{sqlConnectionImport.message}</p>}
                  {sqlConnectionImport.db_type==='redis'&&sqlConnectionImport.error&&<p className="error">{sqlConnectionImport.error}</p>}
                </div>
                <div className="sql-field-grid two">
                  <label className="sql-field"><span>Host</span><input value={sqlProfile.host||''} onChange={e=>setSqlProfile(prev=>({...prev,host:e.target.value}))} placeholder="127.0.0.1"/></label>
                  <label className="sql-field"><span>Port</span><input type="number" value={sqlProfile.port||6379} onChange={e=>setSqlProfile(prev=>({...prev,port:Number(e.target.value)||6379}))} placeholder="6379"/></label>
                </div>
                <label className="sql-field">
                  <span>Redis DB index</span>
                  <input type="number" min="0" value={sqlProfile.database??'0'} onChange={e=>setSqlProfile(prev=>({...prev,database:String(Math.max(0,Number(e.target.value)||0))}))} placeholder="0"/>
                </label>
                <label className="sql-field">
                  <span>사용자 (ACL 사용 시)</span>
                  <input value={sqlProfile.username||''} onChange={e=>setSqlProfile(prev=>({...prev,username:e.target.value}))} placeholder="비워두면 기본 사용자"/>
                </label>
                <label className="sql-field">
                  <span>비밀번호 {sqlProfile.credential_saved&&<em className="sql-credential-saved">Windows 보안 저장됨</em>}</span>
                  <input
                    type="password"
                    value={sqlProfile.password||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,password:e.target.value}))}
                    placeholder={sqlProfile.credential_saved?'저장된 비밀번호 사용 · 변경할 때만 새 비밀번호 입력':'비밀번호가 없으면 비워두세요'}
                  />
                </label>
                <div className="sql-connection-info">
                  <div><span>드라이버</span><code>redis-py</code></div>
                  <div><span>구조</span><code>Key → Value · String / Hash / List / Set / ZSet</code></div>
                  <small>Redis는 SQL DB가 아니라 NoSQL Key-Value 데이터베이스입니다. 연결/인증/PING 테스트를 지원하며 SQL 실행은 사용하지 않습니다.</small>
                </div>
              </>
            : sqlProfile.db_type==='sqlite3'
            ? <>
                <label className="sql-field">
                  <span>SQLite DB 파일</span>
                  <input
                    value={sqlProfile.database||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))}
                    placeholder="data/app.db 또는 기존 .sqlite/.sqlite3 파일"
                    list="sqlite-project-db-files"
                  />
                  <datalist id="sqlite-project-db-files">
                    {(sqliteProjectStatus?.database_files||[]).map(path=><option value={path} key={path}/>) }
                  </datalist>
                </label>
                <div className="sqlite-project-status-card">
                  <div className="sqlite-project-status-head">
                    <div>
                      <strong>프로젝트 SQLite3 상태</strong>
                      <small>AgentStudio SQL Workspace는 Python 표준 sqlite3 모듈을 사용합니다.</small>
                    </div>
                    <button type="button" onClick={()=>loadSqliteProjectStatus()} disabled={sqliteProjectStatusBusy}>{sqliteProjectStatusBusy?'…':'↻ 확인'}</button>
                  </div>
                  <div className="sqlite-status-grid">
                    <div><span>AgentStudio sqlite3</span><strong className={sqliteProjectStatus?.agentstudio_python?.available?'ok':'warn'}>{sqliteProjectStatus?.agentstudio_python?.available?`사용 가능 · ${sqliteProjectStatus.agentstudio_python.sqlite_version||''}`:'확인 필요'}</strong></div>
                    <div><span>프로젝트 Python</span><strong className={sqliteProjectStatus?.project_python?.sqlite3_available?'ok':''}>{sqliteProjectStatus?.project_python?.found?(sqliteProjectStatus.project_python.sqlite3_available?`sqlite3 ${sqliteProjectStatus.project_python.sqlite_version||''}`:'sqlite3 사용 불가'):'가상환경 미탐지'}</strong></div>
                    <div><span>Node sqlite 패키지</span><strong>{(sqliteProjectStatus?.node_packages||[]).length?sqliteProjectStatus.node_packages.map(item=>`${item.name} ${item.version}`).join(', '):'설치 항목 없음'}</strong></div>
                    <div><span>SQLite CLI</span><strong>{sqliteProjectStatus?.sqlite_cli||'PATH에서 미탐지'}</strong></div>
                  </div>
                  <div className="sqlite-db-file-list">
                    <span>프로젝트 DB 파일 {(sqliteProjectStatus?.database_files||[]).length}개</span>
                    {(sqliteProjectStatus?.database_files||[]).length
                      ? (sqliteProjectStatus.database_files||[]).slice(0,12).map(path=><button type="button" key={path} onClick={()=>setSqlProfile(prev=>({...prev,database:path}))}>{path}</button>)
                      : <small>발견된 DB 파일이 없습니다. 예: data/app.db 를 입력하면 연결 시 생성합니다.</small>}
                  </div>
                </div>
              </>
            : <>
                {sqlProfile.db_type==='supabase'&&<>
                  <div className="sql-connection-import-card">
                    <div>
                      <strong>Supabase JSON 자동 등록</strong>
                      <small>JSON의 PostgreSQL URL 또는 Host/Port/Database/Schema/User/Password/SSL 정보를 분석해 아래 입력란에 자동 등록합니다.</small>
                    </div>
                    <button type="button" onClick={()=>importSqlConnectionFile('supabase')} disabled={sqlConnectionImport.busy}>
                      {sqlConnectionImport.busy&&sqlConnectionImport.db_type==='supabase'?'분석 중...':'JSON 파일 찾기 / 로드'}
                    </button>
                    {sqlConnectionImport.db_type==='supabase'&&sqlConnectionImport.message&&<p className="ok">{sqlConnectionImport.message}</p>}
                    {sqlConnectionImport.db_type==='supabase'&&sqlConnectionImport.error&&<p className="error">{sqlConnectionImport.error}</p>}
                  </div>
                  <label className="sql-field">
                    <span>Supabase Connection URL</span>
                    <input
                      type="password"
                      value={sqlSupabaseConnectionUrl}
                      onChange={e=>setSqlSupabaseConnectionUrl(e.target.value)}
                      placeholder="postgresql://USER:PASSWORD@HOST:5432/postgres"
                      autoComplete="off"
                    />
                  </label>
                  <div className="sql-profile-manager-actions">
                    <button type="button" onClick={applySupabaseConnectionUrl} disabled={!String(sqlSupabaseConnectionUrl||'').trim()}>Connection URL 적용</button>
                  </div>
                  <small className="muted">Dashboard에서 복사한 URL은 저장하지 않고 아래 연결 필드로만 분해합니다.</small>
                </>}
                <div className="sql-field-grid two">
                  <label className="sql-field"><span>Host</span><input value={sqlProfile.host||''} onChange={e=>setSqlProfile(prev=>({...prev,host:e.target.value}))}/></label>
                  <label className="sql-field"><span>Port</span><input type="number" value={sqlProfile.port||''} onChange={e=>setSqlProfile(prev=>({...prev,port:Number(e.target.value)||0}))}/></label>
                </div>

                {sqlProfile.db_type!=='oracle'
                  ? (()=>{
                      const history=getSqlDatabaseHistory()
                      const current=String(sqlProfile.database||'')
                      const canUseHistory=history.length>=2&&!sqlDatabaseManual&&(!current||history.includes(current))
                      return <label className="sql-field">
                        <span>Database {history.length>=2&&<em className="sql-database-history-count">접속 이력 {history.length}개</em>}</span>
                        {canUseHistory
                          ? <div className="sql-database-history-control">
                              <select
                                value={current}
                                onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))}
                              >
                                <option value="">Database 선택</option>
                                {history.map(dbName=><option key={dbName} value={dbName}>{dbName}</option>)}
                              </select>
                              <button type="button" onClick={()=>{setSqlDatabaseManual(true);setSqlProfile(prev=>({...prev,database:''}))}}>직접 입력</button>
                            </div>
                          : <div className="sql-database-history-control">
                              <input
                                value={current}
                                onChange={e=>setSqlProfile(prev=>({...prev,database:e.target.value}))}
                                placeholder={sqlProfile.db_type==='mssql'?'master':'postgres'}
                              />
                              {history.length>=2&&<button type="button" onClick={()=>{setSqlDatabaseManual(false);setSqlProfile(prev=>({...prev,database:history[0]||''}))}}>이력 선택</button>}
                            </div>}
                      </label>
                    })()
                  : <label className="sql-field"><span>Service Name</span><input value={sqlProfile.service_name||''} onChange={e=>setSqlProfile(prev=>({...prev,service_name:e.target.value}))} placeholder="FREEPDB1 / XEPDB1"/></label>}

                {sqlProfile.db_type==='supabase'&&<label className="sql-field">
                  <span>Schema</span>
                  <input
                    value={sqlProfile.schema_name||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,schema_name:e.target.value}))}
                    placeholder="예: theanova_agentstudio / public"
                  />
                  <small className="muted">Supabase PostgreSQL 연결 후 기본 search_path를 Schema → extensions → public 순서로 적용합니다. 비우면 public을 사용합니다.</small>
                </label>}

                <label className="sql-field"><span>사용자</span><input value={sqlProfile.username||''} onChange={e=>setSqlProfile(prev=>({...prev,username:e.target.value}))}/></label>
                <label className="sql-field">
                  <span>비밀번호 {sqlProfile.credential_saved&&<em className="sql-credential-saved">Windows 보안 저장됨</em>}</span>
                  <input
                    type="password"
                    value={sqlProfile.password||''}
                    onChange={e=>setSqlProfile(prev=>({...prev,password:e.target.value}))}
                    placeholder={sqlProfile.credential_saved?'저장된 비밀번호 사용 · 변경할 때만 새 비밀번호 입력':'DB 비밀번호'}
                  />
                </label>

                {sqlProfile.db_type==='mssql'&&<>
                  <label className="sql-field"><span>ODBC Driver</span><input value={sqlProfile.driver||''} onChange={e=>setSqlProfile(prev=>({...prev,driver:e.target.value}))}/></label>
                  <label className="sql-check-field"><input type="checkbox" checked={!!sqlProfile.trust_server_certificate} onChange={e=>setSqlProfile(prev=>({...prev,trust_server_certificate:e.target.checked}))}/><span>Trust Server Certificate</span></label>
                </>}
                {sqlProfile.db_type==='supabase'&&
                  <label className="sql-field"><span>SSL Mode</span><input value={sqlProfile.ssl_mode||'require'} onChange={e=>setSqlProfile(prev=>({...prev,ssl_mode:e.target.value}))} placeholder="require"/></label>}
              </>}

          <div className="sql-connection-actions">
            <button type="button" onClick={saveSqlWorkspaceProfile} disabled={sqlConnectionBusy}>연결 정보 저장</button>
            <button type="button" className="primary" onClick={connectSqlWorkspace} disabled={sqlConnectionBusy}>{sqlConnectionBusy?'처리 중...':'연결 / 테스트'}</button>
            <button type="button" onClick={disconnectSqlWorkspace} disabled={sqlConnectionBusy||!sqlConnectionStatus?.connected}>현재 연결 해제</button>
            <button type="button" onClick={loadSqlWorkspaceStatus} disabled={sqlConnectionBusy}>상태 새로고침</button>
            {sqlProfile.db_type==='supabase'&&<button type="button" onClick={()=>window.open('https://supabase.com/dashboard','_blank','noopener,noreferrer')}>Supabase Dashboard</button>}
            {sqlProfile.db_type==='firestore'&&<button type="button" onClick={()=>window.open('https://console.cloud.google.com/firestore/databases','_blank','noopener,noreferrer')}>Google Cloud Firestore</button>}
          </div>

          <div className="sql-connection-info">
            <div><span>현재 파일</span><code>{selected}</code></div>
            <div><span>선택 연결</span><strong>{sqlProfile.name||'새 DB 연결'} · {String(sqlProfile.db_type||'').toUpperCase()}</strong></div>
            <div><span>현재 연결 상태</span><strong>{sqlConnectionStatus?.connected?'연결 유지 중':'연결 필요'}</strong></div>
            <div><span>저장된 연결</span><code>{sqlConnectionStatus?.saved_connection_count??sqlConnections.length}개 · 연결 중 {sqlConnectionStatus?.connected_connection_count??sqlConnections.filter(item=>item.connected).length}개</code></div>
            {sqlProfile.db_type==='sqlite3'&&<div><span>DB 파일</span><code>{sqlConnectionStatus?.profile?.database||sqlProfile.database||'-'}</code></div>}
            {sqlProfile.db_type==='supabase'&&<div><span>Supabase Schema</span><code>{sqlConnectionStatus?.profile?.schema_name||sqlProfile.schema_name||'public'}</code></div>}
            {sqlConnectionStatus?.connected_at&&<div><span>연결 시각</span><code>{sqlConnectionStatus.connected_at}</code></div>}
            {!!(sqlConnectionStatus?.saved_db_types||[]).length&&<div><span>등록된 DB 종류</span><code>{sqlConnectionStatus.saved_db_types.map(v=>String(v).toUpperCase()).join(', ')}</code></div>}
            {sqlConnectionStatus?.profile_storage_path&&<div><span>연결 정보 저장 위치</span><code title={sqlConnectionStatus.profile_storage_path}>{sqlConnectionStatus.profile_storage_path}</code></div>}
            {!['sqlite3','firestore'].includes(sqlProfile.db_type)&&<div><span>비밀번호 저장</span><code>{sqlConnectionStatus?.credential_storage||'Windows DPAPI'}</code></div>}
            {sqlProfile.db_type==='firestore'&&<div><span>인증</span><code>{sqlProfile.service_account_json?'Service Account JSON':'GOOGLE_APPLICATION_CREDENTIALS / ADC'}</code></div>}
            <small>{sqlProfile.db_type==='sqlite3'
              ? 'SQLite3도 여러 DB 파일을 각각 별도의 연결로 등록할 수 있습니다.'
              : sqlProfile.db_type==='firestore'
                ? 'Firestore는 NoSQL 문서형 DB입니다. AgentStudio에서는 Project/Database/Service Account 경로를 저장하고 연결을 테스트합니다.'
                : sqlProfile.db_type==='supabase'
                  ? 'Supabase는 PostgreSQL 기반 관리형 플랫폼으로 psycopg와 SSL(require)을 사용해 SQL Workspace에 연결합니다.'
                  : sqlProfile.db_type==='redis'
                    ? 'Redis는 NoSQL Key-Value DB입니다. Host/Port/DB index/ACL 사용자/비밀번호를 저장하고 redis-py PING으로 연결한 뒤 Key Browser에서 데이터를 조회합니다.'
                    : '동일한 DB 종류도 연결 이름을 다르게 하여 여러 개 등록할 수 있습니다. Windows에서는 비밀번호를 DPAPI 현재 사용자 범위로 암호화하여 저장하며 평문으로 기록하지 않습니다.'}</small>
          </div>

          <div className="sql-object-explorer">
            <div className="sql-object-explorer-head">
              <div>
                <strong>{sqlProfile.db_type==='firestore'?'Firestore 연결':sqlProfile.db_type==='redis'?'Redis 연결':'DB Object Explorer'}</strong>
                <small>{sqlProfile.db_type==='firestore'?'NoSQL Document Database · Collection → Document → Field':sqlProfile.db_type==='redis'?'NoSQL Key-Value Database · String / Hash / List / Set / ZSet':'테이블 · 뷰 · 프로시저 · 함수 · 인덱스 · 시퀀스 · 트리거'}</small>
                <small className="sql-object-doubleclick-help">{sqlProfile.db_type==='firestore'?'Firestore 인증 후 Collection/Document/Field를 읽기 전용으로 탐색합니다. SQL 실행은 사용하지 않습니다.':sqlProfile.db_type==='redis'?'Redis 인증/PING 후 Key Browser에서 실제 Key/Value를 읽기 전용으로 조회합니다. SQL 실행은 사용하지 않습니다.':'더블클릭: 테이블은 전체 컬럼 SELECT 조회 · 기타 객체는 수정용 임시 SQL 생성'}</small>
              </div>
              <button
                type="button"
                onClick={()=>sqlProfile.db_type==='firestore'?loadFirestoreCollections():sqlProfile.db_type==='redis'?loadRedisKeys():loadSqlDbObjects()}
                disabled={!sqlConnectionStatus?.connected||(sqlProfile.db_type==='firestore'?firestoreBrowserBusy:sqlProfile.db_type==='redis'?redisBrowserBusy:sqlDbObjectsBusy)}
                title={sqlProfile.db_type==='firestore'?'Firestore Collection 목록 새로고침':sqlProfile.db_type==='redis'?'Redis Key 목록 새로고침':'DB 객체 목록 새로고침'}
              >
                {(sqlProfile.db_type==='firestore'?firestoreBrowserBusy:sqlProfile.db_type==='redis'?redisBrowserBusy:sqlDbObjectsBusy)?'…':'↻'}
              </button>
            </div>

            {sqlProfile.db_type==='firestore'
              ? <FirestoreBrowserPanel
                  connected={sqlConnectionStatus?.connected}
                  profile={sqlProfile}
                  browser={firestoreBrowser}
                  browserBusy={firestoreBrowserBusy}
                  browserError={firestoreBrowserError}
                  collectionFilter={firestoreCollectionFilter}
                  documentFilter={firestoreDocumentFilter}
                  selectedCollection={firestoreSelectedCollection}
                  documents={firestoreDocuments}
                  documentsBusy={firestoreDocumentsBusy}
                  selectedDocument={firestoreSelectedDocument}
                  documentDetail={firestoreDocumentDetail}
                  documentDetailBusy={firestoreDocumentDetailBusy}
                  setCollectionFilter={setFirestoreCollectionFilter}
                  setDocumentFilter={setFirestoreDocumentFilter}
                  loadCollections={loadFirestoreCollections}
                  loadDocuments={loadFirestoreDocuments}
                  loadDocumentDetail={loadFirestoreDocumentDetail}
                  openContextMenu={openFirestoreContextMenu}
                />
              : sqlProfile.db_type==='redis'
                ? <RedisBrowserPanel
                    connected={sqlConnectionStatus?.connected}
                    profile={sqlProfile}
                    browser={redisBrowser}
                    browserBusy={redisBrowserBusy}
                    browserError={redisBrowserError}
                    keyFilter={redisKeyFilter}
                    typeFilter={redisTypeFilter}
                    selectedKey={redisSelectedKey}
                    keyDetail={redisKeyDetail}
                    keyDetailBusy={redisKeyDetailBusy}
                    keyExpanded={redisKeyExpanded}
                    setKeyFilter={setRedisKeyFilter}
                    setTypeFilter={setRedisTypeFilter}
                    toggleKeyGroup={toggleRedisKeyGroup}
                    loadKeys={loadRedisKeys}
                    loadKeyDetail={loadRedisKeyDetail}
                    openContextMenu={openRedisContextMenu}
                  />
                : <SqlObjectTreePanel
                    connected={sqlConnectionStatus?.connected}
                    profile={sqlProfile}
                    connectionStatus={sqlConnectionStatus}
                    dbObjects={sqlDbObjects}
                    busy={sqlDbObjectsBusy}
                    error={sqlDbObjectsError}
                    expanded={sqlDbObjectExpanded}
                    actionBusy={sqlObjectActionBusy}
                    toggleObject={toggleSqlDbObject}
                    openObject={openSqlDbObject}
                    openObjectContextMenu={openSqlObjectContextMenu}
                    openDatabaseContextMenu={openSqlDatabaseContextMenu}
                  />}

            {sqlDbObjects?.refreshed_at&&sqlProfile.db_type!=='firestore'&&sqlProfile.db_type!=='redis'&&
              <div className="sql-object-refreshed">최근 조회: {sqlDbObjects.refreshed_at.replace('T',' ')}</div>}

            <DatabaseBrowserContextMenus
              firestoreContextMenu={firestoreContextMenu}
              firestoreScriptBusy={firestoreScriptBusy}
              createFirestorePythonScript={createFirestorePythonScript}
              redisContextMenu={redisContextMenu}
              redisScriptBusy={redisScriptBusy}
              createRedisPythonScript={createRedisPythonScript}
              sqlObjectContextMenu={sqlObjectContextMenu}
              sqlObjectActionBusy={sqlObjectActionBusy}
              createSqlTableScript={createSqlTableScript}
              createSqlTableAlterScript={createSqlTableAlterScript}
              createSqlTableDmlScript={createSqlTableDmlScript}
              sqlDatabaseContextMenu={sqlDatabaseContextMenu}
              dbObjects={sqlDbObjects}
              profile={sqlProfile}
              createPostgresqlAdminScript={createPostgresqlAdminScript}
              openSqlAdminPrompt={openSqlAdminPrompt}
              sqlAdminPrompt={sqlAdminPrompt}
              setSqlAdminPrompt={setSqlAdminPrompt}
              submitSqlAdminPrompt={submitSqlAdminPrompt}
            />

          </div>

          {sqlConnectionStatus?.error&&<div className="sql-connection-error">{sqlConnectionStatus.error}</div>}
        </div>}

        {codeRightPanelTab==='PROPOSAL'&&
        <div className="info-card code-proposal-panel code-tab-panel">
          <div className="code-proposal-panel-head">
            <div>
              <strong>AI 변경 제안</strong>
              <small>AI 코드는 바로 원본에 반영되지 않습니다.</small>
            </div>
            {codeDiffReview&&<span className="diff-review-badge">Diff 검토 중</span>}
          </div>

          {codeEditProposal
            ? <>
                <div className="code-proposal-meta">
                  <span>대상 파일</span>
                  <code>{codeEditProposal.path}</code>
                </div>
                {codeEditProposal.instruction&&
                  <div className="code-proposal-instruction">
                    <span>요청</span>
                    <p>{codeEditProposal.instruction}</p>
                  </div>
                }
                {codeEditProposal.editScope==='notebook_cell'&&
                  <div className="code-proposal-context-budget">
                    <span>Notebook Cell {(Number(codeEditProposal.activeCellIndex)||0)+1}만 수정</span>
                    {codeEditProposal.contextBudget&&<small>
                      LLM Context {Number(codeEditProposal.contextBudget.llm_context_chars||0).toLocaleString('ko-KR')}자
                      {' / '}전체 파일 {Number(codeEditProposal.contextBudget.original_file_chars||0).toLocaleString('ko-KR')}자
                    </small>}
                  </div>
                }
                {codeEditProposal.explanation&&
                  <p className="code-proposal-explanation">{codeEditProposal.explanation}</p>
                }
                <div className="code-proposal-editor-wrap">
                  <Editor
                    key={codeEditProposal.createdAt||codeEditProposal.path}
                    height="100%"
                    value={codeEditProposal.displayCode||codeEditProposal.code}
                    language={codeEditProposal.editScope==='notebook_cell'?'python':getEditorLanguage(codeEditProposal.path)}
                    theme="vs-dark"
                    options={{
                      readOnly:true,
                      minimap:{enabled:false},
                      lineNumbers:'on',
                      fontSize:13,
                      lineHeight:20,
                      automaticLayout:true,
                      scrollBeyondLastLine:false,
                      folding:true,
                      wordWrap:'off',
                      mouseWheelScrollSensitivity:1,
                      scrollbar:{
                        vertical:'visible',
                        horizontal:'auto',
                        verticalScrollbarSize:12,
                        horizontalScrollbarSize:10,
                        alwaysConsumeMouseWheel:false,
                        useShadows:true
                      }
                    }}
                  />
                </div>
                <div className="code-proposal-panel-actions">
                  <button type="button" className="apply" onClick={openCodeEditDiffReview}>Apply · 비교</button>
                  <button type="button" onClick={discardCodeEditProposal}>취소</button>
                </div>
              </>
            : <div className="code-proposal-empty">
                <span>◇</span>
                <strong>AI 변경 제안이 없습니다.</strong>
                <p>하단 채팅에서 파일 단위로 코드 변경을 요청하면 이 탭에 제안 코드가 표시됩니다.</p>
              </div>
          }
        </div>}
      </div>}

    </aside>
  </div>

  const pickExternalProjectFolder=async()=>{
    if(externalProjectPickerLoading) return

    setExternalProjectPickerLoading(true)
    setExternalProjectPickerMessage(
      'Windows 폴더 선택창을 여는 중입니다...'
    )

    try{
      const r=await api('/system/pick-folder',{
        method:'POST',
        body:JSON.stringify({
          title:'분석할 기존 프로젝트 폴더 선택',
          initial_path:externalProjectPath||''
        })
      })

      if(r?.ok && !r?.cancelled && r?.path){
        setExternalProjectPath(r.path)
        setExternalProjectPickerMessage(
          '선택한 경로: '+r.path
        )
        return
      }

      if(r?.cancelled){
        setExternalProjectPickerMessage(
          '폴더 선택을 취소했습니다.'
        )
        return
      }

      setExternalProjectPickerMessage(
        '경로 선택 실패: '
        +(r?.message||'폴더 선택창을 열지 못했습니다.')
      )
    }catch(e){
      const message='경로 선택 실패: '+String(e)

      setExternalProjectPickerMessage(message)
      setProjectLoadMessage(message)
    }finally{
      setExternalProjectPickerLoading(false)
    }
  }

  const pollExternalProjectJob=async(jobId)=>{
    let lastProgress=0

    for(let i=0;i<1800;i++){
      try{
        const j=await api(`/jobs/${jobId}`)

        const progress=Math.max(lastProgress,Number(j.progress||0))
        lastProgress=progress

        setExternalProjectProgress(progress)
        setExternalProjectStatus(j.status||'RUNNING')
        setExternalProjectStep(j.message||'분석 작업을 진행하고 있습니다.')

        if(j.status==='SUCCESS'){
          const r=j.result||{}

          setExternalProjectProgress(100)
          setExternalProjectStatus('SUCCESS')
          setExternalProjectStep('분석 및 DB 저장 완료. 작업공간으로 이동합니다.')

          setExternalProjectAnalysis(r)
          setExternalProjectMode(false)
          setSelectedProjectId(r.project_id||null)
          setRoot(r.project_root||externalProjectPath)
          setNewAgentProjectRoot(r.project_root||externalProjectPath)
          setNewAgentName(
            r.project_name
            || (r.project_root||externalProjectPath).split(/[\\/]/).filter(Boolean).pop()
            || 'External Project'
          )
          setNewAgentCachePath(r.cache_path||'')
          setNewAgentTempPath(r.temp_path||'')
          setNewAgentOutputPath(r.output_path||'')
          setNewAgentVenvPath(r.venv_path||'')
          setNewAgentModelsPath(r.models_path||'')
          setLoadedProjectAnalysis({
            summary:r.summary||'',
            tech_stack:r.tech_stack||[],
            entry_points:r.entry_points||[],
            major_files:r.major_files||[],
            mcp_tools:r.mcp_tools||[],
            structure:r.structure||{}
          })

          setProjectLoadMessage(`Project #${r.project_id} 분석 및 DB 저장 완료`)
          const dbProjects=await refreshProjectList()

          if(!dbProjects.some(p=>p.id===r.project_id)){
            setProjectListStatus(
              `DB 저장 응답은 성공했지만 Project #${r.project_id}가 GET /api/projects 결과에 없습니다.`
            )
          }

          await loadProject(r.project_id)

          // 완료 상태를 잠깐 보여준 후 자동으로 작업공간 이동
          await new Promise(resolve=>setTimeout(resolve,700))

          setProjectListOpen(false)
          setScreen('WORKSPACE')

          try{
            const fileResult=await api(
              `/files?root=${encodeURIComponent(r.project_root||externalProjectPath)}`
            )
            setFiles(
              Array.isArray(fileResult)
                ? fileResult
                : (fileResult.files||[])
            )
          }catch(e){
            try{ await loadFiles() }catch(_){}
          }

          setExternalProjectLoading(false)
          return
        }

        if(['FAILED','CANCELLED'].includes(j.status)){
          setExternalProjectStatus(j.status)
          setExternalProjectStep(
            j.result?.message
            || j.message
            || '프로젝트 분석 작업에 실패했습니다.'
          )
          setExternalProjectAnalysis({
            ok:false,
            message:j.result?.message||j.message||'',
            log_path:j.result?.log_path||'',
            traceback:j.result?.traceback||''
          })
          setProjectLoadMessage(
            '프로젝트 분석 실패: '
            + (j.result?.message||j.message||'상세 오류를 확인하세요.')
          )
          setExternalProjectLoading(false)
          return
        }
      }catch(e){
        setExternalProjectStep(
          '분석 상태 확인 중 오류: '+String(e)
        )
      }

      await new Promise(resolve=>setTimeout(resolve,800))
    }

    setExternalProjectStatus('FAILED')
    setExternalProjectStep('프로젝트 분석 상태 확인 시간이 초과되었습니다.')
    setExternalProjectLoading(false)
  }

  const analyzeExternalProject=async()=>{
    if(!externalProjectPath.trim()){
      setProjectLoadMessage('분석할 프로젝트 경로를 지정하세요.')
      return
    }

    setExternalProjectLoading(true)
    setExternalProjectProgress(0)
    setExternalProjectStatus('QUEUED')
    setExternalProjectStep('프로젝트 분석 작업을 준비하고 있습니다.')
    setProjectLoadMessage('')
    setExternalProjectAnalysis(null)

    try{
      const job=await api('/projects/analyze-external',{
        method:'POST',
        body:JSON.stringify({
          project_root:externalProjectPath,
          request:'프로젝트 소스 구조, 기술 스택, 주요 파일, 실행 진입점, MCP/Agent 관련 소스만 분석해주세요. 모델은 실행하지 말고 소스에 명시된 모델명만 참고해주세요.'
        })
      })

      if(!job.ok || !job.job_id){
        setExternalProjectStatus('FAILED')
        setExternalProjectStep(job.message||'분석 작업 시작에 실패했습니다.')
        setExternalProjectLoading(false)
        return
      }

      setExternalProjectStatus(job.status||'QUEUED')
      setExternalProjectProgress(job.progress||0)
      setExternalProjectStep(job.message||'분석 작업을 시작했습니다.')

      pollExternalProjectJob(job.job_id)

    }catch(e){
      setExternalProjectStatus('FAILED')
      setExternalProjectStep('프로젝트 분석 시작 실패: '+String(e))
      setExternalProjectLoading(false)
    }
  }

  const openExternalProjectWorkspace=async()=>{
    if(!externalProjectAnalysis?.project_root) return

    setRoot(externalProjectAnalysis.project_root)
    setScreen('WORKSPACE')
    setProjectListOpen(false)
    setExternalProjectMode(true)

    try{
      const r=await api(`/files?root=${encodeURIComponent(externalProjectAnalysis.project_root)}`)
      setFiles(Array.isArray(r)?r:(r.files||[]))
    }catch(e){
      try{ await loadFiles() }catch(_){}
    }
  }

  const registerExternalProject=async()=>{
    if(!externalProjectAnalysis?.project_root) return

    const name = newAgentName.trim() || externalProjectAnalysis.project_root.split(/[\\/]/).filter(Boolean).pop() || 'Imported Project'

    try{
      const r=await api('/projects/create-agent',{
        method:'POST',
        body:JSON.stringify({
          name,
          project_root:externalProjectAnalysis.project_root,
          cache_path:'',
          temp_path:'',
          output_path:'',
          venv_path:'',
          models_path:''
        })
      })

      if(r.ok){
        setSelectedProjectId(r.project_id)
        setExternalProjectMode(false)
        setProjectLoadMessage(`프로젝트 #${r.project_id} DB 등록 완료`)
        setExternalProjectAnalysis(prev=>({...prev,registered:true,project_id:r.project_id}))
      }else{
        setProjectLoadMessage(r.message||'프로젝트 등록에 실패했습니다.')
      }
    }catch(e){
      setProjectLoadMessage('프로젝트 등록 실패: '+String(e))
    }
  }


  const runningBackgroundJobs=Object.values(jobs||{}).filter(job=>['QUEUED','PENDING','RUNNING','WAITING_USER'].includes(String(job?.status||'').toUpperCase()))
  const busyTerminalSessions=terminalSessions.filter(item=>item?.busy)
  const hasActiveExecution=Boolean(
    pythonExecutionState.busy
    ||sqlQueryBusy
    ||cmdExecution.busy
    ||agentBuildBusy
    ||activeWorkflowJobId
    ||busyTerminalSessions.length
    ||runningBackgroundJobs.length
  )

  const stopAllExecutions=async()=>{
    if(globalStopBusy||!hasActiveExecution) return
    setGlobalStopBusy(true)
    try{
      const actions=[]
      if(pythonExecutionState.busy){
        if(isNotebookFile(selectedEditorFileRef.current||selected||'')) actions.push(notebookEditorControllerRef.current?.stopExecution?.()||stopPythonExecution())
        else actions.push(stopPythonExecution())
      }
      if(sqlQueryBusy) actions.push(stopSqlExecution())
      if(cmdExecution.busy) actions.push(stopCurrentCmdFile())
      if(activeWorkflowJobId) actions.push(cancelAgentDevelopment())

      for(const terminalSession of busyTerminalSessions){
        try{ interruptTerminal(terminalSession.id) }catch{}
      }

      const distinctJobIds=new Set(runningBackgroundJobs.map(job=>String(job?.id||'')).filter(Boolean))
      if(activeWorkflowJobId) distinctJobIds.delete(String(activeWorkflowJobId))
      for(const jobId of distinctJobIds){
        actions.push(api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'}).catch(()=>null))
      }
      await Promise.allSettled(actions)
    }finally{
      setGlobalStopBusy(false)
    }
  }


  return <div className="app studio-app ux-app">
    <header className="ux-topbar">
      <div className="brand-block" onClick={()=>setScreen('HOME')} title="THEANOVA AgentStudio 홈">
        <img
          className="brand-symbol-image"
          src="/branding/theanova-symbol.png"
          alt="THEANOVA"
          draggable="false"
        />
        <img
          className="brand-wordmark-image"
          src="/branding/theanova-wordmark.png"
          alt="THEANOVA"
          draggable="false"
        />
        <strong className="brand-product-name">AgentStudio</strong>
        <span
          className="brand-version-badge"
          title={`현재 THEANOVA AgentStudio 버전 v${AGENTSTUDIO_FRONTEND_VERSION}`}
        >
          v{AGENTSTUDIO_FRONTEND_VERSION}
        </span>
      </div>
      {hasActiveExecution&&<button
        type="button"
        className="global-execution-stop-button"
        onClick={stopAllExecutions}
        disabled={globalStopBusy}
        title="현재 AgentStudio에서 실행 중인 작업을 모두 중지"
      >■ {globalStopBusy?'정지 중…':'실행 정지'}</button>}
      <div className="project-switcher-control">
        <button
          type="button"
          className="project-switcher"
          onClick={async()=>{
            const next=!projectSwitcherOpen
            setProjectSwitcherOpen(next)
            if(next) await refreshProjectList()
          }}
          aria-expanded={projectSwitcherOpen}
        >
          <span>{currentProjectName}</span><b>⌄</b>
        </button>
        {projectSwitcherOpen&&
          <div className="project-switcher-menu">
            <div className="project-switcher-menu-head">
              <strong>프로젝트 전환</strong>
              <small>{projectList.length}개</small>
            </div>
            <button
              type="button"
              className="project-switcher-new"
              onClick={()=>{
                setProjectSwitcherOpen(false)
                startNewProject()
              }}
            >＋ 신규 Agent 만들기</button>
            <div className="project-switcher-list">
              {projectList.map(p=>
                <button
                  type="button"
                  key={p.id}
                  className={selectedProjectId===p.id?'project-switcher-item active':'project-switcher-item'}
                  onClick={async()=>{
                    setProjectSwitcherOpen(false)
                    await loadProject(p.id)
                  }}
                >
                  <span>
                    <strong>{p.name||`Project ${p.id}`}</strong>
                    <small>{p.project_root||''}</small>
                  </span>
                  {selectedProjectId===p.id&&<b>✓</b>}
                </button>
              )}
              {!projectList.length&&
                <div className="project-switcher-empty">등록된 프로젝트가 없습니다.</div>
              }
            </div>
            <button
              type="button"
              className="project-switcher-all"
              onClick={async()=>{
                setProjectSwitcherOpen(false)
                await openProjectList()
              }}
            >전체 프로젝트 보기</button>
          </div>
        }
      </div>
      <div className="global-search">⌕ 명령어 검색... <kbd>Ctrl + K</kbd></div>
      <div className="topbar-spacer"/>
      <div className="ai-mode-control">
        <button
          type="button"
          className="mode-pill ai-mode-button"
          onClick={async()=>{
            const next=!aiModeMenuOpen
            setAiModeMenuOpen(next)
            if(next) await refreshAiRuntimeStatus()
          }}
          aria-expanded={aiModeMenuOpen}
        >
          {aiModeHeaderLabel} <span className="ai-mode-caret">⌄</span>
        </button>

        {aiModeMenuOpen&&
          <div className="ai-mode-menu">
            <div className="ai-mode-menu-head">
              <strong>AI 실행 모드</strong>
              <button
                type="button"
                onClick={refreshAiRuntimeStatus}
                disabled={aiModeBusy}
              >↻</button>
            </div>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='auto'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('auto')}
              disabled={aiModeBusy}
            >
              <span><strong>AUTO</strong><small>로컬 작업과 유료 LLM을 작업별로 자동 라우팅</small></span>
              {aiRuntimeStatus?.mode==='auto'&&<b>✓</b>}
            </button>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='openai'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('openai')}
              disabled={aiModeBusy||!aiRuntimeStatus?.providers?.openai?.configured}
            >
              <span>
                <strong>OpenAI · {aiRuntimeStatus?.providers?.openai?.model||'-'}</strong>
                <small>{aiRuntimeStatus?.providers?.openai?.configured?'API Key 설정됨':'API Key 미설정'}</small>
              </span>
              {aiRuntimeStatus?.mode==='openai'&&<b>✓</b>}
            </button>

            <button
              type="button"
              className={aiRuntimeStatus?.mode==='ollama'?'ai-mode-option active':'ai-mode-option'}
              onClick={()=>applyAiMode('ollama')}
              disabled={aiModeBusy||!aiRuntimeStatus?.providers?.ollama?.connected}
            >
              <span>
                <strong>Ollama · {aiRuntimeStatus?.providers?.ollama?.model||'-'}</strong>
                <small className={aiRuntimeStatus?.providers?.ollama?.connected?'provider-ok':'provider-bad'}>
                  {aiRuntimeStatus?.providers?.ollama?.connected?'연결됨':'연결 안됨'}
                </small>
              </span>
              {aiRuntimeStatus?.mode==='ollama'&&<b>✓</b>}
            </button>

            <div className="ai-mode-routing">
              <div><span>코딩/디버깅</span><b>{aiRuntimeStatus?.routing?.coding?.provider||'-'} · {aiRuntimeStatus?.routing?.coding?.model||'-'}</b></div>
              <div><span>요구사항</span><b>{aiRuntimeStatus?.routing?.requirements?.provider||'-'} · {aiRuntimeStatus?.routing?.requirements?.model||'-'}</b></div>
              <div><span>로컬 작업</span><b>{aiRuntimeStatus?.routing?.local?.provider||'-'} · {aiRuntimeStatus?.routing?.local?.model||'-'}</b></div>
            </div>

            {aiModeError&&<div className="ai-mode-error">{aiModeError}</div>}

            <button
              type="button"
              className="ai-mode-settings-link"
              onClick={()=>location.href='/system'}
            >AI 설정 열기
            </button>
          </div>
        }
      </div>
      <div className="external-notification-control">
        <button
          type="button"
          className={externalFileNotifications.length?'icon-btn notification-bell active':'icon-btn notification-bell'}
          onClick={()=>setExternalNotificationOpen(prev=>!prev)}
          title="외부 파일 변경 알림"
          aria-label="외부 파일 변경 알림"
        >
          🔔
          {externalFileNotifications.length>0&&
            <span className="notification-badge">
              {Math.min(externalFileNotifications.length,99)}
            </span>
          }
        </button>
        {externalNotificationOpen&&
          <div className="external-notification-menu">
            <div className="external-notification-head">
              <strong>외부 파일 변경</strong>
              <button
                type="button"
                onClick={()=>setExternalFileNotifications([])}
                disabled={!externalFileNotifications.length}
              >모두 지우기</button>
            </div>
            <div className="external-notification-list">
              {externalFileNotifications.map(item=><div
                key={item.id}
                className="external-notification-item"
              >
                <span>{item.status==='deleted'?'삭제':'수정'}</span>
                <div className="external-notification-body">
                  <strong>{item.path.split('/').pop()}</strong>
                  <small>{item.path}</small>
                  <em>
                    {item.status==='modified_conflict'
                      ? '미저장 내용과 외부 수정이 충돌했습니다.'
                      : item.status==='modified_reloaded'
                        ? '외부 수정 내용을 자동 반영했습니다.'
                        : '외부에서 파일이 삭제되었습니다.'}
                  </em>
                </div>
                <div className="external-notification-actions">
                  <button
                    type="button"
                    className="external-notification-review"
                    onClick={()=>handleExternalNotificationClick(item)}
                  >{item.status==='deleted'?'확인':'수정'}</button>
                  <button
                    type="button"
                    className="external-notification-ignore"
                    onClick={()=>handleExternalNotificationIgnore(item)}
                    title={item.status==='modified_conflict'
                      ? '외부 수정 내용을 지금은 무시하고 현재 AgentStudio 편집 내용을 유지합니다.'
                      : '이 알림을 무시합니다.'}
                  >무시</button>
                </div>
              </div>)}
              {!externalFileNotifications.length&&
                <div className="external-notification-empty">새 알림이 없습니다.</div>
              }
            </div>
          </div>
        }
      </div>
      <button className="icon-btn">?</button>
      <button className="icon-btn">♢</button>
      <button className="icon-btn" onClick={()=>location.href='/system'}>⚙</button>
      <div className="profile-block"><span className="avatar">A</span><div><strong>admin</strong><small>시스템 관리자</small></div></div>
    </header>

    <div className="ux-body">
      <aside className="ux-global-nav">
        <StudioIcon
          active={screen==='HOME'}
          onClick={()=>setScreen('HOME')}
        >⌂</StudioIcon>

        <StudioIcon
          active={screen==='WORKSPACE'&&workspaceTab==='DESIGN'}
          onClick={startNewProject}
          title="신규 Agent 설계"
        >✦</StudioIcon>

        <StudioIcon
          active={screen==='MCP'}
          onClick={()=>{
            refreshMcp()
            setScreen('MCP')
          }}
        >◉</StudioIcon>

        <StudioIcon
          active={screen==='PROJECTS'}
          onClick={async()=>{
            await refreshProjectList()
            setScreen('PROJECTS')
          }}
        >⌘</StudioIcon>

        <StudioIcon
          active={screen==='TOOLS'}
          onClick={()=>setScreen('TOOLS')}
        >◫</StudioIcon>

        <StudioIcon
          active={false}
          onClick={()=>location.href='/system'}
        >⚙</StudioIcon>

        <div className="nav-spacer"/>

        <StudioIcon
          active={false}
          onClick={()=>setUsageOpen(true)}
        >?</StudioIcon>
      </aside>

      <div className="ux-content">
        {screen==='HOME'&&renderHomeScreen()}
        <div className={
          screen==='WORKSPACE'
            ? 'persistent-workspace-host active'
            : 'persistent-workspace-host hidden'
        }>
          {renderWorkspaceScreen()}
        </div>
        {screen==='MCP'&&renderMcpScreen()}
        {screen==='PROJECTS'&&renderProjectLibraryScreen()}
        {screen==='TOOLS'&&renderToolsScreen()}
      </div>
    </div>

    <div className="ux-statusbar">
      <span><b className="status-green">●</b> 시스템 상태 정상</span>
      <span><b className="status-green">●</b> Ollama</span>
      <span><b className="status-blue">●</b> MCP {mcpServers.length}</span>
      <span><b className="status-green">●</b> PostgreSQL</span>
      <div className="statusbar-spacer"/>
      <span>Project #{selectedProjectId||'-'}</span>
      <span>{new Date().toLocaleTimeString()}</span>
    </div>

    {mcpAddOpen&&
      <div className="mcp-add-overlay" onMouseDown={e=>{if(e.target===e.currentTarget)closeMcpAddDialog()}}>
        <div className="mcp-add-dialog" role="dialog" aria-modal="true" aria-labelledby="mcp-add-title">
          <div className="mcp-add-head">
            <div>
              <strong id="mcp-add-title">MCP 연결 추가</strong>
              <small>서버를 등록한 뒤 Tool 목록을 자동 동기화합니다.</small>
            </div>
            <button type="button" onClick={closeMcpAddDialog} disabled={mcpAddBusy}>×</button>
          </div>

          <label className="mcp-add-field">
            <span>서버 이름</span>
            <input
              value={mcpAddForm.name}
              onChange={e=>setMcpAddForm(p=>({...p,name:e.target.value}))}
              placeholder="예: GitHub MCP"
              autoFocus
            />
          </label>

          <label className="mcp-add-field">
            <span>Endpoint</span>
            <input
              value={mcpAddForm.endpoint}
              onChange={e=>setMcpAddForm(p=>({...p,endpoint:e.target.value}))}
              placeholder="예: http://127.0.0.1:8001/mcp"
            />
          </label>

          <label className="mcp-add-field">
            <span>신뢰 수준</span>
            <select
              value={mcpAddForm.trust_level}
              onChange={e=>setMcpAddForm(p=>({...p,trust_level:e.target.value}))}
            >
              <option value="UNTRUSTED">UNTRUSTED · 매 실행 확인 권장</option>
              <option value="TRUSTED">TRUSTED · 신뢰된 서버</option>
            </select>
          </label>

          <label className="mcp-add-check">
            <input
              type="checkbox"
              checked={mcpAddForm.allow_read_without_prompt}
              onChange={e=>setMcpAddForm(p=>({...p,allow_read_without_prompt:e.target.checked}))}
            />
            읽기 Tool은 별도 확인 없이 허용
          </label>

          <label className="mcp-add-check">
            <input
              type="checkbox"
              checked={mcpAddForm.allow_write_without_prompt}
              onChange={e=>setMcpAddForm(p=>({...p,allow_write_without_prompt:e.target.checked}))}
            />
            쓰기 Tool은 별도 확인 없이 허용
          </label>

          {mcpAddError&&<div className="mcp-add-error">{mcpAddError}</div>}

          <div className="mcp-add-actions">
            <button type="button" onClick={closeMcpAddDialog} disabled={mcpAddBusy}>취소</button>
            <button type="button" className="primary" onClick={submitMcpServer} disabled={mcpAddBusy}>
              {mcpAddBusy?'등록/동기화 중...':'등록하고 Tool 동기화'}
            </button>
          </div>
        </div>
      </div>
    }

    {editorCloseConfirm&&
      <div
        className="editor-unsaved-overlay"
        onMouseDown={e=>e.stopPropagation()}
      >
        <div
          className="editor-unsaved-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="editor-unsaved-title"
          onMouseDown={e=>e.stopPropagation()}
        >
          <div className="editor-unsaved-icon">!</div>
          <div className="editor-unsaved-copy">
            <h3 id="editor-unsaved-title">저장되지 않은 파일이 있습니다.</h3>
            <p>정말 닫겠습니까?</p>
            <small>저장되지 않은 파일 {editorCloseConfirm.dirtyPaths.length}개</small>
            {editorCloseConfirm.error&&
              <div className="editor-unsaved-error">
                {editorCloseConfirm.error}
              </div>
            }
          </div>
          <div className="editor-unsaved-actions">
            <button
              type="button"
              className="primary"
              disabled={editorCloseConfirm.saving}
              onClick={()=>handleEditorCloseDecision('save')}
            >
              {editorCloseConfirm.saving?'저장 중...':'저장하고 닫기'}
            </button>
            <button
              type="button"
              className="danger"
              disabled={editorCloseConfirm.saving}
              onClick={()=>handleEditorCloseDecision('discard')}
            >
              저장 안하고 닫기
            </button>
            <button
              type="button"
              disabled={editorCloseConfirm.saving}
              onClick={()=>handleEditorCloseDecision('cancel')}
            >
              취소
            </button>
          </div>
        </div>
      </div>
    }

    {fileDeleteConfirm&&
      <div className="editor-unsaved-overlay" onMouseDown={e=>e.stopPropagation()}>
        <div className="editor-unsaved-dialog" role="dialog" aria-modal="true" onMouseDown={e=>e.stopPropagation()}>
          <div className="editor-unsaved-icon danger">!</div>
          <div className="editor-unsaved-copy">
            <h3>정말 삭제하시겠습니까?</h3>
            <p>선택한 파일 {fileDeleteConfirm.paths.length}개를 실제 디스크에서 삭제합니다.</p>
            {fileDeleteConfirm.dirtyCount>0&&
              <small>저장되지 않은 파일 {fileDeleteConfirm.dirtyCount}개도 함께 삭제됩니다.</small>
            }
            {fileDeleteConfirm.error&&<div className="editor-unsaved-error">{fileDeleteConfirm.error}</div>}
          </div>
          <div className="editor-unsaved-actions">
            <button
              type="button"
              className="danger"
              disabled={fileDeleteConfirm.deleting}
              onClick={confirmProjectFilesDelete}
            >{fileDeleteConfirm.deleting?'삭제 중...':'OK'}</button>
            <button
              type="button"
              disabled={fileDeleteConfirm.deleting}
              onClick={()=>setFileDeleteConfirm(null)}
            >취소</button>
          </div>
        </div>
      </div>
    }

    {externalChangeConfirm&&
      <div className="editor-unsaved-overlay" onMouseDown={e=>e.stopPropagation()}>
        <div className="editor-unsaved-dialog" role="dialog" aria-modal="true" onMouseDown={e=>e.stopPropagation()}>
          <div className="editor-unsaved-icon">↻</div>
          <div className="editor-unsaved-copy">
            <h3>외부에서 수정이 되었습니다.</h3>
            {externalChangeConfirm.mode==='save_conflict'
              ? <p>외부 파일과 현재 AgentStudio의 내용이 다릅니다. 어떻게 처리하시겠습니까?</p>
              : <p>수정된 외부 파일 로드하시겠습니까?</p>
            }
            <small>{externalChangeConfirm.path}</small>
            <small className="external-change-warning">
              {externalChangeConfirm.mode==='save_conflict'
                ? '외부 파일 무시하고 저장을 선택하면 현재 AgentStudio 내용으로 디스크 파일을 덮어씁니다.'
                : '외부 파일 로드를 선택하면 현재 AgentStudio에서 저장하지 않은 수정 내용은 사라집니다.'
              }
            </small>
            {externalChangeConfirm.error&&<div className="editor-unsaved-error">{externalChangeConfirm.error}</div>}
          </div>
          <div className="editor-unsaved-actions">
            <button
              type="button"
              className="primary"
              disabled={externalChangeConfirm.loading}
              onClick={()=>handleExternalChangeDecision('load_external')}
            >{externalChangeConfirm.loading&&externalChangeConfirm.loadingAction==='load_external'?'로드 중...':'외부 파일 로드'}</button>
            {externalChangeConfirm.mode==='save_conflict'&&
              <button
                type="button"
                className="danger"
                disabled={externalChangeConfirm.loading}
                onClick={()=>handleExternalChangeDecision('force_save')}
              >{externalChangeConfirm.loading&&externalChangeConfirm.loadingAction==='force_save'?'저장 중...':'외부 파일 무시하고 저장'}</button>
            }
            <button
              type="button"
              disabled={externalChangeConfirm.loading}
              onClick={()=>handleExternalChangeDecision('cancel')}
            >취소</button>
          </div>
        </div>
      </div>
    }

    {projectListOpen&&<div className="project-list-overlay" onClick={()=>setProjectListOpen(false)}>
      <div className="project-list-dialog redesigned" onClick={e=>e.stopPropagation()}>
        <div className="project-list-head">
          <div><span className="eyebrow">PROJECT LIBRARY</span><h2>프로젝트 불러오기</h2>
        {projectLoadProgress.active&&<div className={projectLoadProgress.failed?'project-load-progress modal failed':'project-load-progress modal'}>
          <div className="project-load-progress-head">
            <strong>{projectLoadProgress.message}</strong>
            <span>{projectLoadProgress.percent}%</span>
          </div>
          <div className="project-load-progress-track">
            <div className="project-load-progress-fill" style={{width:`${projectLoadProgress.percent}%`}} />
          </div>
        </div>}<p>저장된 프로젝트를 선택하면 바로 작업공간으로 이동합니다.</p></div>
          <button onClick={()=>setProjectListOpen(false)}>✕</button>
        </div>
        
        <div className="external-project-import">
          <div className="external-import-head">
            <div>
              <strong>DB에 없는 기존 프로젝트 분석</strong>
              <small>저장되지 않은 프로젝트도 폴더를 지정하면 바로 분석하고 열 수 있습니다.</small>
            </div>
          </div>

          <div className="external-path-row">
            <input
              value={externalProjectPath}
              onChange={e=>setExternalProjectPath(e.target.value)}
              placeholder="분석할 기존 프로젝트 경로"
            />
            <button
              type="button"
              className={
                externalProjectPickerLoading
                  ? 'external-path-picker-button busy'
                  : 'external-path-picker-button'
              }
              disabled={externalProjectPickerLoading}
              onClick={pickExternalProjectFolder}
              title="Windows 폴더 선택창 열기"
            >
              {externalProjectPickerLoading?'선택창 여는 중...':'경로 찾기'}
            </button>
            <button
              className="primary-install"
              disabled={externalProjectLoading||!externalProjectPath.trim()}
              onClick={analyzeExternalProject}
            >
              {externalProjectLoading?`${Math.round(externalProjectProgress||0)}% 분석 중...`:'프로젝트 분석'}
            </button>
          </div>

          {externalProjectPickerMessage&&
            <div className={
              externalProjectPickerMessage.startsWith('경로 선택 실패')
                ? 'external-path-picker-message error'
                : 'external-path-picker-message'
            }>
              {externalProjectPickerMessage}
            </div>}

          {(externalProjectLoading||externalProjectStatus)&&<div className={
            externalProjectStatus==='SUCCESS'
              ?'external-progress-box success'
              :externalProjectStatus==='FAILED'
                ?'external-progress-box failed'
                :'external-progress-box running'
          }>
            <div className="external-progress-head">
              <strong>
                {externalProjectStatus==='SUCCESS'
                  ?'분석 완료'
                  :externalProjectStatus==='FAILED'
                    ?'분석 실패'
                    :'프로젝트 분석 중'}
              </strong>
              <b>{Math.round(externalProjectProgress||0)}%</b>
            </div>

            <progress
              max="100"
              value={externalProjectProgress||0}
            />

            <div className="external-progress-step">
              {externalProjectStep||'분석 준비 중...'}
            </div>

            <div className="external-progress-stages">
              <span className={(externalProjectProgress||0)>=5?'done':''}>경로 확인</span>
              <span className={(externalProjectProgress||0)>=15?'done':''}>파일 스캔</span>
              <span className={(externalProjectProgress||0)>=40?'done':''}>소스 분석</span>
              <span className={(externalProjectProgress||0)>=82?'done':''}>DB 저장</span>
              <span className={(externalProjectProgress||0)>=100?'done':''}>완료</span>
            </div>

            {externalProjectStatus==='SUCCESS'&&
              <div className="auto-move-note">
                DB 저장이 완료되었습니다. 작업공간으로 자동 이동합니다.
              </div>}
          </div>}

          {externalProjectStatus==='FAILED'&&externalProjectAnalysis?.ok===false&&
            <div className="external-failure-detail">
              <div className="failure-title">분석 실패 상세</div>
              <div className="failure-message">
                {externalProjectAnalysis.message||externalProjectStep}
              </div>

              <div className="failure-label">로그 파일 전체 경로</div>
              <code className="failure-log-path">
                {externalProjectAnalysis.log_path||'로그 파일 저장에 실패했습니다.'}
              </code>

              {externalProjectAnalysis.traceback&&<details>
                <summary>상세 Traceback 보기</summary>
                <pre>{externalProjectAnalysis.traceback}</pre>
              </details>}
            </div>}

          {externalProjectAnalysis&&externalProjectAnalysis.ok!==false&&<div className="external-analysis-result">
            <div className="external-analysis-title">
              <div>
                <strong>{newAgentName||'기존 프로젝트'}</strong>
                <code>{externalProjectAnalysis.project_root}</code>
              </div>
              <span className="unregistered-chip">
                {externalProjectAnalysis.registered?'DB 등록됨':'DB 미등록'}
              </span>
            </div>

            {externalProjectAnalysis.summary&&<div className="external-summary-box">
              <div><b>프로젝트 요약</b></div>
              <pre>{typeof externalProjectAnalysis.summary==='string'
                ? externalProjectAnalysis.summary
                : JSON.stringify(externalProjectAnalysis.summary,null,2)}</pre>
            </div>}

            <div className="external-analysis-actions">
              <button className="hero-primary" onClick={openExternalProjectWorkspace}>
                분석 결과로 프로젝트 열기
              </button>
              {!externalProjectAnalysis.registered&&
                <button onClick={registerExternalProject}>이 프로젝트를 DB에 등록</button>}
            </div>
          </div>}
        </div>

        {projectListLoading&&<div className="project-list-empty">프로젝트 목록을 불러오는 중...</div>}
        {!projectListLoading&&projectList.length===0&&<div className="project-list-empty">저장된 프로젝트가 없습니다.<br/><button onClick={()=>{setProjectListOpen(false);startNewProject()}}>첫 프로젝트 만들기</button></div>}
        {!projectListLoading&&projectList.length>0&&<div className="project-list-items">
          {projectList.map(p=><button key={p.id} className="project-list-item" onClick={()=>loadProject(p.id)}>
            <div className="project-list-title"><strong>{p.name}</strong><span>#{p.id}</span></div>
            <div className="project-list-path">{p.project_root}</div>
            <div className="project-list-meta">
              <span>Cache {p.cache_path?'✓':'-'}</span><span>Models {p.models_path?'✓':'-'}</span>
            </div>
          </button>)}
        </div>}
      </div>
    </div>}

    {usageOpen&&<div className="project-list-overlay" onClick={()=>setUsageOpen(false)}>
      <div className="usage-dialog" onClick={e=>e.stopPropagation()}>
        <div className="project-list-head"><div><span className="eyebrow">QUICK GUIDE</span><h2>AgentStudio 사용 방법</h2></div><button onClick={()=>setUsageOpen(false)}>✕</button></div>
        <div className="usage-steps">
          <div><b>1</b><section><strong>신규 생성</strong><p>만들고 싶은 Agent의 목적부터 설명합니다. AI가 다음 질문을 하나씩 이어갑니다.</p></section></div>
          <div><b>2</b><section><strong>프로젝트 구성</strong><p>이름과 프로젝트 경로를 정합니다. Cache/Temp/Output/Venv/Models는 필요할 때만 별도 경로를 지정합니다.</p></section></div>
          <div><b>3</b><section><strong>프로젝트 생성</strong><p>FastAPI가 경로를 만들고 PostgreSQL projects 테이블에 저장합니다.</p></section></div>
          <div><b>4</b><section><strong>코딩 작업공간</strong><p>파일 편집, AI 코드 수정, Terminal, MCP, LangGraph Workflow, Memory를 사용합니다.</p></section></div>
          <div><b>5</b><section><strong>불러오기</strong><p>다음 실행에서는 불러오기에서 프로젝트를 선택해 이어서 작업합니다.</p></section></div>
        </div>
        <button className="hero-primary full" onClick={()=>{setUsageOpen(false);startNewProject()}}>신규 프로젝트 시작</button>
      </div>
    </div>}
  </div>
}
export default function App(){return location.pathname.startsWith('/system')?<SystemPage/>:<IDE/>}
