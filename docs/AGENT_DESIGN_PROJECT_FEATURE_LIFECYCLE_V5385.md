# v5.385 AgentDesignProjectFeatureLifecycle

## 목적

신규 Agent의 `Agent 설계 인터뷰`가 한 번의 세션에서 끝나지 않아도 되도록 설계 작업 자체를 DB 프로젝트로 저장합니다. 사용자는 다른 작업을 한 뒤 `프로젝트 목록 / 열기`에서 이전 설계를 불러와 대화, 요구사항, UI Layout, Workflow Preview, 첨부 분석, 기능 변경 상태를 이어서 진행할 수 있습니다.

## 설계 프로젝트 저장 / 로드 / 목록

- `agent_design_projects`: 최신 설계 상태 저장
- `agent_design_project_versions`: 수동 저장 또는 기능 변경 전 Snapshot 보존
- 저장 대상: Agent 이름, 생성 예정 경로, 인터뷰 Chat, 확정 요구사항, Workflow Preview/Quality, UI Layout, 첨부 요구사항 분석, 기능 Registry, 현재 단계/진행률
- 프로젝트가 실제 소스 폴더로 생성되기 전에도 PostgreSQL에 저장 가능
- 설계 프로젝트와 Generated Project는 분리하여 관리

## 기능 관리

기존 인터뷰에서 감지된 기능과 사용자가 직접 추가한 기능을 하나의 기능 관리 화면에서 관리합니다.

- 기능 추가
- 기능 수정 / 재정의
- 기능 비활성화
- 기능 삭제
- 삭제된 기능 복원

기능 삭제 시 즉시 코드를 지우지 않습니다. UI/API/DB/Auth/Workflow/Test 등 영향 가능 영역을 먼저 보여 주고 확인 후 최신 요구사항에 `REMOVED` 상태를 기록합니다. 비활성화는 `DISABLED`로 유지하여 삭제와 구분합니다.

## Incremental Generation 연결

기능 Registry는 설계 인터뷰의 최신 요구사항보다 높은 우선순위의 변경 Registry로 Workflow 요청에 포함됩니다.

- `ACTIVE`: 생성/유지 대상
- `DISABLED`: 코드/DB를 제거하지 않고 비활성화
- `REMOVED`: 신규 Workflow/생성 대상에서 제거
- 기능 변경 시 기존 `targetWorkflowPreview`를 `previousTargetWorkflowPreview`로 남기고 Workflow를 무효화하여 기존 Incremental Designer가 변경 범위만 재설계하도록 연결

## 안전한 Snapshot

기능 ADD/MODIFY/DISABLE/REMOVE 전에 이미 DB 설계 프로젝트가 저장되어 있으면 자동으로 이전 설계를 버전 Snapshot으로 남깁니다. 따라서 기능 삭제 후에도 DB에는 삭제 이전 설계 이력이 남습니다.
