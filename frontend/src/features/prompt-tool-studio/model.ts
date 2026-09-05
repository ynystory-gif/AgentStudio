export type StudioChatMessage={role:string;content:string;turn_type?:string}
export type StateStatus='CONFIRMED'|'CANDIDATE'|'MISSING'|'RECOMMENDED'|'CHANGED'|'CONFLICT'
export type SourceType='USER'|'INFERRED'|'DEFAULT'|'RECOMMENDED'|'SYSTEM'
export type StateHistory={value:string;status:StateStatus;source:SourceType;sourceMessageId:string;changedAt:string;operation:'SET'|'REPLACE'|'RECOMMEND'}
export type StateItem={key:string;label:string;value:string;status:StateStatus;source:SourceType;confidence:number;sourceMessageId:string;sourceText:string;history:StateHistory[]}
export type SemanticUnit={id:string;text:string;types:string[];intents:string[]}
export type PendingQuestion={id:string;question:string;expectedSchema:Record<string,string>}
export type ValidationResult={valid:boolean;missing:string[];conflicts:string[];warnings:string[];confidence:number}
export type LocalAnalysis={types:string[];intents:string[];units:SemanticUnit[];extraction:StateItem[];contextRelations:string[];validation:ValidationResult}
export type StudioTool={id:string;name:string;type:'Python'|'API'|'MCP'|'Database'|'Agent';description:string;inputSchema:string;outputSchema:string;permissions:string[];timeout:number;retry:number;source:string;usage:string[];version:number;registryId?:number;serverId?:number;runtimeStatus?:string;riskLevel?:number;requiresConfirmation?:boolean;syncStatus?:'NEW'|'CHANGED'|'SYNCED'|'MANUAL';sourceOriginPath?:string;sourceLine?:number;sourceFingerprint?:string;discoveryKind?:string}
export type RouteRule={id:string;intent:string;condition:string;targetType:'TOOL'|'WORKFLOW'|'LLM'|'NEXT_QUESTION';target:string;enabled:boolean}

export const statusLabel:Record<StateStatus,string>={CONFIRMED:'● 확정',CANDIDATE:'◐ 후보',MISSING:'○ 미정',RECOMMENDED:'★ 추천',CHANGED:'↺ 변경',CONFLICT:'⚠ 충돌'}
const now=()=>new Date().toISOString()
const msgId=(i:number)=>`msg_${i+1}`

export function classify(text:string,pending?:PendingQuestion|null){
 const t=text.trim(),out:string[]=[]
 if(!t)return ['UNKNOWN']
 if(/^(안녕|hello|hi\b)/i.test(t))out.push('GREETING')
 if(/[?？]|무엇|왜|어떻게|필요한가|가능한가|알려|추천|어느/.test(t))out.push('QUESTION')
 if(/해줘|해주세요|추가|만들|설정|사용|넣어|적용|구성|생성/.test(t))out.push('REQUEST')
 if(/^(실행|시작|중지|삭제|저장|열어|닫아)|반드시|즉시/.test(t))out.push('COMMAND')
 if(/아니|바꿔|수정|대신|변경|취소하고/.test(t))out.push('CORRECTION')
 if(/^(네|예|응|좋아|맞아|확인|동의|그렇게)/.test(t))out.push('CONFIRMATION')
 if(/^(아니요|아니|싫어|안 돼|하지 마)/.test(t))out.push('REJECTION')
 if(/중에서|선택|로 할게|로 하자/.test(t))out.push('SELECTION')
 if(/좋다|별로|느리|빠르|문제|개선/.test(t)&&!/해줘|해주세요/.test(t))out.push('FEEDBACK')
 if(pending&&t.length<120&&!out.includes('QUESTION'))out.unshift('ANSWER')
 if(!out.length)out.push('STATEMENT')
 return [...new Set(out)]
}

export function detectIntents(text:string){
 const a:string[]=[]
 if(/왜|필요한가/.test(text))a.push('ASK_REASON')
 if(/추천|어떤 게|어느|좋을까/.test(text))a.push('ASK_RECOMMENDATION')
 if(/비교|차이|중 어떤/.test(text))a.push('ASK_COMPARISON')
 if(/상태|진행|완료|됐어/.test(text)&&/[?？]|어떻게|알려/.test(text))a.push('ASK_STATUS')
 if(/어떻게|방법/.test(text)&&/[?？]|알려/.test(text))a.push('ASK_HOW_TO')
 if(/가능|할 수/.test(text)&&/[?？]/.test(text))a.push('ASK_CAPABILITY')
 if(/[?？]|무엇|알려/.test(text))a.push('ASK_INFORMATION')
 if(/추가|넣어|사용|설정|구성/.test(text))a.push('CONFIGURATION')
 if(/바꿔|수정|변경|대신/.test(text))a.push('CHANGE_CONFIGURATION')
 if(/삭제|제거/.test(text))a.push('REMOVE_RESOURCE')
 return [...new Set(a.length?a:['PROVIDE_INFORMATION'])]
}

export function splitSemanticUnits(text:string,pending?:PendingQuestion|null):SemanticUnit[]{
 const normalized=text.replace(/\r/g,'').trim()
 if(!normalized)return []
 const chunks=normalized.split(/(?<=[.!?。！？])\s+|\n+|(?<=요)\s+(?=[가-힣A-Z])/).map(x=>x.trim()).filter(Boolean)
 return chunks.map((unit,i)=>({id:`unit_${i+1}`,text:unit,types:classify(unit,pending),intents:detectIntents(unit)}))
}

const stateItem=(key:string,label:string,value:string,status:StateStatus,source:SourceType,messageId:string,sourceText:string,confidence=.96):StateItem=>({key,label,value,status,source,confidence,sourceMessageId:messageId,sourceText,history:[]})

export function extractFromText(text:string,messageId='msg_latest',previous?:Map<string,StateItem>):StateItem[]{
 const r:StateItem[]=[]
 const changing=/아니|바꿔|수정|대신|변경|로 해줘|로 하고/.test(text)
 const add=(key:string,label:string,value:string,confidence=.96)=>{
  if(r.some(x=>x.key===key))return
  const old=previous?.get(key)
  const status:StateStatus=old&&old.value!==value&&changing?'CHANGED':'CONFIRMED'
  r.push(stateItem(key,label,value,status,'USER',messageId,text,confidence))
 }
 if(/PostgreSQL/i.test(text))add('database.primary','Database / Primary','PostgreSQL')
 if(/Firestore/i.test(text))add('database.primary','Database / Primary','Firestore')
 if(/Redis/i.test(text))add('database.cache','Database / Cache','Redis')
 if(/React/i.test(text))add('frontend.framework','Frontend / Framework','React')
 if(/TypeScript|\bTS\b/i.test(text))add('frontend.language','Frontend / Language','TypeScript')
 if(/FastAPI/i.test(text))add('backend.framework','Backend / Framework','FastAPI')
 if(/Django/i.test(text))add('backend.framework','Backend / Framework','Django')
 if(/LangGraph/i.test(text))add('workflow.engine','Workflow / Engine','LangGraph')
 if(/LangChain/i.test(text))add('agent.framework','Agent / Framework','LangChain')
 if(/\bRAG\b/i.test(text))add('rag.enabled','RAG / 사용 여부',/안\s*쓰|사용\s*안|제외/.test(text)?'미사용':'사용')
 if(/OpenAI/i.test(text))add('llm.provider','LLM / Provider','OpenAI')
 if(/Ollama/i.test(text))add('llm.provider','LLM / Provider','Ollama')
 if(/Codex/i.test(text))add('llm.coding_provider','LLM / Coding Provider','Codex')
 if(/pgvector/i.test(text))add('database.vector','Database / Vector','pgvector')
 const ports=[...text.matchAll(/(?:프론트(?:엔드)?|frontend)\s*(?:포트|port)?\s*(?:는|:|=)?\s*(\d{4,5})/ig)];const frontPort=ports.at(0)?.[1];if(frontPort)add('frontend.port','Frontend / Port',frontPort)
 const bp=[...text.matchAll(/(?:백(?:엔드)?|backend)\s*(?:포트|port)?\s*(?:는|:|=)?\s*(\d{4,5})/ig)];const backPort=bp.at(0)?.[1];if(backPort)add('backend.port','Backend / Port',backPort)
 const generic=text.match(/(?:포트|port)\s*(?:는|:|=)?\s*(\d{4,5})/i);const genericPort=generic?.[1];if(genericPort&&!frontPort&&!backPort)add('runtime.port','Runtime / Port',genericPort)
 return r
}

export function inferPendingQuestion(question:string):PendingQuestion|null{
 const q=String(question||'').trim();if(!q)return null
 const checks:[RegExp,string,Record<string,string>][]=[
  [/database|데이터베이스|DB/i,'database_type',{database:'string'}],[/backend|백엔드/i,'backend_framework',{backend_framework:'string'}],[/LLM|모델|provider/i,'llm_provider',{llm_provider:'string'}],[/RAG/i,'rag_enabled',{rag_enabled:'boolean|string'}],[/port|포트/i,'runtime_port',{port:'integer'}],[/목적|무엇을 만들|어떤.*Agent/i,'agent_goal',{goal:'string'}]
 ]
 const found=checks.find(x=>x[0].test(q));if(found)return {id:found[1],question:q,expectedSchema:found[2]};return {id:'pending_question',question:q,expectedSchema:{answer:'string'}}
}

export function buildState(chat:StudioChatMessage[]):StateItem[]{
 const map=new Map<string,StateItem>()
 chat.forEach((m,i)=>{
  if(m.role==='assistant')return
  const id=msgId(i),found=extractFromText(m.content,id,map)
  found.forEach(item=>{
   const old=map.get(item.key)
   if(old&&old.value!==item.value){
    item.history=[...old.history,{value:old.value,status:old.status,source:old.source,sourceMessageId:old.sourceMessageId,changedAt:now(),operation:'REPLACE'}]
    item.status='CHANGED'
   }else if(old)item.history=old.history
   map.set(item.key,item)
  })
 })
 const firstUser=chat.find(m=>m.role!=='assistant'&&m.content.trim())
 if(firstUser&&!map.has('agent.goal'))map.set('agent.goal',stateItem('agent.goal','Agent / 목적',firstUser.content.trim().slice(0,180),'CANDIDATE','INFERRED','msg_1',firstUser.content,.72))
 const required:[string,string][]=[['backend.framework','Backend / Framework'],['llm.provider','LLM / Provider'],['rag.enabled','RAG / 사용 여부'],['tool.required','Tool / 필요 여부'],['security.policy','Security / 정책']]
 required.forEach(([key,label])=>{if(!map.has(key))map.set(key,stateItem(key,label,'미정','MISSING','SYSTEM','system','',1))})
 return [...map.values()]
}

export function contextRelations(text:string,pending:PendingQuestion|null,state:StateItem[]){
 const out:string[]=[]
 if(pending&&text.trim()&&!/[?？]/.test(text))out.push(`ANSWERS_PENDING_QUESTION:${pending.id}`)
 if(/아니|바꿔|수정|대신|변경/.test(text))out.push('REPLACES_EXISTING_VALUE')
 if(/추가|또|그리고|도 넣/.test(text))out.push('ADDS_REQUIREMENT')
 if(/^(네|예|응|좋아|맞아|그렇게)/.test(text.trim()))out.push('CONFIRMATION_RESPONSE')
 const ext=extractFromText(text,'latest',new Map(state.map(x=>[x.key,x])))
 if(ext.some(x=>state.some(s=>s.key===x.key&&s.value!==x.value)))out.push('STATE_CONFLICT_OR_CHANGE')
 return out.length?out:['CONTINUES_CURRENT_TOPIC']
}

export function validate(extraction:StateItem[],state:StateItem[]):ValidationResult{
 const warnings:string[]=[],conflicts:string[]=[]
 extraction.forEach(x=>{
  if(x.key.endsWith('.port')){const n=Number(x.value);if(!Number.isInteger(n)||n<1||n>65535)warnings.push(`${x.label}: 포트 범위가 올바르지 않습니다.`)}
  const old=state.find(s=>s.key===x.key&&s.status==='CONFIRMED');if(old&&old.value!==x.value&&x.status!=='CHANGED')conflicts.push(`${x.label}: ${old.value} ↔ ${x.value}`)
 })
 const confidence=extraction.length?extraction.reduce((a,b)=>a+b.confidence,0)/extraction.length:.8
 return {valid:!conflicts.length&&!warnings.length,missing:state.filter(x=>x.status==='MISSING').map(x=>x.key),conflicts,warnings,confidence}
}

export function analyzeLocal(text:string,pending:PendingQuestion|null,state:StateItem[]):LocalAnalysis{
 const map=new Map(state.map(x=>[x.key,x]));const extraction=extractFromText(text,'latest',map)
 return {types:classify(text,pending),intents:detectIntents(text),units:splitSemanticUnits(text,pending),extraction,contextRelations:contextRelations(text,pending,state),validation:validate(extraction,state)}
}

export function detectAgentMediaType(chat:StudioChatMessage[]){const t=chat.map(x=>x.content).join(' ');if(/비디오|영상|쇼츠|릴스|video/i.test(t))return 'VIDEO';if(/이미지|포스터|image/i.test(t))return 'IMAGE';return 'GENERAL'}
