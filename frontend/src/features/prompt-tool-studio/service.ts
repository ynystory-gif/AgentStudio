import {api} from '../../api'
import type {PendingQuestion,RouteRule,StateItem,StudioTool} from './model'
export type AiStudioAnalysis={types?:string[];intents?:string[];semantic_units?:Array<{text:string;types?:string[];intents?:string[]}>;extraction?:Array<Record<string,unknown>>;context_relations?:string[];validation?:Record<string,unknown>;response_plan?:string[];response_preview?:string}
export type RuntimeTraceStep={stage:string;status:'PASS'|'CHECK'|'FAIL';detail:string;elapsed_ms:number;input?:unknown;output?:unknown;retry_count?:number}
export type StudioRuntimeTestResult={ok:boolean;mode:string;matched_routes?:RouteRule[];tool_validation?:{valid:boolean;errors:string[];registered:string[];registry_matches?:Array<Record<string,unknown>>};trace?:string[];trace_steps?:RuntimeTraceStep[];response?:string;provider?:string;error?:string;prompt_chars?:number;total_elapsed_ms?:number;graph_summary?:Record<string,unknown>;tool_execution?:Record<string,unknown>|null;llm_usage?:{model?:string;tokens?:Record<string,unknown>;cost?:number|null;cost_note?:string}}
export type McpRegistryTool={id:number;server_id:number;name:string;category?:string;capability?:string;risk_level?:number;enabled?:boolean;requires_confirmation?:boolean}
export type McpServer={id:number;name:string;transport:string;status?:string;trust_level?:string;endpoint?:string}
export async function analyzeStudioInput(payload:{message:string;pendingQuestion:PendingQuestion|null;state:StateItem[];provider?:string}){
 return api<{ok:boolean;analysis?:AiStudioAnalysis;error?:string}>('/prompt-tool-studio/analyze',{method:'POST',body:JSON.stringify({message:payload.message,pending_question:payload.pendingQuestion,state:payload.state,provider:payload.provider||''})})
}
export async function runStudioRuntimeTest(payload:{message:string;mode:string;compiledPrompt:string;routes:RouteRule[];tools:StudioTool[];intents:string[];provider?:string;executeTool?:boolean;toolName?:string;toolArguments?:Record<string,unknown>;confirmation?:boolean;projectRoot?:string}){
 return api<StudioRuntimeTestResult>('/prompt-tool-studio/test',{method:'POST',body:JSON.stringify({message:payload.message,mode:payload.mode,compiled_prompt:payload.compiledPrompt,routes:payload.routes,tools:payload.tools,intents:payload.intents,provider:payload.provider||'',execute_tool:Boolean(payload.executeTool),tool_name:payload.toolName||'',tool_arguments:payload.toolArguments||{},confirmation:Boolean(payload.confirmation),project_root:payload.projectRoot||''})})
}

export async function fetchMcpRegistryTools(){return api<McpRegistryTool[]>('/mcp/tools')}
export async function fetchMcpServers(){return api<McpServer[]>('/mcp/servers')}
export async function syncMcpServer(serverId:number){return api<Record<string,unknown>>(`/mcp/servers/${serverId}/sync`,{method:'POST'})}
