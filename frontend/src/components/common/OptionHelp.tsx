import React, { useState } from 'react'
import './option-help.css'

interface OptionHelpProps{
  title:string
  summary:string
  detail?:string
  recommendedFor?:string[]
  example?:string
  aiReason?:string
}

export function OptionHelp({title,summary,detail,recommendedFor=[],example,aiReason}:OptionHelpProps){
  const [open,setOpen]=useState(false)
  return <span className={`option-help ${open?'open':''}`}>
    <button
      type="button"
      className="option-help-trigger"
      aria-label={`${title} 도움말`}
      aria-expanded={open}
      onClick={()=>setOpen((value)=>!value)}
      onBlur={(event)=>{if(!event.currentTarget.parentElement?.contains(event.relatedTarget as Node|null))setOpen(false)}}
    >ⓘ</button>
    <span className="option-help-tooltip" role="tooltip"><strong>{title}</strong><span>{summary}</span></span>
    {open&&<span className="option-help-popover" role="dialog" aria-label={`${title} 설명`} tabIndex={-1}>
      <strong>{title}</strong>
      <span>{summary}</span>
      {detail&&<p>{detail}</p>}
      {recommendedFor.length>0&&<p><b>추천:</b> {recommendedFor.join(', ')}</p>}
      {example&&<p><b>예:</b> {example}</p>}
      {aiReason&&<p className="option-help-ai-reason"><b>✨ AI 추천 이유</b>{aiReason}</p>}
      <button type="button" onClick={()=>setOpen(false)}>닫기</button>
    </span>}
  </span>
}
