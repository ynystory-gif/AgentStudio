import React, { useState } from 'react'

type Props={
  scope:string
  setScope:(value:string)=>void
  busy:boolean
  rootReady:boolean
  fileReady:boolean
  attachmentReady:boolean
  onFocus:()=>void
  onSubmit:(prompt:string)=>void|Promise<void>
}

export const CodeLlmPromptComposer=React.memo(function CodeLlmPromptComposer({
  scope,setScope,busy,rootReady,fileReady,attachmentReady,onFocus,onSubmit
}:Props){
  const [prompt,setPrompt]=useState('')

  const disabled=
    busy
    || !rootReady
    || !attachmentReady
    || (scope==='FILE'&&!fileReady)

  const submit=()=>{
    const value=prompt.trim()
    if(!value||disabled) return
    setPrompt('')
    void onSubmit(value)
  }

  return <div className="code-llm-input">
    <select
      className="code-edit-scope-select"
      value={scope}
      onChange={(event)=>setScope(event.target.value)}
      disabled={busy}
      title="코드 작업 범위"
    >
      <option value="FILE">파일 단위</option>
      <option value="PROJECT">프로젝트 단위</option>
    </select>

    <textarea
      value={prompt}
      onFocus={onFocus}
      onPointerDown={onFocus}
      onChange={(event)=>setPrompt(event.target.value)}
      placeholder={
        scope==='PROJECT'
          ? '예: 유튜브 등록 에이전트를 만들어줘. 필요한 신규 파일도 생성해줘.'
          : fileReady
            ? '예: print hello 를 찍어줘.'
            : '파일 단위 작업은 먼저 수정할 파일을 선택하세요.'
      }
      disabled={disabled}
      onKeyDown={(event)=>{
        if(event.key!=='Enter') return
        if(event.nativeEvent?.isComposing) return
        if(event.shiftKey||event.altKey) return
        event.preventDefault()
        event.stopPropagation()
        submit()
      }}
      title="Enter: 실행 · Shift+Enter / Alt+Enter: 줄바꿈"
    />

    <button
      type="button"
      onClick={submit}
      disabled={disabled||!prompt.trim()}
    >
      {scope==='PROJECT'?'프로젝트 코딩':'파일 수정'}
    </button>
  </div>
})
