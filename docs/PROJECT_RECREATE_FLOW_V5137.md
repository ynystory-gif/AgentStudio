# v5.137 Project Recreate Flow

## 기존 문제

신규 Agent 프로젝트 생성 시 동일한 `project_root`가 DB에 있으면:

`이미 등록된 프로젝트 경로입니다.`

메시지만 반환하고 제작을 중단했습니다.

## 변경

Backend `/projects/create-agent`에 `force_recreate` 옵션을 추가했습니다.

첫 요청에서 동일 경로가 발견되면:

- `conflict=true`
- `conflict_type=PROJECT_PATH_ALREADY_REGISTERED`
- `can_recreate=true`

를 반환합니다.

Frontend는 다음 확인창을 표시합니다.

`이미 등록된 프로젝트 경로입니다. 재생성하시겠습니까?`

### 확인

기존 Project Row를 중복 추가하지 않고 재사용합니다.
현재 Agent 설계의 이름/Cache/Temp/Output/Venv/Models 경로로 프로젝트 정보를 갱신하고
Agent Factory 개발을 계속할 수 있는 `PROJECT_CREATED` 상태로 이동합니다.

### 취소

현재 설계 값을 유지하고 중단합니다.
Workspace 상단의 `← 신규 Agent 설계` 버튼을 눌러 프로젝트 경로를 수정할 수 있습니다.

## 중요

"재생성"은 DB Row를 삭제하고 새 ID를 만드는 의미가 아닙니다.
동일 경로의 기존 DB Project를 재사용하여 중복 등록을 막고,
그 경로에 Agent 코드를 다시 생성/수정하는 방식입니다.
