import { memo, useEffect, useState } from 'react'

export const DebouncedProjectSearchInput=memo(function DebouncedProjectSearchInput({value,onCommit,placeholder='프로젝트 검색...'}:LegacyRecord){
  const [localValue,setLocalValue]=useState(value||'')
  useEffect(()=>{ setLocalValue(value||'') },[value])
  useEffect(()=>{
    const timer=window.setTimeout(()=>{
      if((value||'')!==localValue) onCommit(localValue)
    },180)
    return()=>window.clearTimeout(timer)
  },[localValue,value,onCommit])
  return <input
    className="project-search"
    value={localValue}
    onChange={(event: LegacyValue)=>setLocalValue(event.target.value)}
    placeholder={placeholder}
    autoComplete="off"
    spellCheck={false}
  />
})
