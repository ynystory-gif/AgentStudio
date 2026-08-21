# v5.307 Frontend TypeScript System / Runtime UI Migration

## 목표

v5.306을 안정 기준으로 SystemPage에서 결합도가 낮은 표시 계층을 TypeScript 컴포넌트로 이동한다. Backend 설정 저장, Runtime 전환 orchestration, 비밀번호 처리와 API 호출 순서는 변경하지 않는다.

## 이동한 영역

- `ServicePortSettingsPanel`
- `RuntimeDatabasePanel`
- `OllamaSettingsPanel`
- `SystemStatusSummary`
- System/Runtime 관련 TypeScript 계약 (`src/types/system.ts`)

## 의도적으로 App.jsx에 유지한 영역

- `/settings`, `/settings/database-runtime` 등 Backend API 호출
- Supabase URL 저장/초기화/Runtime 전환 orchestration
- PostgreSQL 관리자/앱 비밀번호 ref 및 provisioning
- pgvector 설치 job polling
- Ollama process API 호출과 job polling
- 일반 Settings form helper (`renderField`, `renderPathField`, `saveGroup`)

## 회귀 방지

`validate_frontend_contracts.cjs`에 System Runtime 컴포넌트 import 계약을 추가했다. App.jsx에서 컴포넌트를 사용하면서 import가 빠지면 `npm run typecheck`/`npm run build` 전에 실패한다.
