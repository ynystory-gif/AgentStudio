# v5.218 PowerShell Admin Root File Read Fix

## 변경 사항

1. 프로젝트 파일 읽기/저장 root 안정화
   - 코드 편집 파일 읽기는 React `root` state 하나만 사용하지 않고 현재 선택 프로젝트의 `project_root`를 최우선으로 사용합니다.
   - `.ps1`을 포함한 모든 파일 형식에 동일하게 적용됩니다.
   - 외부 파일 reload/watcher와 Editor 저장도 같은 Workspace root 기준을 사용합니다.

2. AgentStudio 터미널 관리자 권한 보장
   - `SYSTEM_ADMIN.cmd`가 `SYSTEM_ADMIN.ps1`을 실행하면 PowerShell 스크립트가 관리자 여부를 확인합니다.
   - 관리자 권한이 아니면 UAC 승격을 요청하고 승격된 프로세스에서 AgentStudio Backend/Frontend를 시작합니다.
   - Backend가 관리자 권한이 아닌 상태에서는 Windows Terminal session 생성을 거부하고 `SYSTEM_ADMIN.cmd` 재실행 안내를 반환합니다.
   - 따라서 정상 진입점으로 실행된 AgentStudio의 PowerShell terminal은 관리자 권한을 상속합니다.

3. 기본 PowerShell 탭의 작업 경로
   - SYSTEM_ADMIN 실행 시 `frontend/public/runtime-config.js`에 실제 AgentStudio 설치 경로를 `AGENTSTUDIO_ROOT`로 기록합니다.
   - 첫 번째 `PowerShell` 탭은 프로젝트와 무관하게 이 경로에서 시작합니다.
   - 예: `PS F:\Source\repos\Theanova\AI\AgentStudio>`
   - 프로젝트별 terminal tab은 기존처럼 해당 프로젝트 root에서 시작합니다.
