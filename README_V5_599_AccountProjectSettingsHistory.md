# THEANOVA AgentStudio v5.599 — Account / Project Settings DB + History

v5.598의 RAG Studio 1~6차 기능, RAG API 통합 수정, Source Picker, Dark UI 및 테이블별 PK 명명 정책을 유지하면서 계정 설정과 프로젝트 설정을 DB에서 분리 관리하고 수정 이력을 조회할 수 있도록 확장한다.

## 1. 계정 저장 DB 연결

- `account_database_profiles`에 로그인 계정별 DB 연결 메타데이터를 저장한다.
- PostgreSQL/Supabase/Redis/Firestore 등 연결 종류, Host/Port/Database/Schema/User 등 재사용 가능한 비밀이 아닌 설정을 저장한다.
- `password`, `_password_dpapi`, Service Account private key/content, token, API key는 DB JSON에서 제거한다.
- Windows SQL Workspace의 실제 비밀번호는 기존 DPAPI 기반 로컬 보관을 유지한다.

## 2. 프로젝트별 설정 분리 저장

- `account_project_settings`는 `member_id + project_key + setting_group + setting_key` 기준으로 프로젝트별 설정을 저장한다.
- 코드 편집 DB 연결은 `CODE_EDITOR_DB` 그룹으로 프로젝트별 활성 연결을 보관한다.
- Agent 설계 수동 `지금 저장` 시 REQUIREMENTS / RUNTIME / DATABASE / DATABASE_RESOURCE_PLAN / UI_LAYOUT / TOOL_PROMPT / PROMPT_TOOL_STUDIO / DEVELOPMENT_STAGE / RECOMMENDATION / CODING_STYLE 등 주요 설정을 별도 Row로 동기화한다.
- 전체 복원을 위한 기존 `agent_design_projects.snapshot` 및 Version Snapshot은 유지한다.

## 3. 설정이 없는 프로젝트의 초기 목록

- 코드 편집 우측 DB 연결에서 현재 프로젝트 연결이 없으면 계정 저장 DB 연결 목록을 먼저 표시한다.
- Agent 설계 Database 영역도 프로젝트 DB 설정이 없으면 계정 저장 DB 목록을 보여준다.
- RAG Studio DB / Vector Store도 프로젝트 RAG DB 바인딩이 없으면 계정 저장 PostgreSQL/Supabase 목록을 보여준다.
- 계정 프로필을 선택하면 프로젝트 설정으로 별도 바인딩하며, 계정 공통 프로필 자체를 프로젝트별 편집으로 덮어쓰지 않는다.

## 4. 이력 정보 탭

Agent 설계 중앙 상위 탭 순서는 다음과 같다.

`Agent 설계 인터뷰 → Prompt & Tool Studio → RAG Studio → 이력 정보`

`이력 정보`는 현재 프로젝트의 `project_setting_histories`를 조회한다.

- 수정 일시
- Category
- Action
- 제목/요약
- 클릭 시 변경 전 JSON / 변경 후 JSON

DB 연결 저장/적용/삭제, Agent 설계 수동 저장의 주요 설정 변경, RAG Collection/Source/Retrieval/Intelligence/Operation/Security/Evaluation 변경을 이력으로 남긴다.

## 5. 신규 DB 테이블 및 PK

전역 PK 규칙에 따라 단순 `id`를 사용하지 않는다.

- `account_database_profiles.account_database_profiles_id`
- `account_setting_profiles.account_setting_profiles_id`
- `account_project_settings.account_project_settings_id`
- `project_setting_histories.project_setting_histories_id`

기존 인증 테이블은 레거시 호환 범위이며, 이번 버전에서 새로 생성한 테이블은 모두 테이블 기반 PK 규칙을 따른다.

## 6. 저장 원칙

- 계정 공통 재사용 설정: Account Profile
- 프로젝트 확정 설정: Account Project Setting
- 전체 Agent 복원: 기존 Agent Design Snapshot
- 변경 추적: Project Setting History
- 비밀번호/Private Key/Token: DB에 평문 저장 금지
