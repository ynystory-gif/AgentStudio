# System Admin Version Sync Fix v5.236

## 문제

v5.235 Backend/Frontend는 정상적으로 `5.235`를 보고하지만 `SYSTEM_ADMIN.ps1`의 `$ExpectedAgentStudioVersion`이 `5.234`로 남아 있었습니다.

그 결과 Backend가 정상적으로 시작되어 `/api/health`가 `200 OK`를 반환한 뒤에도 SYSTEM_ADMIN이 버전 불일치로 중단되어 PostgreSQL Health Check, Frontend 시작, 브라우저 열기 단계로 진행하지 못했습니다.

## 수정

- SYSTEM_ADMIN 기대 버전을 현재 릴리스와 동일한 `5.236`으로 동기화
- FastAPI 앱 버전/Health API 버전을 `5.236`으로 동기화
- Frontend 버전을 `5.236`으로 동기화
- Health API build 식별자를 `SystemAdminVersionSyncFix`로 갱신

## 정상 시작 순서

1. Backend 시작
2. `/api/health` 성공
3. Backend/Frontend 릴리스 버전 검증 성공
4. PostgreSQL Health Check
5. Frontend 시작
6. Frontend Health Check
7. 브라우저에서 AgentStudio 열기
