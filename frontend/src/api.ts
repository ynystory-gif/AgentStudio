import type {
  AgentStudioRuntimeConfig,
  ApiErrorKind,
  JobEvent,
  RuntimeInfo
} from './types/common'

const AUTH_TOKEN_KEY='theanova.agentstudio.auth.token'
export function getAuthToken():string{return localStorage.getItem(AUTH_TOKEN_KEY)||sessionStorage.getItem(AUTH_TOKEN_KEY)||''}
export function setAuthToken(token:string,remember:boolean):void{clearAuthToken();(remember?localStorage:sessionStorage).setItem(AUTH_TOKEN_KEY,token)}
export function clearAuthToken():void{localStorage.removeItem(AUTH_TOKEN_KEY);sessionStorage.removeItem(AUTH_TOKEN_KEY)}

export class AgentStudioApiError extends Error {
  readonly kind: ApiErrorKind
  readonly network: boolean
  readonly apiBase: string
  readonly url: string
  readonly path: string
  readonly status?: number
  readonly responseBody?: string
  override readonly cause?: unknown
  constructor(message:string,details:{kind:ApiErrorKind;apiBase:string;url:string;path:string;status?:number;responseBody?:string;cause?:unknown}){
    super(message);this.name=details.kind==='network'?'BackendFetchError':'BackendHttpError';this.kind=details.kind;this.network=details.kind==='network';this.apiBase=details.apiBase;this.url=details.url;this.path=details.path;this.status=details.status;this.responseBody=details.responseBody;this.cause=details.cause
  }
}
function getRuntimeConfig():AgentStudioRuntimeConfig{return window.__AGENTSTUDIO_CONFIG__||{}}
function getApiBase():string{const cfg=getRuntimeConfig();const runtimeBase=String(cfg.API_BASE_URL||'').trim();if(runtimeBase)return runtimeBase.replace(/\/$/,'');throw new Error('AgentStudio runtime-config.js에 API_BASE_URL이 없습니다. SYSTEM_ADMIN.cmd를 다시 실행해 프로젝트 루트 .env 설정을 적용하세요.')}
function getWsBase():string{const cfg=getRuntimeConfig();const runtimeBase=String(cfg.WS_BASE_URL||'').trim();if(runtimeBase)return runtimeBase.replace(/\/$/,'');throw new Error('AgentStudio runtime-config.js에 WS_BASE_URL이 없습니다. SYSTEM_ADMIN.cmd를 다시 실행해 프로젝트 루트 .env 설정을 적용하세요.')}
export async function apiFetch(path:string,options:RequestInit={}):Promise<Response>{
  const apiBase=getApiBase(),url=`${apiBase}${path}`,token=getAuthToken();let res:Response
  const incomingHeaders=(options.headers||{}) as Record<string,string>
  const headers:Record<string,string>={...(token?{Authorization:`Bearer ${token}`}:{ }),...incomingHeaders}
  if(options.body!==undefined&&options.body!==null&&!Object.keys(headers).some((key: LegacyValue)=>key.toLowerCase()==='content-type'))headers['Content-Type']='application/json'
  try{
    res=await fetch(url,{...options,headers})
  }catch(cause){
    if(cause instanceof DOMException&&cause.name==='AbortError')throw cause
    throw new AgentStudioApiError(`Backend 연결 실패: ${url}`,{kind:'network',apiBase,url,path,cause})
  }
  if(!res.ok){const body=await res.text();let detail=body||res.statusText;try{const parsed=JSON.parse(body) as {detail?:unknown;message?:unknown};if(typeof parsed.detail==='string'&&parsed.detail.trim())detail=parsed.detail;else if(typeof parsed.message==='string'&&parsed.message.trim())detail=parsed.message}catch{}
    if(res.status===404&&path.startsWith('/ui-themes'))detail='Theme API를 찾을 수 없습니다. Frontend와 Backend 버전이 다른 경우가 많습니다. SYSTEM_ADMIN에서 AgentStudio를 완전히 재시작한 뒤 다시 시도하세요.'
    if(res.status===401&&!path.startsWith('/auth/'))clearAuthToken()
    throw new AgentStudioApiError(`Backend HTTP ${res.status}: ${detail}`,{kind:'http',status:res.status,apiBase,url,path,responseBody:body})
  }
  return res
}
export type DynamicApiResponse=LegacyRecord
export async function api<T=DynamicApiResponse>(path:string,options:RequestInit={}):Promise<T>{
  const res=await apiFetch(path,options)
  return res.json() as Promise<T>
}
export async function saveBlobToOutput(blob:Blob,filename:string,category: LegacyValue='downloads',projectRoot: LegacyValue=''):Promise<{ok:boolean;path:string;output_root:string;relative_path:string;bytes:number}>{
  const params=new URLSearchParams({filename:String(filename||'download.bin'),category:String(category||'downloads')})
  if(projectRoot)params.set('project_root',projectRoot)
  const res=await apiFetch(`/output/save?${params.toString()}`,{method:'POST',headers:{'Content-Type':blob.type||'application/octet-stream'},body:blob})
  return res.json()
}
export function connectJobs(onEvent:(event:JobEvent)=>void):WebSocket{const token=getAuthToken();const ws=new WebSocket(`${getWsBase()}${token?`?access_token=${encodeURIComponent(token)}`:''}`);ws.onmessage=(event: LegacyValue)=>onEvent(JSON.parse(event.data) as JobEvent);ws.onopen=()=>ws.send('connected');return ws}
export function runtimeInfo():RuntimeInfo{return {apiBase:getApiBase(),wsBase:getWsBase(),config:getRuntimeConfig()}}
