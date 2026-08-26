# v5.352 SYSTEM_ADMIN Launcher Version Sync Fix

## 문제

v5.351 배포본의 `SYSTEM_ADMIN.ps1`에 `$ExpectedAgentStudioVersion = "5.349"`가 남아 있었습니다.
따라서 같은 설치 폴더의 Backend v5.351이 정상 시작되어 `/api/health`가 200 OK를 반환해도 Launcher가 이를 오래된 Backend로 오판하고 ExitCode=1로 종료했습니다.

## 수정

- `SYSTEM_ADMIN.ps1`의 현재 버전 하드코딩을 제거했습니다.
- Launcher는 같은 설치 폴더의 `backend/app/main.py`에서 FastAPI `version`을 읽어 기대 버전을 결정합니다.
- 파싱에 실패하는 예외 상황에서만 v5.352 fallback을 사용합니다.
- 실제로 다른 버전의 Backend가 같은 포트에서 실행 중이면 기존 버전 불일치 검사는 계속 동작합니다.
- Backend, Health API, Frontend, PPT Export, Codex Client 등 현재 런타임 버전을 v5.352로 동기화했습니다.

## 회귀 방지

`backend/validate_v5352_system_admin_version_sync_contract.py`에서 다음을 확인합니다.

- stale `5.349` Launcher literal이 존재하지 않는지
- Launcher가 로컬 Backend 소스에서 기대 버전을 계산하는지
- Frontend/FastAPI/Health 버전이 모두 5.352인지
- Health 버전과 로컬 FastAPI 버전이 서로 일치하는지
