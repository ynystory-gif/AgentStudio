# v5.172 Generated SYSTEM_ADMIN Launcher

- 모든 생성 Agent의 프로젝트 루트에 `SYSTEM_ADMIN.cmd`를 제공합니다.
- 사용자는 `SYSTEM_ADMIN.cmd` 하나만 실행하면 됩니다.
- CMD는 `chcp 65001`로 UTF-8 콘솔을 사용하고 `SYSTEM_ADMIN.ps1`을 호출합니다.
- 최초 실행 시 Python 3.12 `.venv`를 생성하고 Backend/Frontend 의존성을 준비합니다.
- 이전 실행의 PID를 정리하여 중복 실행을 방지합니다.
- FastAPI Backend와 React/Vite Frontend를 자동 실행합니다.
- MCP stdio Server는 장기 프로세스로 임의 실행하지 않고 문법/준비 상태를 확인하며 실제 Agent가 필요할 때 stdio로 실행하도록 둡니다.
- Frontend가 있으면 `http://127.0.0.1:5173`을 자동으로 엽니다.
- Runtime PID/로그는 생성 Agent의 `.agentstudio/runtime`, `.agentstudio/logs`에 저장합니다.
- 최종 `COMPLETED` 판정 전에 Launcher 파일 생성 및 기본 계약을 검증합니다.

Health: `5.172 / GeneratedSystemAdminLauncher`
