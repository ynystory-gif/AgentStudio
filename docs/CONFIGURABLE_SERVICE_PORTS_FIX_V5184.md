# v5.184 Configurable Service Ports Fix

## 목적
개인 PC마다 8000/5173 포트를 이미 다른 프로그램이 사용하고 있을 수 있으므로 AgentStudio 시스템 관리자에서 Backend/Frontend 포트를 직접 설정하고 사용 가능 포트를 추천받을 수 있도록 합니다.

## 변경 내용
- 시스템 관리 화면에 `서비스 포트 설정` 영역 추가
- Backend API 포트 / Frontend 포트 직접 입력 및 저장
- 기본값: Backend 8000 / Frontend 5173
- 포트 사용 여부 검사 및 사용 가능한 추천 포트/후보 표시
- `추천 포트 적용` 버튼 제공
- 포트 범위 1024~65535 검증 및 Backend/Frontend 동일 포트 금지
- 포트 설정은 `backend/.env` bootstrap 값으로 저장되어 SYSTEM_ADMIN 시작 전에 읽을 수 있음
- SYSTEM_ADMIN은 저장된 선호 포트가 비어 있으면 그대로 사용
- 저장 포트를 다른 프로그램이 사용 중이면 해당 프로세스를 강제 종료하지 않고 다음 사용 가능한 포트로 안전하게 대체
- 외부 `uvicorn/npm/vite` 프로세스를 광범위하게 종료하던 패턴 제거
- 실제 선택된 포트를 `frontend/public/runtime-config.js`에 기록하여 Frontend API/WebSocket 연결도 동일 포트를 사용
- 시스템 관리자 상단에는 실제 현재 실행 URL을 계속 표시

## 설정 키
- `AGENTSTUDIO_BACKEND_PORT=8000`
- `AGENTSTUDIO_FRONTEND_PORT=5173`

변경된 포트는 다음 `SYSTEM_ADMIN.cmd` 재실행부터 적용됩니다.
