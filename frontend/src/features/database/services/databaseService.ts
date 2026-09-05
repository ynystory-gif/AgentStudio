import { api } from '../../../api'
type LegacyRecord=Record<string,any>
export const fetchSqlObjects=(root:string)=>api(`/sql/objects?root=${encodeURIComponent(root)}`)
export const connectSqlDatabase=(root:string,profile:LegacyRecord)=>api('/sql/connect',{method:'POST',body:JSON.stringify({...profile,root})})
export const disconnectSqlDatabase=(root:string,connectionId:string)=>api('/sql/disconnect',{method:'POST',body:JSON.stringify({root,connection_id:connectionId||''})})
export const executeSql=(root:string,sql:string,maxRows=1000)=>api('/sql/execute',{method:'POST',body:JSON.stringify({root,sql,max_rows:maxRows})})
export const previewDatabaseDesign=(request:string,confirmedRequirements:LegacyRecord)=>api('/database-design/preview',{method:'POST',body:JSON.stringify({request,confirmed_requirements:confirmedRequirements})})

export const finalizeDatabaseDesignPlan=(databasePlan:LegacyRecord)=>api('/database-design/finalize',{method:'POST',body:JSON.stringify({database_plan:databasePlan})})
