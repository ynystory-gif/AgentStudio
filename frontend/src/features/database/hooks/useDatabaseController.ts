import { useRef, useState } from 'react'
import { connectSqlDatabase, disconnectSqlDatabase, executeSql, fetchSqlObjects, previewDatabaseDesign } from '../services/databaseService'
type LegacyValue=any
type LegacyRecord=Record<string,any>
const DEFAULT_SQL_PROFILE={connection_id:'',name:'PostgreSQL 연결',db_type:'postgresql',host:'127.0.0.1',port:5432,database:'',schema_name:'',username:'postgres',password:'',driver:'ODBC Driver 18 for SQL Server',service_name:'FREEPDB1',project_id:'',service_account_json:'',dashboard_url:'',ssl_mode:'',trust_server_certificate:true,credential_saved:false}
export function useDatabaseController(){
  const [sqlProfile,setSqlProfile]=useState<LegacyRecord>({...DEFAULT_SQL_PROFILE})
  const [sqlConnections,setSqlConnections]=useState<LegacyValue[]>([])
  const [sqlSupabaseConnectionUrl,setSqlSupabaseConnectionUrl]=useState('')
  const [sqlConnectionImport,setSqlConnectionImport]=useState({busy:false,db_type:'',source_name:'',message:'',error:''})
  const [sqlDatabaseManual,setSqlDatabaseManual]=useState(false)
  const [sqlConnectionStatus,setSqlConnectionStatus]=useState<LegacyValue|null>(null)
  const [sqlConnectionBusy,setSqlConnectionBusy]=useState(false)
  const [sqlQueryBusy,setSqlQueryBusy]=useState(false)
  const sqlStopRequestedRef=useRef(false)
  const [sqlQueryResult,setSqlQueryResult]=useState<LegacyValue|null>(null)
  const [sqlResultTab,setSqlResultTab]=useState<'DATA'|'MESSAGES'>('DATA')
  const [sqlResultSetIndex,setSqlResultSetIndex]=useState(0)
  const [sqlMessages,setSqlMessages]=useState<LegacyValue[]>([])
  const [sqlDbObjects,setSqlDbObjects]=useState<LegacyValue|null>(null)
  const [sqlDbObjectsBusy,setSqlDbObjectsBusy]=useState(false)
  const [sqlDbObjectsError,setSqlDbObjectsError]=useState('')
  const [sqlDbObjectExpanded,setSqlDbObjectExpanded]=useState<LegacyRecord>({})
  const [sqlObjectActionBusy,setSqlObjectActionBusy]=useState('')
  const [sqlObjectContextMenu,setSqlObjectContextMenu]=useState<LegacyValue|null>(null)
  const [sqlSchemaContextMenu,setSqlSchemaContextMenu]=useState<LegacyValue|null>(null)
  const [sqlDatabaseContextMenu,setSqlDatabaseContextMenu]=useState<LegacyValue|null>(null)
  const [sqlAdminPrompt,setSqlAdminPrompt]=useState<LegacyValue|null>(null)
  const [sqliteProjectStatus,setSqliteProjectStatus]=useState<LegacyValue|null>(null)
  const [sqliteProjectStatusBusy,setSqliteProjectStatusBusy]=useState(false)
  const sqlLoadedRootRef=useRef('')
  const [databaseDesignFinalizeBusy,setDatabaseDesignFinalizeBusy]=useState(false)
  const [liveDatabasePreview,setLiveDatabasePreview]=useState<LegacyValue|null>(null)
  const [liveDatabasePreviewLoading,setLiveDatabasePreviewLoading]=useState(false)
  const [liveDatabasePreviewError,setLiveDatabasePreviewError]=useState('')
  const [liveDatabasePreviewTab,setLiveDatabasePreviewTab]=useState('MODULES')
  const liveDatabasePreviewRequestRef=useRef('')

  const pushSqlMessage=(type:string,text:string)=>setSqlMessages(prev=>[{type,text,time:new Date().toLocaleTimeString()},...prev].slice(0,100))

  const loadSqlObjects=async(root:string,{quiet=false}:LegacyRecord={})=>{
    if(!root)return null
    if(!quiet)setSqlDbObjectsBusy(true)
    setSqlDbObjectsError('')
    try{
      const objects=await fetchSqlObjects(root)
      setSqlDbObjects(objects)
      setSqlDbObjectExpanded(prev=>{
        const next={...prev}; const first=objects?.schemas?.[0]
        if(first){
          const sk=`schema:${first.name}`,tk=`category:${first.name}:tables`
          if(next[sk]===undefined)next[sk]=true
          if(next[tk]===undefined)next[tk]=true
        }
        return next
      })
      return objects
    }catch(error){setSqlDbObjects(null);setSqlDbObjectsError(String(error));return null}
    finally{if(!quiet)setSqlDbObjectsBusy(false)}
  }

  const connectSql=async(root:string,profile:LegacyRecord=sqlProfile)=>{
    if(!root)return null
    setSqlConnectionBusy(true)
    try{
      const status=await connectSqlDatabase(root,profile)
      setSqlConnectionStatus(status)
      pushSqlMessage('success',`${status?.profile?.name||String(status?.profile?.db_type||profile.db_type||'DB').toUpperCase()} 연결 성공`)
      return status
    }catch(error){setSqlConnectionStatus((prev:LegacyValue)=>({...prev,connected:false,error:String(error)}));pushSqlMessage('error',`DB 연결 실패: ${error}`);throw error}
    finally{setSqlConnectionBusy(false)}
  }

  const disconnectSql=async(root:string,connectionId:string)=>{
    if(!root)return null
    setSqlConnectionBusy(true)
    try{
      const status=await disconnectSqlDatabase(root,connectionId)
      setSqlConnectionStatus(status);setSqlDbObjects(null);setSqlDbObjectsError('');setSqlDbObjectExpanded({})
      pushSqlMessage('info',`${sqlProfile.name||'데이터베이스'} 연결을 해제했습니다.`)
      return status
    }catch(error){pushSqlMessage('error',`연결 해제 실패: ${error}`);throw error}
    finally{setSqlConnectionBusy(false)}
  }

  const runSql=async(root:string,statement:string,label='SQL')=>{
    if(!root||!statement.trim())return null
    sqlStopRequestedRef.current=false;setSqlQueryBusy(true)
    try{
      const result=await executeSql(root,statement,1000)
      setSqlQueryResult(result)
      const count=Array.isArray(result?.result_sets)?result.result_sets.length:0
      setSqlResultSetIndex(count?count-1:0);setSqlResultTab(count||result?.columns?.length?'DATA':'MESSAGES')
      pushSqlMessage('success',`${label} 실행 완료 · ${result?.message||''} · ${result?.elapsed_ms||0}ms`)
      return result
    }catch(error){
      setSqlResultTab('MESSAGES')
      pushSqlMessage(sqlStopRequestedRef.current?'warning':'error',sqlStopRequestedRef.current?`${label} 실행을 사용자가 중지했습니다.`:`${label} 실행 실패: ${error}`)
      throw error
    }finally{setSqlQueryBusy(false);sqlStopRequestedRef.current=false}
  }

  const rebuildDatabasePreview=async(request:string,confirmedRequirements:LegacyRecord)=>{
    setLiveDatabasePreviewLoading(true);setLiveDatabasePreviewError('')
    try{
      const result=await previewDatabaseDesign(request,confirmedRequirements)
      const plan=result?.database_plan||{}
      const preview={...plan,ddl_preview:String(result?.ddl_preview||'')}
      setLiveDatabasePreview(preview)
      return {result,plan,preview}
    }catch(error){setLiveDatabasePreviewError(String(error));throw error}
    finally{setLiveDatabasePreviewLoading(false)}
  }

  return {sqlProfile,setSqlProfile,sqlConnections,setSqlConnections,sqlSupabaseConnectionUrl,setSqlSupabaseConnectionUrl,sqlConnectionImport,setSqlConnectionImport,sqlDatabaseManual,setSqlDatabaseManual,sqlConnectionStatus,setSqlConnectionStatus,sqlConnectionBusy,setSqlConnectionBusy,sqlQueryBusy,setSqlQueryBusy,sqlStopRequestedRef,sqlQueryResult,setSqlQueryResult,sqlResultTab,setSqlResultTab,sqlResultSetIndex,setSqlResultSetIndex,sqlMessages,setSqlMessages,pushSqlMessage,sqlDbObjects,setSqlDbObjects,sqlDbObjectsBusy,setSqlDbObjectsBusy,sqlDbObjectsError,setSqlDbObjectsError,sqlDbObjectExpanded,setSqlDbObjectExpanded,sqlObjectActionBusy,setSqlObjectActionBusy,sqlObjectContextMenu,setSqlObjectContextMenu,sqlSchemaContextMenu,setSqlSchemaContextMenu,sqlDatabaseContextMenu,setSqlDatabaseContextMenu,sqlAdminPrompt,setSqlAdminPrompt,sqliteProjectStatus,setSqliteProjectStatus,sqliteProjectStatusBusy,setSqliteProjectStatusBusy,sqlLoadedRootRef,databaseDesignFinalizeBusy,setDatabaseDesignFinalizeBusy,liveDatabasePreview,setLiveDatabasePreview,liveDatabasePreviewLoading,setLiveDatabasePreviewLoading,liveDatabasePreviewError,setLiveDatabasePreviewError,liveDatabasePreviewTab,setLiveDatabasePreviewTab,liveDatabasePreviewRequestRef,loadSqlObjects,connectSql,disconnectSql,runSql,rebuildDatabasePreview}
}
