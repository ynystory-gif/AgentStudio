import React, { useEffect, useRef, useState } from 'react'
import { loadSystemOverview, systemApi as api, apiFetch, runtimeInfo, saveBlobToOutput } from './services/systemService'
import { asLegacyError } from '../../utils/errors'
import {
  GpuSettingsPanel,
  OllamaSettingsPanel,
  RuntimeDatabasePanel,
  ServicePortSettingsPanel,
  SystemStatusSummary,
} from '../../components/system/SystemRuntimePanels'
import { CodexSettingsPanel } from '../codex/components/CodexSettingsPanel'

export function SystemPage() {
  const [status,setStatus]=useState<LegacyRecord>({})
  const [runtimeLoopStatus,setRuntimeLoopStatus]=useState<LegacyValue|null>(null)
  const [settings,setSettings]=useState<LegacyRecord>({})
  const [tests,setTests]=useState<LegacyRecord>({})
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [pgvectorInstall,setPgvectorInstall]=useState<LegacyValue|null>(null)
  const [pgvectorInfo,setPgvectorInfo]=useState<LegacyValue|null>(null)
  const [pgPathCheck,setPgPathCheck]=useState<LegacyValue|null>(null)
  const [pgAdminUser,setPgAdminUser]=useState('postgres')
  const [pgAdminPassword,setPgAdminPassword]=useState('')
  const [agentDbName,setAgentDbName]=useState('theanova_agentstudio')
  const [agentDbUser,setAgentDbUser]=useState('theanova_agentstudio_app')
  const [agentDbPassword,setAgentDbPassword]=useState('')
  const [dbProvision,setDbProvision]=useState<LegacyValue|null>(null)
  const [ollamaInstall,setOllamaInstall]=useState<LegacyValue|null>(null)
  const [ollamaRuntime,setOllamaRuntime]=useState<LegacyValue|null>(null)
  const [ollamaRuntimeBusy,setOllamaRuntimeBusy]=useState(false)
  const [gpuRuntime,setGpuRuntime]=useState<LegacyValue|null>(null)
  const [gpuRuntimeBusy,setGpuRuntimeBusy]=useState(false)
  const [portInfo,setPortInfo]=useState<LegacyValue|null>(null)
  const [portCheckBusy,setPortCheckBusy]=useState(false)
  const [machineName,setMachineName]=useState('')
  const [machineNameBusy,setMachineNameBusy]=useState(false)
  const [databaseRuntime,setDatabaseRuntime]=useState<LegacyValue|null>(null)
  const [databaseProviderChoice,setDatabaseProviderChoice]=useState('local')
  const [supabaseRuntimeUrl,setSupabaseRuntimeUrl]=useState('')
  const [supabaseLanggraphRuntimeUrl,setSupabaseLanggraphRuntimeUrl]=useState('')
  const [supabaseRuntimeSchema,setSupabaseRuntimeSchema]=useState('theanova_agentstudio')
  const [databaseRuntimeBusy,setDatabaseRuntimeBusy]=useState(false)
  const [supabaseInfoSaveBusy,setSupabaseInfoSaveBusy]=useState(false)
  const [databaseRuntimeResult,setDatabaseRuntimeResult]=useState<LegacyValue|null>(null)
  const pgAdminPasswordRef=useRef<LegacyValue|null>(null)
  const agentDbPasswordRef=useRef<LegacyValue|null>(null)

  const readPgAdminPassword=()=>String(pgAdminPasswordRef.current?.value ?? pgAdminPassword ?? '')
  const readAgentDbPassword=()=>String(agentDbPasswordRef.current?.value ?? agentDbPassword ?? '')

  const refresh=async()=>{
    try{
      const overview=await loadSystemOverview()
      const s=overview.status
      const cfg=overview.settings
      setStatus(s);setSettings(cfg);setMachineName(cfg?._machine?.pending_pc_name||cfg?._machine?.pc_name||'');setError('')
      setOllamaRuntime(overview.ollamaRuntime);setGpuRuntime(overview.gpuRuntime);setPortInfo(overview.portInfo)
      if(overview.databaseRuntime){
        const dbRuntime=overview.databaseRuntime
        setDatabaseRuntime(dbRuntime)
        setDatabaseProviderChoice(dbRuntime?.selected_provider||dbRuntime?.active_provider||'local')
        setSupabaseRuntimeSchema(String(dbRuntime?.supabase_schema||'theanova_agentstudio'))
      }else setDatabaseRuntime(null)
    }catch(e){setError(String(e))}
  }

  useEffect(()=>{refresh()},[])

  const valueOf=(key: LegacyValue)=>{
    const v=settings[key]
    if(v && typeof v==='object' && 'configured' in v) return ''
    return v ?? ''
  }

  const configured=(key: LegacyValue)=>{
    const v=settings[key]
    return !!(v && typeof v==='object' && v.configured)
  }

  const setValue=(key: LegacyValue,value: LegacyValue)=>setSettings((p: LegacyValue)=>({...p,[key]:value}))

  const saveGroup=async(keys: LegacyValue)=>{
    setBusy(true); setMessage(''); setError('')
    try{
      const values:LegacyRecord={}
      keys.forEach((k: LegacyValue)=>{ values[k]=valueOf(k) })
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
      // 응답도 DB가 아니라 프로젝트 루트 .env에서 재읽은 실제 저장값입니다.
      setSettings((prev: LegacyValue)=>({
        ...prev,
        DATABASE_URL:r?.saved?.DATABASE_URL ?? payload.database_url,
        LANGGRAPH_DATABASE_URL:r?.saved?.LANGGRAPH_DATABASE_URL ?? payload.langgraph_database_url,
        POSTGRESQL18_ROOT:r?.saved?.POSTGRESQL18_ROOT ?? payload.postgresql_root
      }))
      setMessage(`${r.message||'DB 연결 설정을 .env에 저장했습니다.'} 저장 위치: ${r.env_path||'프로젝트 루트 .env'}`)
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

  const downloadSupabaseSchemaScript=async()=>{
    try{
      const response=await apiFetch('/settings/database-runtime/supabase/schema-script')
      const blob=await response.blob()
      const saved=await saveBlobToOutput(blob,'theanova_agentstudio_supabase_schema.sql','sql')
      setMessage(`Supabase 스키마 SQL 저장 완료: ${saved.path}`)
    }catch(e){ setError(`Supabase 스키마 SQL 저장 실패: ${e instanceof Error?asLegacyError(e).message:String(e)}`) }
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
      const backendPort=Number(valueOf('AGENTSTUDIO_BACKEND_PORT')||window.__AGENTSTUDIO_CONFIG__?.BACKEND_PORT||0)
      const frontendPort=Number(valueOf('AGENTSTUDIO_FRONTEND_PORT')||window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT||0)

      if(!Number.isInteger(backendPort)||backendPort<1024||backendPort>65535){
        throw new Error('Backend 포트는 1024~65535 사이의 숫자를 입력하세요.')
      }
      if(!Number.isInteger(frontendPort)||frontendPort<1024||frontendPort>65535){
        throw new Error('Frontend 포트는 1024~65535 사이의 숫자를 입력하세요.')
      }

      const currentFrontendPort=Number(window.location.port||window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT||0)
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
    setValue('AGENTSTUDIO_BACKEND_PORT',String(result.backend?.recommended||window.__AGENTSTUDIO_CONFIG__?.BACKEND_PORT||''))
    setValue('AGENTSTUDIO_FRONTEND_PORT',String(result.frontend?.recommended||window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT||''))
    setMessage('추천 포트를 입력했습니다. 포트 설정 저장 후 SYSTEM_ADMIN.cmd를 다시 실행하면 적용됩니다.')
  }

  const savePortSettings=async()=>{
    const backendPort=Number(valueOf('AGENTSTUDIO_BACKEND_PORT')||window.__AGENTSTUDIO_CONFIG__?.BACKEND_PORT||0)
    const frontendPort=Number(valueOf('AGENTSTUDIO_FRONTEND_PORT')||window.__AGENTSTUDIO_CONFIG__?.FRONTEND_PORT||0)
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

  const portStateLabel=(state: LegacyValue)=>(({ 
    current:'현재 AgentStudio 사용 중',
    available:'사용 가능',
    in_use:'다른 프로그램이 사용 중',
    conflict_with_backend:'Backend 포트와 중복'
  } as LegacyRecord)[state]||state||'-')

  const testOne=async(name: LegacyValue)=>{
    setBusy(true)
    try{
      const options:RequestInit={method:'POST'}
      if(name==='postgresql' || name==='pgvector'){
        options.body=JSON.stringify({database_url:String(valueOf('DATABASE_URL')||'').trim()})
      }
      const r=await api(`/settings/test/${name}`,options)
      setTests((p: LegacyValue)=>({...p,[name]:r}))
    }catch(e){
      setTests((p: LegacyValue)=>({...p,[name]:{ok:false,message:String(e)}}))
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


  const pollPgvectorJob=async(jobId: LegacyValue)=>{
    let unchanged=0
    let lastSignature=''

    for(let i=0;i<240;i++){
      try{
        const j=await api(`/jobs/${jobId}`)
        const signature=`${j.status}|${j.progress}|${j.message}`

        if(signature===lastSignature) unchanged++
        else unchanged=0
        lastSignature=signature

        setPgvectorInstall((current: LegacyValue)=>({
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
        setPgvectorInstall((current: LegacyValue)=>({
          ...(current||{}),
          message:`Job 상태 확인 중 오류: ${String(e)}`
        }))
      }

      await new Promise((r: LegacyValue)=>setTimeout(r,1000))
    }

    setBusy(false)
    setPgvectorInstall((current: LegacyValue)=>({
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
      setTests((p: LegacyValue)=>({...p,postgresqlAdmin:r}))
    }catch(e){
      setTests((p: LegacyValue)=>({...p,postgresqlAdmin:{ok:false,message:String(e)}}))
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
    const missing:LegacyValue[]=[]
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


  const refreshGpuRuntime=async()=>{
    try{
      const runtime=await api('/settings/gpu/runtime/status')
      setGpuRuntime(runtime)
      return runtime
    }catch(e){
      setGpuRuntime({ok:false,available:false,enabled:false,message:String(e)})
      return null
    }
  }

  const startGpuRuntime=async()=>{
    setGpuRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/gpu/runtime/start',{method:'POST'})
      setGpuRuntime(result)
      if(result?.ok){
        setMessage(result.message||'GPU 가속을 시작했습니다.')
        setTimeout(()=>{ refreshGpuRuntime(); refreshOllamaRuntime() },300)
      }else{
        setError(result?.message||'GPU 가속 시작에 실패했습니다.')
      }
    }catch(e){
      setError('GPU 가속 시작 실패: '+String(e))
    }finally{
      setGpuRuntimeBusy(false)
    }
  }

  const stopGpuRuntime=async()=>{
    if(!window.confirm('AgentStudio GPU 가속을 정지하시겠습니까?\n\nAgentStudio 관리 Ollama와 생성 Agent 테스트는 가능한 경우 CPU 모드로 실행됩니다.')) return
    setGpuRuntimeBusy(true)
    setMessage('')
    setError('')
    try{
      const result=await api('/settings/gpu/runtime/stop',{method:'POST'})
      setGpuRuntime(result)
      if(result?.ok){
        setMessage(result.message||'GPU 가속을 정지했습니다.')
        setTimeout(()=>{ refreshGpuRuntime(); refreshOllamaRuntime() },300)
      }else{
        setError(result?.message||'GPU 가속 정지에 실패했습니다.')
      }
    }catch(e){
      setError('GPU 가속 정지 실패: '+String(e))
    }finally{
      setGpuRuntimeBusy(false)
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

  const pollOllamaJob=async(jobId: LegacyValue)=>{
    for(let i=0;i<600;i++){
      try{
        const j=await api(`/jobs/${jobId}`)
        setOllamaInstall((current: LegacyValue)=>({
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
        setOllamaInstall((p: LegacyValue)=>({...p,message:'설치 상태 확인 실패: '+String(e)}))
      }
      await new Promise((r: LegacyValue)=>setTimeout(r,1000))
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


  const cancelSystemJob=async(jobId: LegacyValue,label: LegacyValue='작업')=>{
    if(!jobId) return
    try{
      await api(`/jobs/${encodeURIComponent(jobId)}/cancel`,{method:'POST'})
      setMessage(`${label} 실행 중지 요청을 보냈습니다.`)
      setBusy(false)
    }catch(e){
      setError(`${label} 실행 중지 실패: ${String(e)}`)
    }
  }


  const chooseFolder=async(name: LegacyValue,label: LegacyValue)=>{
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

  const renderPathField=(label: LegacyValue,name: LegacyValue,placeholder: LegacyValue='')=><label className="setting-field">
    <span>{label}</span>
    <div className="path-input-row">
      <input
        type="text"
        value={valueOf(name)}
        placeholder={placeholder}
        onChange={(e: LegacyValue)=>setValue(name,e.target.value)}
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

  const renderField=(label: string,name: string,type: string='text',placeholder: string='')=><label className="setting-field">
    <span>{label}</span>
    <input
      type={type}
      value={valueOf(name)}
      placeholder={configured(name) ? '설정됨 - 변경할 때만 새 값을 입력' : placeholder}
      onChange={(e: LegacyValue)=>setValue(name,e.target.value)}
    />
  </label>

  const renderTestResult=(name: string)=>{
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
        단, <b>DATABASE URL / LangGraph DB URL은 DB 연결 자체에 필요한 bootstrap 정보이므로 예외적으로 프로젝트 루트 .env에만 저장</b>하며 app_settings에는 저장하지 않습니다.
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
            onChange={(e: LegacyValue)=>setMachineName(e.target.value)}
            onKeyDown={(e: LegacyValue)=>{if(e.key==='Enter'&&!e.nativeEvent?.isComposing){e.preventDefault();saveMachineName()}}}
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
          아래 경로는 신규 Agent뿐 아니라 AgentStudio 런타임에도 실제 적용됩니다. Temp는 임시 작업파일, Cache는 pip/Hugging Face/Torch/OCR/브라우저 캐시, Output은 다운로드·내보내기·녹음/Transcript 결과 파일의 기본 저장 위치입니다. C: 공간이 부족하면 다른 드라이브를 지정하세요.
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
            onChange={(e: LegacyValue)=>setValue('WEATHER_AUTO_LOCATION',e.target.checked?'true':'false')}
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
          <input value={pgAdminUser} onChange={(e: LegacyValue)=>setPgAdminUser(e.target.value)} placeholder="예: postgres"/>
        </label>
        <label className="setting-field">
          <span>PostgreSQL 관리자 비밀번호 (저장하지 않음)</span>
          <input ref={pgAdminPasswordRef} type="password" value={pgAdminPassword} onInput={(e: LegacyValue)=>setPgAdminPassword(e.currentTarget.value)} onChange={(e: LegacyValue)=>setPgAdminPassword(e.target.value)} autoComplete="new-password" placeholder="DB 생성/pgvector 관리자 작업에만 사용"/>
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
            <input value={agentDbName} onChange={(e: LegacyValue)=>setAgentDbName(e.target.value)}/>
          </label>
          <label className="setting-field">
            <span>AgentStudio 앱 사용자</span>
            <input value={agentDbUser} onChange={(e: LegacyValue)=>setAgentDbUser(e.target.value)}/>
          </label>
          <label className="setting-field">
            <span>AgentStudio 앱 비밀번호 (저장하지 않음)</span>
            <input ref={agentDbPasswordRef} type="password" value={agentDbPassword} onInput={(e: LegacyValue)=>setAgentDbPassword(e.currentTarget.value)} onChange={(e: LegacyValue)=>setAgentDbPassword(e.target.value)} autoComplete="new-password"/>
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
          <b>저장 위치:</b> DATABASE URL과 LangGraph DB URL은 DB 연결 이전에 필요한 bootstrap 설정이므로 <b>프로젝트 루트 .env에만 저장</b>합니다.
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
        <label className="setting-checkbox-row">
          <input
            type="checkbox"
            checked={String(valueOf('OPENAI_ENABLED')||'true').toLowerCase()!=='false'}
            onChange={(e: LegacyValue)=>setValue('OPENAI_ENABLED',e.target.checked?'true':'false')}
          />
          <span>OpenAI 사용</span>
        </label>
        <div className="hint-box">
          <b>OpenAI 사용</b>을 끄면 OpenAI API를 Provider 후보에서 제외합니다. 일반 AI 작업과 Embedding은 Ollama를 우선 사용하며,
          Codex를 별도로 켠 경우 복잡한 코딩/요구사항 작업은 Codex까지 마지막 보조 Provider로 사용할 수 있습니다. 저장된 OpenAI API Key는 삭제하지 않습니다.
        </div>
        {renderField("OpenAI API Key","OPENAI_API_KEY","password","")}
        {renderField("GPT 코딩 모델","OPENAI_MODEL","text","")}
        {renderField("Embedding 모델","OPENAI_EMBEDDING_MODEL","text","")}
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['OPENAI_ENABLED','OPENAI_API_KEY','OPENAI_MODEL','OPENAI_EMBEDDING_MODEL'])}>OpenAI 설정 저장</button>
          <button disabled={String(valueOf('OPENAI_ENABLED')||'true').toLowerCase()==='false'} onClick={()=>testOne('openai')}>OpenAI 연결 테스트</button>
        </div>
        {String(valueOf('OPENAI_ENABLED')||'true').toLowerCase()==='false'&&
          <div className="test-result okbox">OpenAI 비사용 · OpenAI API 호출을 하지 않습니다. Ollama가 우선이며 Codex 사용 설정은 별도로 적용됩니다.</div>}
        {renderTestResult("openai")}
      </section>

      <CodexSettingsPanel
        enabled={String(valueOf('CODEX_ENABLED')||'false').toLowerCase()==='true'}
        busy={busy}
        onEnabledChange={(enabled: LegacyValue)=>setValue('CODEX_ENABLED',enabled?'true':'false')}
        onSave={()=>saveGroup(['CODEX_ENABLED'])}
      />

      <GpuSettingsPanel
        busy={gpuRuntimeBusy}
        runtime={gpuRuntime}
        onStart={startGpuRuntime}
        onStop={stopGpuRuntime}
        onRefresh={refreshGpuRuntime}
      />

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
        <h2>AI Provider 라우팅</h2>
        <label>Provider 전략
          <select value={String(valueOf('AI_PROVIDER_STRATEGY')||'ollama_first')} onChange={(e: LegacyValue)=>setValue('AI_PROVIDER_STRATEGY',e.target.value)}>
            <option value="ollama_first">자동 · 일반 Ollama 우선 / 고난도 Codex 우선</option>
            <option value="manual">수동 Provider 지정</option>
          </select>
        </label>
        <label>로컬/일반 작업 Provider
          <select value={String(valueOf('LOCAL_LLM_PROVIDER')||'auto')} onChange={(e: LegacyValue)=>setValue('LOCAL_LLM_PROVIDER',e.target.value)}>
            <option value="auto">자동</option><option value="ollama">Ollama</option><option value="openai">OpenAI API</option>
          </select>
        </label>
        <label>코딩 Provider
          <select value={String(valueOf('CODING_LLM_PROVIDER')||'auto')} onChange={(e: LegacyValue)=>setValue('CODING_LLM_PROVIDER',e.target.value)}>
            <option value="auto">자동</option><option value="ollama">Ollama</option><option value="openai">OpenAI API</option><option value="codex">Codex</option>
          </select>
        </label>
        <label>요구사항/Agent 설계 Provider
          <select value={String(valueOf('REQUIREMENTS_LLM_PROVIDER')||'auto')} onChange={(e: LegacyValue)=>setValue('REQUIREMENTS_LLM_PROVIDER',e.target.value)}>
            <option value="auto">자동</option><option value="ollama">Ollama</option><option value="openai">OpenAI API</option><option value="codex">Codex</option>
          </select>
        </label>
        <div className="hint-box">
          자동 모드에서는 일반 요약·분류·인터뷰·간단한 코드 작업은 <b>Ollama 우선</b>으로 처리하고 필요한 작업만 OpenAI/Codex로 보조합니다.
          반대로 <b>Workflow 전체/LangGraph 분기, DB Entity·관계, 복잡한 다중파일 변경, 실행·디버깅·대규모 수정</b>은
          활성화된 Provider 기준 <b>Codex → OpenAI → Ollama</b> 순으로 품질을 우선합니다. 수동 모드에서는 아래 Provider 선택값을 존중합니다.
        </div>
        <div className="panel-actions">
          <button disabled={busy} onClick={()=>saveGroup(['AI_PROVIDER_STRATEGY','LOCAL_LLM_PROVIDER','CODING_LLM_PROVIDER','REQUIREMENTS_LLM_PROVIDER'])}>라우팅 설정 저장</button>
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
