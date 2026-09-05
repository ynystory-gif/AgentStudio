import { useEffect, useRef, useState } from 'react'
import { readWorkspaceBoolean, readWorkspaceNumber, writeWorkspacePreference } from '../../../stores'
import type { WorkspacePanelSide, WorkspaceTab } from '../workspace.types'

export function useWorkspaceLayout(initialTab:WorkspaceTab='DESIGN'){
  const [workspaceTab,setWorkspaceTab]=useState<WorkspaceTab>(initialTab)
  const [workspaceLeftCollapsed,setWorkspaceLeftCollapsed]=useState(()=>readWorkspaceBoolean('leftCollapsed'))
  const [workspaceRightCollapsed,setWorkspaceRightCollapsed]=useState(()=>readWorkspaceBoolean('rightCollapsed'))
  const [workspaceBottomCollapsed,setWorkspaceBottomCollapsed]=useState(()=>readWorkspaceBoolean('bottomCollapsed'))
  const [workspaceBottomHeight,setWorkspaceBottomHeight]=useState(()=>readWorkspaceNumber('bottomHeight',305,305))
  const [workspaceResizeSide,setWorkspaceResizeSide]=useState<WorkspacePanelSide|null>(null)
  const [workspaceBottomResizing,setWorkspaceBottomResizing]=useState(false)
  const [workspaceLeftWidth,setWorkspaceLeftWidth]=useState(()=>readWorkspaceNumber('leftWidth',270,230))
  const [workspaceRightWidth,setWorkspaceRightWidth]=useState(()=>readWorkspaceNumber('rightWidth',300,260))
  const workspaceLayoutRef=useRef<HTMLDivElement|null>(null)
  const workspaceResizeCleanupRef=useRef<(()=>void)|null>(null)
  const workspaceBottomResizeCleanupRef=useRef<(()=>void)|null>(null)

  useEffect(()=>{writeWorkspacePreference('leftCollapsed',workspaceLeftCollapsed)},[workspaceLeftCollapsed])
  useEffect(()=>{writeWorkspacePreference('rightCollapsed',workspaceRightCollapsed)},[workspaceRightCollapsed])
  useEffect(()=>{writeWorkspacePreference('bottomCollapsed',workspaceBottomCollapsed)},[workspaceBottomCollapsed])
  useEffect(()=>{writeWorkspacePreference('bottomHeight',Math.round(workspaceBottomHeight))},[workspaceBottomHeight])
  useEffect(()=>{writeWorkspacePreference('leftWidth',Math.round(workspaceLeftWidth))},[workspaceLeftWidth])
  useEffect(()=>{writeWorkspacePreference('rightWidth',Math.round(workspaceRightWidth))},[workspaceRightWidth])
  useEffect(()=>{
    const timer=setTimeout(()=>{try{window.dispatchEvent(new Event('resize'))}catch{}},40)
    return ()=>clearTimeout(timer)
  },[workspaceBottomHeight,workspaceBottomCollapsed])
  useEffect(()=>()=>{try{workspaceResizeCleanupRef.current?.()}catch{};try{workspaceBottomResizeCleanupRef.current?.()}catch{}},[])

  const beginWorkspaceBottomResize=(event:React.PointerEvent)=>{
    if(workspaceBottomCollapsed)return
    event.preventDefault();event.stopPropagation()
    const main=(event.currentTarget as HTMLElement)?.closest?.('.workspace-main') as HTMLElement|null
    if(!main)return
    const rect=main.getBoundingClientRect()
    const startY=event.clientY
    const startHeight=workspaceBottomHeight
    const minimum=305
    const maxHeight=Math.max(minimum,rect.height-42-6-180)
    const previousCursor=document.body.style.cursor
    const previousSelect=document.body.style.userSelect
    document.body.style.cursor='row-resize';document.body.style.userSelect='none'
    setWorkspaceBottomResizing(true)
    const onMove=(moveEvent:PointerEvent)=>{
      const delta=startY-moveEvent.clientY
      setWorkspaceBottomHeight(Math.max(minimum,Math.min(maxHeight,startHeight+delta)))
    }
    const cleanup=()=>{
      window.removeEventListener('pointermove',onMove);window.removeEventListener('pointerup',cleanup);window.removeEventListener('pointercancel',cleanup)
      document.body.style.cursor=previousCursor;document.body.style.userSelect=previousSelect
      setWorkspaceBottomResizing(false);workspaceBottomResizeCleanupRef.current=null
    }
    workspaceBottomResizeCleanupRef.current=cleanup
    window.addEventListener('pointermove',onMove);window.addEventListener('pointerup',cleanup);window.addEventListener('pointercancel',cleanup)
  }

  const beginWorkspacePanelResize=(side:WorkspacePanelSide,event:React.PointerEvent)=>{
    if((side==='left'&&workspaceLeftCollapsed)||(side==='right'&&workspaceRightCollapsed))return
    event.preventDefault();event.stopPropagation()
    const host=workspaceLayoutRef.current
    if(!host)return
    const rect=host.getBoundingClientRect()
    const startX=event.clientX
    const startWidth=side==='left'?workspaceLeftWidth:workspaceRightWidth
    const otherWidth=side==='left'?(workspaceRightCollapsed?0:workspaceRightWidth):(workspaceLeftCollapsed?0:workspaceLeftWidth)
    const compact=typeof window!=='undefined'&&window.innerWidth<=1150
    const minWidth=side==='left'?(compact?230:270):(compact?260:300)
    const maxWidth=Math.max(minWidth,rect.width-otherWidth-420)
    const previousCursor=document.body.style.cursor
    const previousSelect=document.body.style.userSelect
    document.body.style.cursor='col-resize';document.body.style.userSelect='none'
    setWorkspaceResizeSide(side)
    const onMove=(moveEvent:PointerEvent)=>{
      const delta=side==='left'?moveEvent.clientX-startX:startX-moveEvent.clientX
      const next=Math.max(minWidth,Math.min(maxWidth,startWidth+delta))
      if(side==='left')setWorkspaceLeftWidth(next);else setWorkspaceRightWidth(next)
    }
    const cleanup=()=>{
      window.removeEventListener('pointermove',onMove);window.removeEventListener('pointerup',cleanup);window.removeEventListener('pointercancel',cleanup)
      document.body.style.cursor=previousCursor;document.body.style.userSelect=previousSelect
      setWorkspaceResizeSide(null);workspaceResizeCleanupRef.current=null
    }
    workspaceResizeCleanupRef.current=cleanup
    window.addEventListener('pointermove',onMove);window.addEventListener('pointerup',cleanup);window.addEventListener('pointercancel',cleanup)
  }

  return {
    workspaceTab,setWorkspaceTab,
    workspaceLeftCollapsed,setWorkspaceLeftCollapsed,
    workspaceRightCollapsed,setWorkspaceRightCollapsed,
    workspaceBottomCollapsed,setWorkspaceBottomCollapsed,
    workspaceBottomHeight,setWorkspaceBottomHeight,
    workspaceResizeSide,workspaceBottomResizing,
    workspaceLeftWidth,setWorkspaceLeftWidth,
    workspaceRightWidth,setWorkspaceRightWidth,
    workspaceLayoutRef,beginWorkspaceBottomResize,beginWorkspacePanelResize,
  }
}
