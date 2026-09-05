# THEANOVA AgentStudio v5.601 — History SQL / Workflow Save / Existing Prompt·Tool Sync

v5.600을 기준으로 프로젝트 수정 이력, Workflow 저장, 기존 프로젝트 Prompt/Tool 복원과 변경 상태 표시, 중복 저장 방지 기능을 보강한다.

## 1. 이력 정보 SQL 임시 파일

- `이력 정보` 목록의 각 항목에 `SQL` 버튼을 추가했다.
- 상세 이력에도 `SQL 임시 파일` 버튼을 추가했다.
- 버튼을 누르면 현재 프로젝트의 `.agentstudio/sql_scratch/` 아래에 `history_<history_id>_<category>_<timestamp>.sql` 파일을 만든다.
- SQL 파일에는 해당 이력 Row를 확인하는 안전한 SELECT, 변경 전/후 JSON 주석이 포함된다.
- 이력 payload에서 SQL/DDL/query 문자열이 확인되는 경우 관련 SQL도 함께 넣는다.
- 생성된 SQL은 자동 실행하지 않고 코드 편집 탭의 임시 파일로 연다.

## 2. Workflow 탭 저장

- Workflow 탭 상단에 `저장` 버튼을 추가했다.
- 개발 대상 Workflow 또는 기존 프로젝트 소스에서 추론된 Workflow를 프로젝트 `WORKFLOW/default` 설정으로 저장한다.
- 저장 후에는 `✓ 저장됨` 상태로 바뀌며 Workflow 내용이 다시 변경되기 전에는 저장 버튼이 비활성화된다.
- 프로젝트를 다시 열면 명시적으로 저장한 Workflow 설정을 복원한다.
- 저장된 Workflow 변경은 프로젝트 이력에 `WORKFLOW` 분류로 남는다.

## 3. 변경사항 없는 저장 차단

- `account_project_settings` 저장은 기존 JSON과 `source_profile_id`가 동일하면 DB UPDATE와 History INSERT를 수행하지 않는다.
- 프로젝트 수정 이력도 동일한 연속 category/action/title/before/after payload이면 새 History Row를 만들지 않는다.
- Agent Design Project 저장도 저장 시각 같은 volatile metadata를 제외한 실제 설계 내용이 동일하면 Snapshot/Version을 새로 만들지 않는다.
- Account DB Profile 및 공통 설정 Profile도 동일 값이면 DB UPDATE를 하지 않는다.
- Prompt & Tool Studio의 Prompt/Tool/Routing/State/Test Report/Studio Version 저장도 마지막 저장 내용과 동일하면 새 버전을 추가하지 않는다.

## 4. 기존 프로젝트 Prompt / Tool 자동 로드

- 기존 프로젝트를 로드하면 저장된 `PROMPT_TOOL_STUDIO/default` 설정을 먼저 복원하고 Source-only adaptive 분석에서 Prompt 변수, LangChain PromptTemplate, `@tool`, MCP Tool decorator/registration, tools 경로 Symbol을 감지한다.
- Source Scan은 기존 4,000자 Preview만 보지 않고 Prompt/Tool/Agent 관련 파일을 우선으로 파일당 최대 120,000자, 전체 최대 8,000,000자 범위에서 추가 확인해 뒤쪽 정의도 놓치지 않도록 했다.
- 감지한 Prompt/Tool을 중앙 `Prompt & Tool Studio`로 동기화한다.
- 기존 프로젝트에 저장된 Studio 설정이 있으면 사용자 편집값을 유지하면서 현재 소스의 path/line/fingerprint를 다시 연결한다.
- 기존 프로젝트에 Studio Prompt가 저장되어 있지 않으면 감지된 첫 Prompt를 System Prompt 기준값으로 사용한다.

## 5. 신규 / 변경 표시

- 최초 v5.601 Source baseline에서는 현재 프로젝트에 이미 존재하는 Prompt/Tool을 `동일`로 본다.
- 이후 저장된 Source fingerprint에 없던 Prompt/Tool이 나타나면 `신규`로 표시한다.
- 같은 Prompt/Tool의 Source fingerprint가 바뀌면 `변경`으로 표시한다.
- Studio에서 새로 추가한 Tool/RAG Tool/MCP Tool은 실제 프로젝트 Source에 생성되기 전까지 `신규`로 표시한다.
- Source에 동일 Tool이 생성되면 이름/Source를 연결해 `동일` 상태로 전환한다.
- Source Tool을 Studio에서 다시 편집하면 `변경` 상태로 표시한다.
- System Prompt도 프로젝트 Prompt와 동일/변경/신규 상태를 표시한다.

## DB 정책

이번 버전은 신규 DB 테이블을 만들지 않는다. v5.600의 기존 Account/Project Settings 및 Project History 테이블을 그대로 사용한다.

## 주요 수정 파일

- `backend/app/services/account_setting_service.py`
- `backend/app/api/account_settings_routes.py`
- `backend/app/services/project_adaptive_report.py`
- `backend/app/api/routes.py`
- `frontend/src/app/App.tsx`
- `frontend/src/features/history/ProjectHistoryPanel.tsx`
- `frontend/src/features/history/projectHistory.css`
- `frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx`
- `frontend/src/features/prompt-tool-studio/model.ts`
- `frontend/src/styles.css`
