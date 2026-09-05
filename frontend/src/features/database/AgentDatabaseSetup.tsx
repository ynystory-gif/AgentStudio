import { useEffect, useState } from 'react'
import { api } from '../../api'

export const createDefaultAgentDatabaseSetup=()=>({
  mode:'PENDING',
  postgresql:{
    enabled:false,auto_provision:false,use_existing:false,analyze_existing:false,
    host:'127.0.0.1',port:'5432',database:'',schema:'public',user:'postgres',password:'',
    ssl:true,sslmode:'prefer',pgvector:false,role:'영구 데이터 · 관계형 데이터 · Agent Memory',
  },
  firestore:{
    enabled:false,auto_provision:false,use_existing:false,analyze_existing:false,
    project_id:'',database_id:'(default)',service_account_path:'',region:'',emulator:false,
    collection_prefix:'',initial_collections:'',map_design_entities:true,
    role:'Document 기반 데이터 · Agent Event · 사용자 설정 · 실시간 상태',
  },
  redis:{
    enabled:false,auto_provision:false,use_existing:false,
    host:'127.0.0.1',port:'6379',db:'0',username:'',password:'',tls:false,key_prefix:'',
    role:'Session · Cache · TTL 데이터 · Queue · Lock · 작업 상태',
  },
})

export const normalizeAgentDatabaseSetup=(value:LegacyValue=null)=>{
  const base=createDefaultAgentDatabaseSetup()
  const source=value&&typeof value==='object'?value:{}
  const providerEnabled=(provider: LegacyValue)=>{
    const row=source?.[provider]||{}
    // v5.535: `enabled` is the current UI/source-of-truth field.
    // `use_in_agent` is legacy/persisted compatibility only. When both exist
    // and disagree, prefer the current `enabled` value so a checkbox click
    // cannot be reverted by stale `use_in_agent:false`.
    if(Object.prototype.hasOwnProperty.call(row,'enabled')) return Boolean(row.enabled)
    return Boolean(row.use_in_agent)
  }
  const postgresqlEnabled=providerEnabled('postgresql')
  const firestoreEnabled=providerEnabled('firestore')
  const redisEnabled=providerEnabled('redis')
  return {
    ...base,...source,mode:String(source.mode||base.mode).toUpperCase(),
    postgresql:{...base.postgresql,...(source.postgresql||{}),enabled:postgresqlEnabled,use_in_agent:postgresqlEnabled,password:String(source?.postgresql?.password||'')},
    firestore:{...base.firestore,...(source.firestore||{}),enabled:firestoreEnabled,use_in_agent:firestoreEnabled,service_account_path:String(source?.firestore?.service_account_path||'')},
    redis:{...base.redis,...(source.redis||{}),enabled:redisEnabled,use_in_agent:redisEnabled,password:String(source?.redis?.password||''),tls:Boolean(source?.redis?.tls??source?.redis?.ssl)},
  }
}

export const safeAgentDatabaseSetup=(value:LegacyValue=null)=>{
  const setup=normalizeAgentDatabaseSetup(value)
  const collectionText=Array.isArray(setup.firestore.initial_collections)?setup.firestore.initial_collections.join(', '):String(setup.firestore.initial_collections||'')
  return {
    mode:setup.mode,
    providers:['postgresql','firestore','redis'].filter((key: LegacyValue)=>setup[key]?.enabled),
    postgresql:{
      enabled:Boolean(setup.postgresql.enabled),use_in_agent:Boolean(setup.postgresql.enabled),auto_provision:Boolean(setup.postgresql.auto_provision),
      use_existing:Boolean(setup.postgresql.use_existing),analyze_existing:Boolean(setup.postgresql.analyze_existing),
      host:setup.postgresql.host,port:Number(setup.postgresql.port||5432),database:setup.postgresql.database,schema:setup.postgresql.schema||'public',user:setup.postgresql.user,
      ssl:Boolean(setup.postgresql.ssl),sslmode:setup.postgresql.sslmode||'prefer',pgvector:Boolean(setup.postgresql.pgvector),role:setup.postgresql.role||'',password_env:'POSTGRES_PASSWORD',
    },
    firestore:{
      enabled:Boolean(setup.firestore.enabled),use_in_agent:Boolean(setup.firestore.enabled),auto_provision:Boolean(setup.firestore.auto_provision),
      use_existing:Boolean(setup.firestore.use_existing),analyze_existing:Boolean(setup.firestore.analyze_existing),project_id:setup.firestore.project_id,database_id:setup.firestore.database_id||'(default)',
      region:setup.firestore.region||'',emulator:Boolean(setup.firestore.emulator),collection_prefix:setup.firestore.collection_prefix,
      initial_collections:collectionText.split(/[,;\n]+/).map((v: LegacyValue)=>v.trim()).filter(Boolean),map_design_entities:setup.firestore.map_design_entities!==false,role:setup.firestore.role||'',credentials_env:'GOOGLE_APPLICATION_CREDENTIALS',
    },
    redis:{
      enabled:Boolean(setup.redis.enabled),use_in_agent:Boolean(setup.redis.enabled),auto_provision:Boolean(setup.redis.auto_provision),use_existing:Boolean(setup.redis.use_existing),
      host:setup.redis.host,port:Number(setup.redis.port||6379),db:Number(setup.redis.db||0),username:setup.redis.username,tls:Boolean(setup.redis.tls),ssl:Boolean(setup.redis.tls),
      key_prefix:setup.redis.key_prefix,role:setup.redis.role||'',password_env:'REDIS_PASSWORD',
    },
  }
}

export const selectedAgentDatabaseProviders=(value:LegacyValue=null)=>{
  const setup=normalizeAgentDatabaseSetup(value)
  return [setup.postgresql.enabled?'PostgreSQL':'',setup.firestore.enabled?'Google Cloud Firestore':'',setup.redis.enabled?'Redis':''].filter(Boolean)
}

export const databaseModeLabel=(mode: LegacyValue)=>({
  CONFIGURE:'지금 DB 설정',CONNECTION_ONLY:'연결 정보만 사용',NO_DB:'DB 없이 생성',SKIP:'이번 단계 건너뛰기',LATER_EDITOR:'Agent Editor에서 나중에 설정',PENDING:'선택 필요'
}[String(mode||'PENDING').toUpperCase()]||mode)

export function AgentDatabaseResourcePlanPanel({plan,onChange,onApprove,onBack,onEditStructure,busy=false}:LegacyRecord){
  if(!plan) return null
  const providers=Array.isArray(plan.providers)?plan.providers:[]
  const commitProviders=(nextProviders: LegacyValue)=>onChange?.({...plan,approved:false,requires_approval:nextProviders.some((row: LegacyValue)=>Boolean(row.auto_provision&&row.include_in_provision!==false)),providers:nextProviders})
  const patchProvider=(provider: LegacyValue,patch: LegacyValue)=>commitProviders(providers.map((row: LegacyValue)=>row.provider===provider?{...row,...patch}:row))
  const patchResources=(provider: LegacyValue,patch: LegacyValue)=>commitProviders(providers.map((row: LegacyValue)=>row.provider===provider?{...row,resources:{...(row.resources||{}),...patch}}:row))
  const patchTablePolicy=(provider: LegacyValue,tableName: LegacyValue,key: LegacyValue,checked: LegacyValue)=>{
    const row=providers.find((item: LegacyValue)=>item.provider===provider)
    const resources=row?.resources||{}
    const overrides={...(resources.table_policy_overrides||{})}
    overrides[tableName]={...(overrides[tableName]||{}),[key]:Boolean(checked)}
    patchResources(provider,{table_policy_overrides:overrides})
  }
  return <div className={`agent-db-resource-plan ${plan.approved?'approved':''}`}>
    <div className="agent-db-resource-plan-head"><div><strong>DB Resource Plan / DB 생성 계획 Preview</strong><small>실제 DB는 아직 변경되지 않았습니다. 생성할 구조를 확인·수정한 뒤 승인하세요.</small></div><span>{plan.approved?'승인 완료':plan.requires_approval?'승인 필요':'자동 생성 없음'}</span></div>
    {providers.map((row: LegacyValue)=>{
      const r=row.resources||{}
      return <section className="agent-db-resource-provider" key={row.provider}>
        <header><div><strong>{row.provider==='postgresql'?'PostgreSQL':row.provider==='firestore'?'Google Cloud Firestore':'Redis'}</strong><small>{row.role||''}</small></div><label><input type="checkbox" checked={row.include_in_provision!==false&&Boolean(row.auto_provision)} disabled={!row.auto_provision||plan.approved} onChange={(e: LegacyValue)=>patchProvider(row.provider,{include_in_provision:e.target.checked})}/><span>실제 구조 생성 포함</span></label></header>
        {r.existing_structure&&<div className="agent-db-existing-summary">기존 구조 분석: {r.existing_structure.message||'분석 결과 반영됨'}</div>}
        {row.provider==='postgresql'&&<>
          <div className="agent-db-resource-grid">
            <label><span>Schema</span><input value={r.schema||''} disabled={plan.approved} onChange={(e: LegacyValue)=>patchResources(row.provider,{schema:e.target.value})}/></label>
            <div><span>Tables</span><code>{(r.tables||[]).join(', ')||'없음'}</code></div>
            <div><span>Indexes</span><code>{(r.indexes||[]).join(', ')||'설계에 따라 생성'}</code></div>
            <div><span>pgvector</span><code>{r.pgvector_extension?'Extension / Vector Column / Vector Index':'사용 안 함'}</code></div>
          </div>
          {(r.table_details||[]).length>0&&<div className="agent-table-policy-preview">
            <div className="agent-table-policy-head"><strong>테이블 자동 생성 공통 정책</strong><small>CRUD 성격을 분석해 테이블명 기반 PK / Audit / Soft Delete를 추천합니다. 기본 PK는 단순 id가 아니라 {'{table_name}_id'} 규칙을 사용합니다.</small></div>
            {(r.table_details||[]).map((table: LegacyValue,index: LegacyValue)=>{
              const policy=table.common_policy||{}
              const recommended=policy.recommendations||{}
              const override=(r.table_policy_overrides||{})[table.name]||{}
              const enabled=(key: LegacyValue)=>Object.prototype.hasOwnProperty.call(override,key)?Boolean(override[key]):Boolean(recommended[key])
              const policyColumnTypes={created_at:'TIMESTAMPTZ',updated_at:'TIMESTAMPTZ',is_deleted:'BOOLEAN',created_by:'BIGINT',updated_by:'BIGINT'}
              const policyKeys=Object.keys(policyColumnTypes)
              const displayColumns=(table.columns||[]).filter((col: LegacyValue)=>!policyKeys.includes(col.name)||enabled(col.name)).map((col: LegacyValue)=>({...col}))
              for(const key of policyKeys) if(enabled(key)&&!displayColumns.some((col: LegacyValue)=>col.name===key)) displayColumns.push({name:key,type:(policyColumnTypes as LegacyRecord)[key],primary_key:false,unique:false})
              return <details className="agent-table-policy-row" key={table.name||index} open={index===0}>
                <summary><div><strong>{table.name}</strong><small>CRUD {(table.crud||[]).join(' / ')||'-'} · {Object.keys(override).length?'USER_FIXED':(policy.status||'RECOMMENDED')}</small></div><span>{(table.columns||[]).length} Columns</span></summary>
                <div className="agent-table-policy-body">
                  <div className="agent-table-policy-checks">{[['id','테이블명 기반 ID'],['created_at','등록일'],['updated_at','수정일'],['is_deleted','삭제 여부'],['created_by','등록자 ID'],['updated_by','수정자 ID']].map(([key,label]: LegacyValue)=><label key={key}><input type="checkbox" checked={enabled(key)} disabled={plan.approved||key==='id'} onChange={(e: LegacyValue)=>patchTablePolicy(row.provider,table.name,key,e.target.checked)}/><span>{label}</span></label>)}</div>
                  <div className="agent-table-policy-columns">{displayColumns.map((col: LegacyValue)=><code key={col.name}>{col.name} {col.type}{col.primary_key?' · PK':''}{col.unique?' · UNIQUE':''}</code>)}</div>
                  <small className="agent-table-policy-reason">{(policy.reason||[]).join(' · ')}</small>
                  {enabled('is_deleted')&&(table.columns||[]).some((col: LegacyValue)=>col.unique)&&<small className="agent-table-policy-note">Soft Delete + UNIQUE는 활성 데이터만 대상으로 Partial Unique Index를 생성합니다.</small>}
                </div>
              </details>
            })}
          </div>}
        </>}
        {row.provider==='firestore'&&<div className="agent-db-resource-grid">
          <label className="span-2"><span>Collections · 쉼표 구분</span><textarea rows={2} disabled={plan.approved} value={(r.collections||[]).join(', ')} onChange={(e: LegacyValue)=>patchResources(row.provider,{collections:e.target.value.split(/[,;\n]+/).map((v: LegacyValue)=>v.trim()).filter(Boolean)})}/></label>
          <div><span>Document / Field</span><code>Collection별 Document Schema / Field 구조</code></div>
          <div><span>Index / Rules</span><code>Composite Index · Security Rules · Initial Document</code></div>
        </div>}
        {row.provider==='redis'&&<div className="agent-db-resource-grid">
          <label><span>Prefix</span><input value={r.prefix||''} disabled={plan.approved} onChange={(e: LegacyValue)=>patchResources(row.provider,{prefix:e.target.value})}/></label>
          <label className="span-2"><span>Key Patterns · 한 줄에 하나</span><textarea rows={4} disabled={plan.approved} value={(r.key_patterns||[]).map((x: LegacyValue)=>typeof x==='string'?x:(x.pattern||x.key||'')).filter(Boolean).join('\n')} onChange={(e: LegacyValue)=>patchResources(row.provider,{key_patterns:e.target.value.split(/\r?\n/).map((v: LegacyValue)=>v.trim()).filter(Boolean).map((pattern: LegacyValue)=>({pattern,type:'STRING',ttl:'',purpose:''}))})}/></label>
          <div><span>Data Structure</span><code>Hash · List · Set · Sorted Set · Stream · TTL</code></div>
        </div>}
      </section>
    })}
    <div className="agent-db-resource-plan-actions">
      <button type="button" onClick={onBack} disabled={busy}>← 이전 단계 / DB 설정</button>
      <button type="button" onClick={onEditStructure} disabled={busy}>구조 수정</button>
      <button type="button" onClick={()=>commitProviders(providers.map((row: LegacyValue)=>({...row,include_in_provision:false})))} disabled={busy||plan.approved}>전체 DB 생성 제외</button>
      <button type="button" className="primary" onClick={onApprove} disabled={busy||plan.approved||!plan.requires_approval}>{plan.approved?'승인 완료':'전체 DB 생성 계획 승인'}</button>
    </div>
  </div>
}

export function AgentDatabaseSetupPanel({value,projectRoot='',onChange,onTest,onAnalyze,onCreateResource,onPickFirestoreCredential,firestoreCredentialBusy=false,testBusy=false,testResult=null,analyzeBusy='',analyzeResult=null,createBusy='',createResult=null,databaseNeeded=false,onBuildPlan,planBusy=false,resourcePlan=null,onResourcePlanChange,onApprovePlan,onBackFromPlan,editorMode=false,onOpenDatabaseDesign}:LegacyRecord){
  const setup=normalizeAgentDatabaseSetup(value)
  const [activeProvider,setActiveProvider]=useState('postgresql')
  const [accountDbProfiles,setAccountDbProfiles]=useState<LegacyValue[]>([])
  const [accountProfileBusy,setAccountProfileBusy]=useState(false)
  const [hasSavedProjectDatabaseSetting,setHasSavedProjectDatabaseSetting]=useState(false)
  useEffect(()=>{
    let cancelled=false
    const root=String(projectRoot||'').trim()
    if(!root){setAccountDbProfiles([]);setHasSavedProjectDatabaseSetting(false);return}
    api(`/account-settings/project?project_root=${encodeURIComponent(root)}`).then((result:LegacyValue)=>{
      if(cancelled)return
      setAccountDbProfiles(Array.isArray(result?.account_database_profiles)?result.account_database_profiles:[])
      setHasSavedProjectDatabaseSetting(Boolean((result?.items||[]).some((item:LegacyValue)=>String(item?.setting_group||'').startsWith('DATABASE'))))
    }).catch(()=>{if(!cancelled){setAccountDbProfiles([]);setHasSavedProjectDatabaseSetting(false)}})
    return()=>{cancelled=true}
  },[projectRoot])

  const applyAccountDatabaseProfile=async(profile:LegacyValue)=>{
    if(!profile)return
    const kind=String(profile.db_type||'').toLowerCase()
    let next=normalizeAgentDatabaseSetup(setup)
    if(kind==='postgresql'||kind==='supabase'){
      next={...next,mode:'CONFIGURE',postgresql:{...next.postgresql,enabled:true,use_in_agent:true,use_existing:true,host:profile.host||next.postgresql.host,port:String(profile.port||5432),database:profile.database||'',schema:profile.schema_name||'public',user:profile.username||'',ssl:String(profile.ssl_mode||'').toLowerCase()!=='disable'}}
      setActiveProvider('postgresql')
    }else if(kind==='redis'){
      next={...next,mode:'CONFIGURE',redis:{...next.redis,enabled:true,use_in_agent:true,use_existing:true,host:profile.host||next.redis.host,port:String(profile.port||6379),db:String(profile.database||0),username:profile.username||''}}
      setActiveProvider('redis')
    }else if(kind==='firestore'){
      next={...next,mode:'CONFIGURE',firestore:{...next.firestore,enabled:true,use_in_agent:true,use_existing:true,project_id:profile.project_id||'',database_id:profile.database||'(default)',service_account_path:profile.service_account_json||''}}
      setActiveProvider('firestore')
    }else return
    onChange?.(next)
    const root=String(projectRoot||'').trim()
    if(root){
      setAccountProfileBusy(true)
      try{
        const bindingKey=kind==='supabase'?'postgresql':kind
        await api('/account-settings/project',{method:'PUT',body:JSON.stringify({project_root:root,setting_group:'DATABASE_PROFILE_BINDING',setting_key:bindingKey,value:{account_profile_id:profile.account_profile_id||profile.account_database_profiles_id,connection_id:profile.connection_id,name:profile.name,db_type:profile.db_type,provider:bindingKey},source_profile_id:profile.account_profile_id||profile.account_database_profiles_id,title:'계정 DB 설정을 Agent 프로젝트에 적용',summary:profile.name||profile.db_type})})
        setHasSavedProjectDatabaseSetting(true)
      }catch{}finally{setAccountProfileBusy(false)}
    }
  }

  const configure=['CONFIGURE','CONNECTION_ONLY'].includes(setup.mode)
  const selectedProviders=selectedAgentDatabaseProviders(setup)
  const patchProvider=(provider: LegacyValue,patch: LegacyValue)=>{
    const nextPatch={...patch}
    if(Object.prototype.hasOwnProperty.call(nextPatch,'enabled')){
      nextPatch.use_in_agent=Boolean(nextPatch.enabled)
    }
    onChange?.({...setup,mode:setup.mode==='PENDING'?'CONFIGURE':setup.mode,[provider]:{...setup[provider],...nextPatch}})
  }
  const providerEnabledToggle=(provider: LegacyValue,label: LegacyValue)=>{
    const enabled=Boolean(setup?.[provider]?.enabled)
    return <button
      type="button"
      className={`agent-db-provider-toggle-checkbox ${enabled?'checked':''}`}
      role="checkbox"
      aria-checked={enabled}
      onClick={()=>patchProvider(provider,{enabled:!enabled})}
      title={`${label} ${enabled?'사용 해제':'사용'}`}
    ><span className="agent-db-provider-checkbox-glyph" aria-hidden="true">{enabled?'✓':''}</span><b>{label}</b></button>
  }
  const setMode=(mode: LegacyValue)=>{
    const next={...setup,mode}
    if(mode==='CONNECTION_ONLY') for(const key of ['postgresql','firestore','redis']) next[key]={...next[key],auto_provision:false}
    if(['NO_DB','SKIP','LATER_EDITOR'].includes(mode)) for(const key of ['postgresql','firestore','redis']) next[key]={...next[key],enabled:false,use_in_agent:false,auto_provision:false}
    onChange?.(next)
  }
  const renderTestState=(provider: LegacyValue)=>{
    const row=(testResult?.providers||[]).find((item: LegacyValue)=>item?.provider===provider)
    if(!row) return null
    return <small className={row.ok?'agent-db-test-result ok':'agent-db-test-result failed'}>{row.ok?'✓':'✕'} {row.message||provider}</small>
  }
  const renderAnalyzeState=(provider: LegacyValue)=>{const row=analyzeResult?.[provider]||(analyzeResult?.provider===provider?analyzeResult:null);return row?<small className={row.ok?'agent-db-test-result ok':'agent-db-test-result failed'}>{row.ok?'✓':'✕'} {row.message}</small>:null}
  const renderCreateState=(provider: LegacyValue)=>{const row=createResult?.[provider]||(createResult?.provider===provider?createResult:null);return row?<small className={row.ok?'agent-db-test-result ok':'agent-db-test-result failed'}>{row.ok?'✓':'✕'} {row.message}</small>:null}
  const providerActions=(provider: LegacyValue,cfg: LegacyValue)=><div className="agent-db-provider-actions">
    <button type="button" onClick={()=>onTest?.(provider)} disabled={testBusy||Boolean(createBusy)}>{testBusy?'확인 중...':'연결 테스트'}</button>
    {provider==='postgresql'&&<button type="button" className="resource-create" onClick={()=>onCreateResource?.('postgresql')} title={setup.mode==='CONNECTION_ONLY'?'연결 정보만 사용 모드에서는 실제 DB 리소스를 생성하지 않습니다.':'입력한 Database에 Schema만 생성합니다.'} disabled={createBusy==='postgresql'||testBusy||setup.mode==='CONNECTION_ONLY'}>{createBusy==='postgresql'?'스키마 생성 중...':'PostgreSQL 스키마 생성'}</button>}
    {provider==='firestore'&&!cfg.emulator&&<button type="button" className="resource-create" onClick={()=>onCreateResource?.('firestore')} title={setup.mode==='CONNECTION_ONLY'?'연결 정보만 사용 모드에서는 실제 DB 리소스를 생성하지 않습니다.':'입력한 Project / Database ID / Region으로 Firestore Database를 생성합니다.'} disabled={createBusy==='firestore'||testBusy||setup.mode==='CONNECTION_ONLY'}>{createBusy==='firestore'?'Database 생성 중...':'Firestore Database 생성'}</button>}
    {cfg.use_existing&&<button type="button" onClick={()=>onAnalyze?.(provider)} disabled={analyzeBusy===provider||Boolean(createBusy)}>{analyzeBusy===provider?'분석 중...':'기존 구조 분석'}</button>}
    {renderTestState(provider)}{renderAnalyzeState(provider)}{renderCreateState(provider)}
  </div>

  if(resourcePlan) return <AgentDatabaseResourcePlanPanel plan={resourcePlan} onChange={onResourcePlanChange} onApprove={onApprovePlan} onBack={onBackFromPlan} onEditStructure={onOpenDatabaseDesign} busy={planBusy}/>

  return <div className={`agent-db-setup-card ${setup.mode.toLowerCase()} ${databaseNeeded?'database-needed':''}`}>
    <div className="agent-db-setup-head"><div><strong>{editorMode?'Agent Editor · Database 구성':'Database 구성'}</strong><small>DB 사용 여부와 실제 DB 구조 생성 여부는 서로 독립적으로 설정합니다. PostgreSQL + Firestore + Redis를 동시에 사용할 수 있습니다.</small></div><span>{databaseModeLabel(setup.mode)}</span></div>
    <div className="agent-account-db-profiles">
      <div><strong>계정 저장 DB 설정</strong><small>{hasSavedProjectDatabaseSetting?'현재 프로젝트 Database 설정이 저장되어 있습니다. 필요하면 계정의 다른 DB 설정을 다시 적용할 수 있습니다.':'현재 프로젝트 Database 설정이 아직 없습니다. 계정에 저장된 DB 연결 목록에서 초기값을 선택할 수 있습니다.'}</small></div>
      {accountDbProfiles.length?<div className="agent-account-db-profile-list">{accountDbProfiles.map((profile:LegacyValue)=><button type="button" key={profile.account_profile_id||profile.account_database_profiles_id||profile.connection_id} disabled={accountProfileBusy} onClick={()=>void applyAccountDatabaseProfile(profile)}><b>{profile.name||'DB 연결'}</b><span>{String(profile.db_type||'').toUpperCase()}</span><small>{[profile.host,profile.database||profile.project_id].filter(Boolean).join(' / ')||'계정 저장 설정'}</small></button>)}</div>:<small className="agent-db-no-account-profile">계정에 저장된 DB 설정이 없습니다. 코드 편집의 DB 연결에서 연결 정보를 저장하면 이 목록에도 등록됩니다.</small>}
      <em>비밀번호 원문은 공용 DB 테이블에 저장하지 않고 Windows DPAPI/Secret 정책을 유지합니다. 프로젝트별 설정은 Agent 설계의 ‘지금 저장’에서도 별도 DB 항목으로 보관됩니다.</em>
    </div>
    <div className="agent-db-mode-actions multi">
      <button type="button" className={setup.mode==='CONFIGURE'?'active':''} onClick={()=>setMode('CONFIGURE')}>지금 DB 설정</button>
      <button type="button" className={setup.mode==='CONNECTION_ONLY'?'active':''} onClick={()=>setMode('CONNECTION_ONLY')}>연결 정보만 사용</button>
      <button type="button" className={setup.mode==='NO_DB'?'active skip':''} onClick={()=>setMode('NO_DB')}>DB 없이 Agent 생성</button>
      <button type="button" className={setup.mode==='SKIP'?'active skip':''} onClick={()=>setMode('SKIP')}>DB 설정 건너뛰기</button>
      <button type="button" className={setup.mode==='LATER_EDITOR'?'active':''} onClick={()=>setMode('LATER_EDITOR')}>Agent Editor에서 나중에 설정</button>
    </div>
    {setup.mode==='PENDING'&&<div className="agent-db-decision-note">{databaseNeeded?'요구사항에서 DB 필요성이 확인되었습니다. DB 설정 방법을 선택하세요.':'DB가 필요하면 설정하고, 필요하지 않으면 DB 없이 생성하거나 건너뛸 수 있습니다.'}</div>}

    {configure&&<div className="agent-db-provider-tabs">
      {[['postgresql','PostgreSQL'],['firestore','Firestore'],['redis','Redis']].map(([key,label]: LegacyValue)=><button type="button" key={key} className={`${activeProvider===key?'active':''} ${setup[key]?.enabled?'enabled':''}`} onClick={()=>setActiveProvider(key)}>{setup[key]?.enabled?'✓ ':''}{label}</button>)}
    </div>}
    {configure&&<div className="agent-db-provider-list">
      <section className={`agent-db-provider ${setup.postgresql.enabled?'enabled':''} ${activeProvider==='postgresql'?'active-provider':''}`}>
        <header>{providerEnabledToggle('postgresql','PostgreSQL 사용')}<small>Schema / Table / PK / FK / Index / Constraint / pgvector / Trigger / Seed</small></header>
        {setup.postgresql.enabled&&<div className="agent-db-field-grid">
          <label><span>Host</span><input value={setup.postgresql.host} onChange={(e: LegacyValue)=>patchProvider('postgresql',{host:e.target.value})}/></label><label><span>Port</span><input value={setup.postgresql.port} onChange={(e: LegacyValue)=>patchProvider('postgresql',{port:e.target.value})}/></label>
          <label><span>Database Name</span><input value={setup.postgresql.database} onChange={(e: LegacyValue)=>patchProvider('postgresql',{database:e.target.value})}/></label><label><span>Schema</span><input value={setup.postgresql.schema} onChange={(e: LegacyValue)=>patchProvider('postgresql',{schema:e.target.value})}/></label>
          <label><span>Username</span><input value={setup.postgresql.user} onChange={(e: LegacyValue)=>patchProvider('postgresql',{user:e.target.value})}/></label><label><span>Password</span><input type="password" value={setup.postgresql.password} onChange={(e: LegacyValue)=>patchProvider('postgresql',{password:e.target.value})} autoComplete="new-password"/></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.postgresql.ssl)} onChange={(e: LegacyValue)=>patchProvider('postgresql',{ssl:e.target.checked,sslmode:e.target.checked?'prefer':'disable'})}/><span>SSL 사용</span></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.postgresql.pgvector)} onChange={(e: LegacyValue)=>patchProvider('postgresql',{pgvector:e.target.checked})}/><span>pgvector 사용</span></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.postgresql.auto_provision)} disabled={setup.mode==='CONNECTION_ONLY'} onChange={(e: LegacyValue)=>patchProvider('postgresql',{auto_provision:e.target.checked})}/><span>Agent 생성 시 DB 구조 자동 생성</span></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.postgresql.use_existing)} onChange={(e: LegacyValue)=>patchProvider('postgresql',{use_existing:e.target.checked})}/><span>기존 DB / Schema 사용</span></label>
          <label className="span-2"><span>추천 역할 · 수정 가능</span><input value={setup.postgresql.role} onChange={(e: LegacyValue)=>patchProvider('postgresql',{role:e.target.value})}/></label>
          {providerActions('postgresql',setup.postgresql)}
        </div>}
      </section>

      <section className={`agent-db-provider ${setup.firestore.enabled?'enabled':''} ${activeProvider==='firestore'?'active-provider':''}`}>
        <header>{providerEnabledToggle('firestore','Google Cloud Firestore 사용')}<small>Database / Collection / Document / Field / Composite Index / Security Rules</small></header>
        {setup.firestore.enabled&&<div className="agent-db-field-grid">
          <label><span>Google Cloud Project ID</span><input value={setup.firestore.project_id} onChange={(e: LegacyValue)=>patchProvider('firestore',{project_id:e.target.value})}/></label><label><span>Firestore Database ID</span><input value={setup.firestore.database_id} onChange={(e: LegacyValue)=>patchProvider('firestore',{database_id:e.target.value})}/></label>
          <label className="span-2"><span>Credential / Service Account JSON</span><div className="agent-db-path-picker"><input value={setup.firestore.service_account_path} onChange={(e: LegacyValue)=>patchProvider('firestore',{service_account_path:e.target.value})} placeholder="파일 경로 또는 ADC"/><button type="button" onClick={()=>onPickFirestoreCredential?.()} disabled={firestoreCredentialBusy}>{firestoreCredentialBusy?'찾는 중...':'파일 찾기'}</button></div></label>
          <label><span>Region / Location</span><input value={setup.firestore.region} onChange={(e: LegacyValue)=>patchProvider('firestore',{region:e.target.value})}/></label><label><span>Collection Prefix</span><input value={setup.firestore.collection_prefix} onChange={(e: LegacyValue)=>patchProvider('firestore',{collection_prefix:e.target.value})}/></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.firestore.emulator)} onChange={(e: LegacyValue)=>patchProvider('firestore',{emulator:e.target.checked})}/><span>Emulator 사용</span></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.firestore.auto_provision)} disabled={setup.mode==='CONNECTION_ONLY'} onChange={(e: LegacyValue)=>patchProvider('firestore',{auto_provision:e.target.checked})}/><span>Agent 생성 시 Firestore 구조 자동 구성</span></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.firestore.use_existing)} onChange={(e: LegacyValue)=>patchProvider('firestore',{use_existing:e.target.checked})}/><span>기존 Firestore Database 사용</span></label>
          <label className="span-2"><span>추천 역할 · 수정 가능</span><input value={setup.firestore.role} onChange={(e: LegacyValue)=>patchProvider('firestore',{role:e.target.value})}/></label>
          {providerActions('firestore',setup.firestore)}
        </div>}
      </section>

      <section className={`agent-db-provider ${setup.redis.enabled?'enabled':''} ${activeProvider==='redis'?'active-provider':''}`}>
        <header>{providerEnabledToggle('redis','Redis 사용')}<small>Prefix / Key Pattern / Hash / List / Set / Sorted Set / Stream / TTL / Session / Cache / Lock / Queue</small></header>
        {setup.redis.enabled&&<div className="agent-db-field-grid">
          <label><span>Host</span><input value={setup.redis.host} onChange={(e: LegacyValue)=>patchProvider('redis',{host:e.target.value})}/></label><label><span>Port</span><input value={setup.redis.port} onChange={(e: LegacyValue)=>patchProvider('redis',{port:e.target.value})}/></label>
          <label><span>Database Number</span><input value={setup.redis.db} onChange={(e: LegacyValue)=>patchProvider('redis',{db:e.target.value})}/></label><label><span>Username</span><input value={setup.redis.username} onChange={(e: LegacyValue)=>patchProvider('redis',{username:e.target.value})}/></label>
          <label><span>Password</span><input type="password" value={setup.redis.password} onChange={(e: LegacyValue)=>patchProvider('redis',{password:e.target.value})} autoComplete="new-password"/></label><label><span>Key Prefix</span><input value={setup.redis.key_prefix} onChange={(e: LegacyValue)=>patchProvider('redis',{key_prefix:e.target.value})} placeholder="예: SJ_"/></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.redis.tls)} onChange={(e: LegacyValue)=>patchProvider('redis',{tls:e.target.checked})}/><span>TLS 사용</span></label>
          {setup.redis.tls&&['127.0.0.1','localhost','::1'].includes(String(setup.redis.host||'').trim().toLowerCase())&&<div className="agent-db-inline-warning span-2">로컬 Redis 기본 포트 6379는 일반적으로 TLS를 사용하지 않습니다. 연결 테스트가 Timeout이면 AgentStudio가 비TLS로 한 번 재시도하고 성공 시 TLS를 자동 해제합니다.</div>}
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.redis.auto_provision)} disabled={setup.mode==='CONNECTION_ONLY'} onChange={(e: LegacyValue)=>patchProvider('redis',{auto_provision:e.target.checked})}/><span>Agent 생성 시 Redis 초기 구조 구성</span></label>
          <label className="agent-db-check"><input type="checkbox" checked={Boolean(setup.redis.use_existing)} onChange={(e: LegacyValue)=>patchProvider('redis',{use_existing:e.target.checked})}/><span>기존 Redis 사용</span></label>
          <label className="span-2"><span>추천 역할 · 수정 가능</span><input value={setup.redis.role} onChange={(e: LegacyValue)=>patchProvider('redis',{role:e.target.value})}/></label>
          {providerActions('redis',setup.redis)}
        </div>}
      </section>
    </div>}

    {configure&&<div className="agent-db-setup-actions"><div><strong>DB 사용과 DB 구조 자동 생성은 별도 설정</strong><small>연결 정보 입력만으로 실제 DB를 변경하지 않습니다. 자동 생성 ON인 DB가 있으면 먼저 Resource Plan Preview를 생성하고 사용자 승인을 받습니다.</small></div><button type="button" className="primary" onClick={onBuildPlan} disabled={planBusy||selectedProviders.length===0}>{planBusy?'생성 계획 만드는 중...':'DB Resource Plan Preview'}</button></div>}
    {testResult?.validation?.errors?.length>0&&<div className="agent-db-validation-errors">{testResult.validation.errors.map((item: LegacyValue,index: LegacyValue)=><span key={index}>• {item}</span>)}</div>}
    {editorMode&&<div className="agent-db-editor-note"><div><strong>기존 Agent DB 변경</strong><small>DB 신규 추가/제거, 연결 정보 변경, Schema/Table/Collection/Redis Key 정책 변경은 Preview와 사용자 승인 후 적용합니다. 기존 기능/데이터 보존을 우선하고 Migration/영향 범위를 먼저 확인합니다.</small></div><button type="button" onClick={onOpenDatabaseDesign}>DB 변경 영향 / Migration Plan</button></div>}
    <p className="agent-db-secret-note">보안: PostgreSQL/Redis Password와 Google Cloud Credential은 Agent Source에 저장하지 않습니다. 환경변수/Secret으로 분리하고 UI 마스킹 및 로그 Redaction을 적용합니다.</p>
  </div>
}


export function AgentDatabaseProvisionResultPanel({result,onRetry,onSkip,busyProvider=''}:LegacyRecord){
  const provision=result?.database_provision
  const rows=Array.isArray(provision?.providers)?provision.providers:[]
  if(!provision||!rows.length) return null
  return <div className={`agent-db-provision-result ${provision.ok?'ok':'failed'}`}>
    <div className="agent-db-provision-result-head"><div><strong>Database 구성 결과</strong><small>DB별 연결/구조 생성 결과를 확인하고 실패한 DB만 다시 처리할 수 있습니다.</small></div><span>{provision.ok?'PASS':'일부 실패'}</span></div>
    {rows.map((row: LegacyValue,index: LegacyValue)=><div className={`agent-db-provision-row ${row.ok?'ok':'failed'}`} key={`${row.provider}-${index}`}>
      <div><strong>{row.provider}</strong><small>{row.message||''}</small>{row.steps&&<code>{Object.entries(row.steps).map(([k,v]: LegacyValue)=>`${k}: ${v}`).join(' · ')}</code>}{row.rollback&&<em>Rollback 가능 여부: {row.rollback}</em>}</div>
      {!row.ok&&row.provider!=='runtime_config'&&<div className="agent-db-provision-actions"><button type="button" onClick={()=>onRetry?.(row.provider)} disabled={busyProvider===row.provider}>{busyProvider===row.provider?'재시도 중...':'재시도'}</button><button type="button" onClick={()=>onSkip?.(row.provider)}>해당 DB만 Skip</button></div>}
    </div>)}
  </div>
}
