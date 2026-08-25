# v5.345 Generated React TypeScript Modular Frontend

## 목적

생성 대상 Agent의 요구사항이 React + TypeScript이면 JavaScript/JSX로 후퇴하지 않고 TypeScript 계약을 유지하며, `App.tsx` 한 파일에 전체 UI를 몰아넣지 않도록 합니다.

## 언어 계약

- React + TypeScript 확정 시 `frontend/src`의 React 파일은 `.tsx`, 일반 모듈은 `.ts`를 사용합니다.
- `App.jsx`, `main.jsx`, `services/api.js`는 생성하지 않습니다.
- LLM File Plan이 잘못된 `.jsx/.js` 경로를 반환해도 AgentStudio가 Code Generation 전에 `.tsx/.ts`로 정규화합니다.

## 기본 Frontend 구조

```text
frontend/
├─ package.json
├─ index.html
├─ tsconfig.json
├─ vite.config.ts
└─ src/
   ├─ main.tsx
   ├─ App.tsx
   ├─ layouts/
   │  └─ AppLayout.tsx
   ├─ components/
   │  └─ layout/
   │     ├─ TopHeader.tsx
   │     ├─ Sidebar.tsx
   │     └─ Footer.tsx
   ├─ pages/
   │  └─ HomePage.tsx
   ├─ services/
   │  └─ api.ts
   ├─ types/
   │  └─ index.ts
   └─ styles/
      └─ global.css
```

업무 화면이 여러 개면 `pages` 또는 `features` 아래에 추가 분리합니다.

## App.tsx 역할

`App.tsx`는 Route/Page/Layout 조립만 담당합니다. Header, Sidebar, Footer, 업무 화면, API 호출 구현을 한 파일에 몰아넣지 않습니다. Artifact Validator는 기본적으로 `App.tsx`가 220줄을 초과하거나 분리된 `AppLayout`/`HomePage`를 조립하지 않으면 Architecture 오류로 처리합니다.

## 완료 Gate

React + TypeScript Agent의 실제 생성 결과에 다음이 있으면 완료 처리하지 않습니다.

- `frontend/src/App.jsx`
- `frontend/src/main.jsx`
- `frontend/src/services/api.js`
- 필수 Layout/Page/Service/Type 파일 누락
- 과도하게 큰 `App.tsx`

이 검증은 Design → Code Generation → Build Artifact Validation → As-Built Architecture → Conformance 흐름에 포함됩니다.
