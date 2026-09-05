import { useEffect, useRef, useState } from 'react'
import type { TerminalSession } from '../../../types/terminal'
import { serializeTerminalClientMessage } from '../../../utils/terminal'
import type { TerminalClientMessage } from '../../../types/terminal'

type LegacyRecord=Record<string,any>
type LegacyValue=any

const defaultSession=():TerminalSession=>({
  id:'terminal-1',
  name:'PowerShell',
  command:'',
  output:'',
  processState:'idle',
  exitCode:null,
})

export function useTerminalController(){
  const [terminalSessions,setTerminalSessions]=useState<TerminalSession[]>([defaultSession()])
  const [activeTerminalId,setActiveTerminalId]=useState('terminal-1')
  const [terminalNameEditId,setTerminalNameEditId]=useState<LegacyValue|null>(null)
  const [terminalNameDraft,setTerminalNameDraft]=useState('')
  const [projectTerminalSessions,setProjectTerminalSessions]=useState<LegacyRecord>({})
  const [activeTerminalProjectId,setActiveTerminalProjectId]=useState<LegacyValue|null>(null)
  const [terminalConnectionState,setTerminalConnectionState]=useState<LegacyRecord>({})
  const [terminalErrors,setTerminalErrors]=useState<LegacyRecord>({})
  const [terminalCompletion,setTerminalCompletion]=useState<LegacyValue|null>(null)

  // WebSocket ownership
  const terminalSocketsRef=useRef<LegacyRecord>({})
  const terminalIntentionalCloseRef=useRef<LegacyRecord>({})
  const terminalReconnectTimersRef=useRef<LegacyRecord>({})
  const terminalReconnectAttemptsRef=useRef<LegacyRecord>({})

  // DOM/xterm ownership
  const terminalOutputRefs=useRef<LegacyRecord>({})
  const terminalInlineInputRef=useRef<LegacyValue|null>(null)
  const xtermInstancesRef=useRef<LegacyRecord>({})
  const xtermContainersRef=useRef<LegacyRecord>({})
  const xtermFitAddonsRef=useRef<LegacyRecord>({})
  const xtermDisposablesRef=useRef<LegacyRecord>({})

  // xterm command-line ownership
  const xtermCommandBuffersRef=useRef<LegacyRecord>({})
  const xtermCommandHistoryRef=useRef<LegacyRecord>({})
  const xtermHistoryIndexRef=useRef<LegacyRecord>({})
  const xtermCursorIndexRef=useRef<LegacyRecord>({})
  const xtermPromptRef=useRef<LegacyRecord>({})
  const xtermOutputParseBufferRef=useRef<LegacyRecord>({})
  const xtermRequiredColsRef=useRef<LegacyRecord>({})
  const xtermSetCommandLineRef=useRef<LegacyRecord>({})
  const xtermKeyboardSelectionRef=useRef<LegacyRecord>({})
  const terminalCommandBusyRef=useRef<LegacyRecord>({})
  const terminalCwdRef=useRef<LegacyRecord>({})
  const terminalRootRef=useRef<LegacyRecord>({})
  const terminalCompletionRef=useRef<LegacyValue|null>(null)
  const terminalCompletionTimerRef=useRef<LegacyRecord>({})

  const setTerminalCompletionState=(next:LegacyValue)=>{
    terminalCompletionRef.current=next
    setTerminalCompletion(next)
  }

  const fitTerminalViewport=(id:LegacyValue)=>{
    const term=xtermInstancesRef.current[id]
    const container=xtermContainersRef.current[id]
    const fit=xtermFitAddonsRef.current[id]
    if(!term||!container)return
    const rect=container.getBoundingClientRect?.()
    if(!rect||rect.width<120||rect.height<80)return
    let proposed:LegacyValue|null=null
    try{proposed=fit?.proposeDimensions?.()||null}catch{}
    const cols=Math.max(20,proposed?.cols||term.cols||80)
    const rows=Math.max(2,(proposed?.rows||term.rows||24)-1)
    try{
      container.style.removeProperty('--terminal-min-width')
      container.style.removeProperty('--terminal-required-cols')
    }catch{}
    try{
      if(term.cols!==cols||term.rows!==rows)term.resize(cols,rows)
    }catch{}
  }

  const writeCommandBuffer=(id:LegacyValue,value:LegacyValue,cursor?:LegacyValue)=>{
    const text=String(value??'')
    xtermCommandBuffersRef.current[id]=text
    xtermCursorIndexRef.current[id]=Math.max(0,Math.min(Number(cursor??text.length),text.length))
  }

  const clearCommandBuffer=(id:LegacyValue)=>{
    xtermCommandBuffersRef.current[id]=''
    xtermCursorIndexRef.current[id]=0
  }

  const sendSocketMessage=(id:LegacyValue,payload:TerminalClientMessage)=>{
    const ws=terminalSocketsRef.current[id]
    if(!ws||ws.readyState!==WebSocket.OPEN)return false
    ws.send(serializeTerminalClientMessage(payload))
    return true
  }

  const attachSocket=(id:LegacyValue,ws:WebSocket)=>{
    const previous=terminalSocketsRef.current[id]
    if(previous&&previous!==ws){
      terminalIntentionalCloseRef.current[id]=true
      try{previous.close(1000,'terminal_replaced')}catch{}
    }
    terminalSocketsRef.current[id]=ws
    return ws
  }

  const closeTerminalSocket=(id:LegacyValue,reason='terminal_closed')=>{
    clearTimeout(terminalReconnectTimersRef.current[id])
    delete terminalReconnectTimersRef.current[id]
    const ws=terminalSocketsRef.current[id]
    if(ws){
      terminalIntentionalCloseRef.current[id]=true
      try{ws.close(1000,reason)}catch{}
    }
    delete terminalSocketsRef.current[id]
    setTerminalConnectionState((prev:LegacyRecord)=>({...prev,[id]:'closed'}))
  }

  const scheduleReconnect=(id:LegacyValue,connect:()=>void,maxAttempts=3)=>{
    clearTimeout(terminalReconnectTimersRef.current[id])
    const attempt=Number(terminalReconnectAttemptsRef.current[id]||0)+1
    terminalReconnectAttemptsRef.current[id]=attempt
    if(attempt>maxAttempts)return false
    const delay=Math.min(2500,350*Math.pow(2,attempt-1))
    terminalReconnectTimersRef.current[id]=setTimeout(connect,delay)
    setTerminalConnectionState((prev:LegacyRecord)=>({...prev,[id]:'reconnecting'}))
    return true
  }

  const resetReconnect=(id:LegacyValue)=>{
    clearTimeout(terminalReconnectTimersRef.current[id])
    delete terminalReconnectTimersRef.current[id]
    terminalReconnectAttemptsRef.current[id]=0
  }

  useEffect(()=>()=>{
    for(const timer of Object.values(terminalReconnectTimersRef.current||{})){
      try{clearTimeout(Number(timer))}catch{}
    }
    terminalReconnectTimersRef.current={}
    for(const [id,socket] of Object.entries(terminalSocketsRef.current||{})){
      terminalIntentionalCloseRef.current[id]=true
      try{(socket as WebSocket)?.close?.(1000,'app_unmount')}catch{}
    }
    terminalSocketsRef.current={}
    for(const disposable of Object.values(xtermDisposablesRef.current||{})){
      try{(disposable as any)?.dispose?.()}catch{}
    }
    xtermDisposablesRef.current={}
    for(const term of Object.values(xtermInstancesRef.current||{})){
      try{(term as any)?.dispose?.()}catch{}
    }
    xtermInstancesRef.current={}
  },[])

  return {
    terminalSessions,setTerminalSessions,
    activeTerminalId,setActiveTerminalId,
    terminalNameEditId,setTerminalNameEditId,
    terminalNameDraft,setTerminalNameDraft,
    projectTerminalSessions,setProjectTerminalSessions,
    activeTerminalProjectId,setActiveTerminalProjectId,
    terminalConnectionState,setTerminalConnectionState,
    terminalErrors,setTerminalErrors,
    terminalCompletion,setTerminalCompletion,
    terminalSocketsRef,terminalIntentionalCloseRef,
    terminalOutputRefs,terminalInlineInputRef,
    xtermInstancesRef,xtermContainersRef,xtermFitAddonsRef,xtermDisposablesRef,
    xtermCommandBuffersRef,xtermCommandHistoryRef,xtermHistoryIndexRef,
    xtermCursorIndexRef,xtermPromptRef,xtermOutputParseBufferRef,
    xtermRequiredColsRef,xtermSetCommandLineRef,xtermKeyboardSelectionRef,
    terminalCommandBusyRef,terminalCwdRef,terminalRootRef,
    terminalCompletionRef,terminalCompletionTimerRef,
    setTerminalCompletionState,fitTerminalViewport,
    writeCommandBuffer,clearCommandBuffer,
    sendSocketMessage,attachSocket,closeTerminalSocket,
    scheduleReconnect,resetReconnect,
  }
}
