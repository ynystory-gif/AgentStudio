# v5.293 TypeScriptFrontendFoundation

## 목적

v5.292의 모든 UI/Notebook/Terminal/Database/Redis/Firestore/Supabase/PowerPoint/LLM/MCP 기능을 유지한 상태에서 React Frontend를 TypeScript로 안전하게 전환하기 위한 첫 기반 버전입니다.

## 이번 버전의 전환 범위

- Vite 설정을 `vite.config.js` → `vite.config.ts`로 전환
- TypeScript project references 기반 `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` 추가
- `src/api.js` → `src/api.ts` 전환
  - Runtime config 타입
  - Backend network/HTTP error 타입
  - generic API response 타입
  - WebSocket job event 타입
- 공통 타입 `src/types/common.ts` 추가
- `src/vite-env.d.ts`에서 runtime config / Vite env 전역 타입 정의
- `src/main.jsx` → `src/main.tsx` 전환
- `index.html` bootstrap entry를 `/src/main.tsx`로 변경
- `npm run build`가 `tsc -b && vite build`를 수행하도록 강화
- SYSTEM_ADMIN이 기존 `node_modules`를 재사용할 때도 TypeScript, Node/React type package 누락을 감지하도록 보강

## 의도적으로 유지한 범위

`App.jsx`는 약 17,000줄의 모놀리식 파일이며 Notebook, Terminal, Database Browser, Redis, Firestore, Supabase, PPT/PPTX Viewer, LLM, MCP 등 핵심 기능이 서로 연결되어 있습니다. v5.293에서는 단순 확장자 변경이나 대규모 동시 타입 수정을 하지 않습니다.

`tsconfig.app.json`은 전환 기간 동안 `allowJs: true`, `checkJs: false`를 사용합니다. 따라서 기존 `App.jsx`는 그대로 실행되고, 새로 전환되는 `.ts/.tsx` 파일부터 strict TypeScript 검증을 받습니다.

## 다음 안전 전환 단위

1. 독립 helper / viewer부터 별도 파일로 추출
2. Notebook/PDF/PPT viewer 계층 `.tsx` 전환
3. 공통 UI/Report/Architecture/LLM panel `.tsx` 전환
4. SystemPage 전환
5. IDE 상태/handler 타입 정의 및 전환
6. 마지막에 `App.jsx` → `App.tsx`
7. 최종적으로 `allowJs` 제거 및 `checkJs` 과도기 설정 제거

## 회귀 검증 기준

- `npm run build`
- SYSTEM_ADMIN 실행 및 Frontend/Backend version gate 일치
- Notebook cell 실행 / magic / focus / Backspace
- Terminal 입력 / multiline / paste / focus / clear
- Database Browser / SQL / Redis / Firestore / Supabase
- PDF / PPT / PPTX preview
- LLM / MCP / workflow / code edit
