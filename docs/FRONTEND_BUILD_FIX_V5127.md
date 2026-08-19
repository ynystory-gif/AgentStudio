# v5.127 Frontend Build Fix

## 발생 오류

Vite/esbuild가 `App.jsx`에서 다음 JSX 태그 불일치를 보고했습니다.

- closing `section` does not match opening `div`
- closing `div` does not match opening `main`
- closing `main` does not match opening `div`

## 원인

v5.125의 실행 결과 / 분석 리포트 Dashboard 삽입 과정에서
`workspace-top-pane`의 REPORT 블록 뒤에 있던 원래 구조 중
`workspace-bottom-grid`와 `editor-pane` 시작 부분이 누락되었습니다.

결과적으로 `editor-pane`의 닫는 `</section>`과
`terminal-pane`만 남아 JSX 트리가 깨졌습니다.

## 복구

마지막 정상 구조인 v5.124에서 기존 LLM 대화형 코드 편집 섹션을 그대로 복원했습니다.

정상 구조:

```text
workspace-main
├─ workspace-tabs
├─ workspace-top-pane
│  ├─ DESIGN
│  ├─ WORKFLOW
│  ├─ CODE
│  ├─ RUN Dashboard
│  └─ REPORT Dashboard
└─ workspace-bottom-grid
   ├─ editor-pane (LLM 대화형 코드 편집)
   └─ terminal-pane
```

v5.126 Settings Generator와 v5.125 Dashboard 기능은 유지합니다.
