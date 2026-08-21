# v5.300 Frontend TypeScript Viewer + Helper Migration

## 목적

v5.293에서 마련한 TypeScript 기반 위에서 `App.jsx` 전체를 한 번에 변경하지 않고 의존성이 낮은 Viewer/Notebook renderer/pure helper부터 실제 `.ts/.tsx`로 이동합니다.

## 이동된 코드

- `src/components/notebook/NotebookRenderers.tsx`
  - NotebookMarkdown
  - NotebookOutput
  - notebookSourceToText
- `src/components/viewers/DocumentViewers.tsx`
  - PdfViewer
  - PresentationViewer
- `src/utils/editor.ts`
  - getEditorLanguage
  - getEditorModelPath
  - Notebook/PDF/PPT 파일 판별 helper
- `src/utils/notebook.ts`
  - raw SQL/%%sql 판별 및 정규화
  - SQL 실행 결과 Notebook 출력 포맷
  - Notebook source 직렬화
  - Notebook JSON parse
  - kernel language 판별
- `src/types/notebook.ts`
  - NotebookDocument
  - NotebookCell
  - NotebookOutputData
  - NotebookAttachments
  - NotebookParseResult

## 회귀 방지 원칙

- CSS className과 DOM 구조는 기존 Viewer/renderer와 동일하게 유지합니다.
- PDF endpoint 및 PPT prepare/pdf endpoint는 변경하지 않습니다.
- Notebook SQL magic 라우팅 정규식은 기존 v5.299 규칙을 유지합니다.
- `App.jsx`의 IDE global state와 NotebookEditor는 이번 버전에서 구조 변경하지 않습니다.
- v5.299의 Supabase custom schema/profile rename을 포함한 DB 기능을 유지합니다.

## 검증

- 신규 `.ts/.tsx` 모듈 strict TypeScript isolated check
- `App.jsx` JSX parser check
- Backend Python compileall
- Frontend import target 존재/중복 local definition 제거 확인
- Version gate 5.300 동기화

이 실행 환경에서는 npm registry 접근이 제한되어 `npm install`이 timeout될 수 있으므로, 최종 Windows 실행 환경에서는 SYSTEM_ADMIN의 `npm run build`를 통해 실제 dependency 기반 production build를 다시 통과해야 합니다.

## 다음 단계

Phase 3에서 NotebookEditor를 `NotebookEditor.tsx`로 이동하고 Monaco editor instance/selection, Python execution result, controller ref, stop/run-all 상태를 구체적인 TypeScript interface로 고정합니다.
