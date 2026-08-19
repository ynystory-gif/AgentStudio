# v5.174 Generated FastAPI Import Contract Fix

## 문제
생성 Agent의 `backend/app/main.py`가 `from routers import ...`를 사용하면서 Generated SYSTEM_ADMIN은 `backend`를 작업 폴더로 `uvicorn app.main:app`을 실행하여 `ModuleNotFoundError: No module named routers`가 발생했습니다. 일부 생성 파일은 `from backend.app...`와 `from app...`도 혼용했습니다.

## 수정
- `backend/app` 내부 import를 `app.*` 또는 상대 import 계약으로 정규화
- `backend/app`, `routers`, `services`, `schemas`, `core`, `mcp`에 필요한 `__init__.py` 자동 생성
- Code Generation 직후와 Settings Generator 이후 Build Artifact Validation에서 재검증
- Generated SYSTEM_ADMIN에서 Backend 시작 전 `app.main:app` import preflight 수행
- Launcher 계약 검증에 backend working directory/import preflight 포함

Health: `5.174 / GeneratedFastApiImportContractFix`
