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
function getApiBase():string{const envBase=import.meta.env.VITE_API_BASE_URL;if(envBase)return envBase.replace(/\/$/,'');const cfg=getRuntimeConfig();const host=cfg.BACKEND_HOST||window.location.hostname||'127.0.0.1';const port=cfg.BACKEND_PORT||8000;return `${window.location.protocol}//${host}:${port}/api`}
function getWsBase():string{const cfg=getRuntimeConfig();const host=cfg.BACKEND_HOST||window.location.hostname||'127.0.0.1';const port=cfg.BACKEND_PORT||8000;return `ws://${host}:${port}/api/ws`}
export async function apiFetch(path:string,options:RequestInit={}):Promise<Response>{
  const apiBase=getApiBase(),url=`${apiBase}${path}`,token=getAuthToken();let res:Response
<<<<<<< HEAD
  const incomingHeaders=(options.headers||{}) as Record<string,string>
  const headers:Record<string,string>={...(token?{Authorization:`Bearer ${token}`}:{ }),...incomingHeaders}
  if(options.body!==undefined&&options.body!==null&&!Object.keys(headers).some(key=>key.toLowerCase()==='content-type'))headers['Content-Type']='application/json'
  try{
    res=await fetch(url,{...options,headers})
=======
  try{
    res=await fetch(url,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{ }),...((options.headers||{}) as Record<string,string>)}})
>>>>>>> d0e40bd86a999808d857b8acca8a9a6f14259c81
  }catch(cause){
    if(cause instanceof DOMException&&cause.name==='AbortError')throw cause
    throw new AgentStudioApiError(`Backend 연결 실패: ${url}`,{kind:'network',apiBase,url,path,cause})
  }
  if(!res.ok){const body=await res.text();let detail=body||res.statusText;try{const parsed=JSON.parse(body) as {detail?:unknown;message?:unknown};if(typeof parsed.detail==='string'&&parsed.detail.trim())detail=parsed.detail;else if(typeof parsed.message==='string'&&parsed.message.trim())detail=parsed.message}catch{}
    if(res.status===404&&path.startsWith('/ui-themes'))detail='Theme API를 찾을 수 없습니다. Frontend와 Backend 버전이 다른 경우가 많습니다. SYSTEM_ADMIN에서 AgentStudio를 완전히 재시작한 뒤 다시 시도하세요.'
    if(res.status===401&&!path.startsWith('/auth/'))clearAuthToken()
    throw new AgentStudioApiError(`Backend HTTP ${res.status}: ${detail}`,{kind:'http',status:res.status,apiBase,url,path,responseBody:body})
  }
<<<<<<< HEAD
  return res
}
export async function api<T=unknown>(path:string,options:RequestInit={}):Promise<T>{
  const res=await apiFetch(path,options)
=======
>>>>>>> d0e40bd86a999808d857b8acca8a9a6f14259c81
  return res.json() as Promise<T>
}
export function connectJobs(onEvent:(event:JobEvent)=>void):WebSocket{const token=getAuthToken();const ws=new WebSocket(`${getWsBase()}${token?`?access_token=${encodeURIComponent(token)}`:''}`);ws.onmessage=event=>onEvent(JSON.parse(event.data) as JobEvent);ws.onopen=()=>ws.send('connected');return ws}
export function runtimeInfo():RuntimeInfo{return {apiBase:getApiBase(),wsBase:getWsBase(),config:getRuntimeConfig()}}
