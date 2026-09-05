import type { ChangeEvent } from 'react'

export interface CodeDocumentationToggleProps {
  enabled?: boolean
  busy?: boolean
  stage?: string
  onChange?: (enabled:boolean)=>void
}

export function CodeDocumentationToggle({ enabled=false, busy=false, stage='', onChange }:CodeDocumentationToggleProps){
  return <label
    className={`agent-build-title-doc-option ${enabled?'enabled':''}`}
    title="체크하면 생성·수정되는 소스의 클래스/함수/메소드와 주요 변수·필드·상수에 언어별 표준 설명 주석을 추가합니다. 단순 지역 변수에는 불필요한 주석을 만들지 않습니다."
  >
    <input
      type="checkbox"
      checked={Boolean(enabled)}
      disabled={busy||stage==='BUILDING'}
      onChange={(event:ChangeEvent<HTMLInputElement>)=>onChange?.(event.target.checked)}
    />
    <span>변수·메소드 설명 추가</span>
  </label>
}
