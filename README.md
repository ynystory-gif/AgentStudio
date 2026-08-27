# THEANOVA AgentStudio v5.369

## v5.369 FailedBuildRedevelopmentCheckpoint

### 핵심 변경

- 프로젝트 이름/경로를 지정하면 `reports/current_run.json`, `workflow_state.json`, `agentstudio_design_checkpoint.json`을 확인해 이전 Agent 개발 실패 이력을 자동 감지합니다.
- 재개 가능한 실패 기록이 있으면 Agent 제작 진행 영역의 **`↻ 재개발 시작`** 버튼이 자동 활성화됩니다.
- 실패 이력이 있는 프로젝트에서는 일반 `개발 시작`을 비활성화해 실수로 처음부터 전체 Workflow를 재실행하지 않도록 합니다.
- `재개발 시작`은 이전 Requirement/Workflow/Architecture/File Plan/Settings/Debug State를 재사용하며 **기록된 실패 단계 직전 Node부터** 새 LangGraph 실행을 시작합니다.
- 사용자가 실패 후 직접 소스 코드를 수정한 경우, 요구사항 수집/설계/프로젝트 생성 단계는 다시 수행하지 않고 수정된 소스를 실패 직전 검증 단계부터 재검증합니다.
- 실패 단계 예: `build_artifact_validation` → `settings_validation`, `architecture_conformance` → `as_built_architecture`, `test` → `environment_configuration`.
- Backend에 `/workflow/redevelop-start-job` 전용 Endpoint를 추가해 브라우저의 오래된 상태가 아니라 프로젝트 폴더의 최신 실패 Checkpoint를 기준으로 재개합니다.
- 재개발 실행은 새 Run ID를 사용하되 `previous_run_id`, `failure_stage`, `resume_from_node`를 보존하여 실행 결과/진단 추적이 가능합니다.
- v5.368 Failed Build Resume Checkpoint와 기존 기능을 모두 유지합니다.

---

## v5.369 ReactTypeScriptLegacySourceCleanupFix

### v5.369 changes

- React + TypeScript 확정 Agent에서 `frontend/src/App.jsx`, `main.jsx`, `services/api.js`가 이전 생성/Repair에서 남아 있으면 Build Artifact Validation 전에 AgentStudio가 결정적으로 삭제합니다.
- LLM이 금지된 JS/JSX 파일을 0-byte 빈 파일로 바꿔도 `Path.is_file()` 검증에 계속 걸리던 `REPAIR_PLAN_INCOMPLETE` 반복을 제거했습니다.
- TypeScript File Plan의 `app.jsx/app.tsx`는 OS와 관계없이 canonical `frontend/src/App.tsx`로 정규화해 Windows 개발 후 Linux/Vercel 배포에서 casing 충돌이 나지 않도록 했습니다.
- 삭제 결과는 `patch_result`에 `deleted=true`, `verified=true`로 기록하여 실패 진단/실행 결과에서 확인할 수 있습니다.
- v5.366의 검색 입력 렌더링 최적화, Chrome 장기 리소스 cleanup, UI Layout Gallery 노출 개선을 모두 유지합니다.

- Isolated project-search typing from the giant App render using a memoized local input with delayed commit.
- Deferred/memoized project filtering so expensive list work does not run on every keystroke.
- Bounded realtime job state and terminal scrollback to prevent browser memory growth during long sessions.
- Added SPA-unmount cleanup for terminal WebSockets and xterm instances/disposables.
- Exposed the UI/Layout Template Gallery in the actual unified Agent Design workspace header and right configuration panel.


v5.364를 기준으로 신규 Agent 설계 좌측 `04 DB 설계` 요약에서 동일 DB 기술이 두 번 표시되는 문제를 수정한 버전입니다.

### 핵심 변경

- `PostgreSQL · Redis · pgvector`처럼 이미 조합된 DB 요약 문자열과 대화에서 재감지한 DB 기술을 토큰 단위로 정규화
- PostgreSQL / Redis / pgvector를 Canonical Label로 변환한 뒤 중복 제거
- `PostgreSQL · Redis · pgvector · PostgreSQL · Redis · pgvector` 형태의 중복 표시 방지
- 신규 Agent 설계 화면과 Workspace 좌측 설계 요약이 같은 정규화 결과를 사용
- v5.364 UI Layout Template Gallery 및 기존 기능 유지

---

## v5.364 AgentUILayoutTemplateGallery

v5.363을 기준으로 신규 Agent 설계 과정에 **시각적 UI / Layout Template Gallery**를 추가한 버전입니다.

### 핵심 변경

- 신규 Agent 설계 단계에 `UI / Layout` 단계 추가
- 쇼핑/검색, AI Chat, RAG, SaaS Dashboard, Admin CRUD, Search Portal, Landing, Mobile, Monitoring 등 15+ 템플릿 제공
- Agent 목적/요구사항 키워드에 따라 추천 템플릿을 우선 표시
- 각 템플릿을 실제 이미지 복사가 아닌 AgentStudio 자체 Wireframe Thumbnail로 표시
- Header, Sidebar, Sidebar 접기, Footer, 사용자 메뉴, Main Layout, Theme, Responsive를 사용자가 직접 조정
- UI가 없는 Agent를 위한 `UI 없음 / Headless Agent` 선택 지원
- 선택 결과를 요구사항 Draft에 저장하고 이전 인터뷰 복원 시 함께 복구
- `confirmed_requirements.ui_layout`과 Workflow 설계 Prompt에 반영하여 실제 생성 코드의 Layout/File Structure에 전달
- Agent PPT 전체 문서에 편집 가능한 PowerPoint Native Shape 기반 `UI / UX Layout` 슬라이드 자동 포함
- Streamlit/React 등 UI 기술과 Layout Schema를 분리해 선택한 화면 구조를 기술에 맞게 구현하도록 설계 Context 제공

자세한 내용은 `docs/UI_LAYOUT_TEMPLATE_GALLERY_V5364.md`를 참고하십시오.

---

## v5.363 AttachmentAnalysisResizableScrollPanel

v5.362를 기준으로 신규 Agent의 **첨부 파일 AI 정리 패널이 긴 요구사항 때문에 인터뷰 화면을 가리는 문제**를 개선한 버전입니다.

### 핵심 변경

- 전체형 첨부 분석 패널의 기본 높이를 화면의 약 42%로 제한
- 패널 하단 **높이 조절** 바를 위/아래로 드래그하여 크기 변경
- 파일/AI 요약/추출 요구사항 영역을 내부 단일 스크롤로 탐색
- 최소 180px ~ 최대 약 72vh 범위로 Resize 제한
- 사용자가 조절한 높이를 브라우저에 저장하고 다음 표시에도 유지
- `기본 높이` 버튼, Resize Handle 더블클릭, 키보드 ↑/↓ 조절 지원
- Compact Sidebar Summary는 기존 크기 유지
- v5.362 ERD/PPT 관계선 개선, v5.361 Context Isolation, v5.360 Deep Requirement Mining 등 기존 기능 유지

자세한 내용은 `docs/ATTACHMENT_ANALYSIS_RESIZABLE_SCROLL_PANEL_V5363.md`를 참고하십시오.

---

## v5.362 ErdKeyBadgeRelationRoutingDatabaseUrlGuide

v5.361을 기준으로 **PPT DB ERD의 PK/FK 가독성·관계선 라우팅**과 **생성 Agent의 DATABASE_URL 초기 설정 안내**를 개선한 버전입니다.

### 핵심 변경

- PPT DB ERD의 `PK` / `FK` 배지를 충분한 가로 폭으로 고정하고 줄바꿈을 금지하여 항상 가로로 표시
- ERD 카드의 키 배지/컬럼명/데이터 타입 영역을 재배치하여 좁은 카드에서도 열 정보가 겹치지 않도록 개선
- 관계선마다 서로 다른 직각(orthogonal) 라우팅 lane과 출발/도착 anchor를 배정
- 관계선이 같은 수평선으로 겹치지 않도록 lane을 분리하고 화살표 방향을 명확히 표시
- 관계가 많은 DB는 슬라이드당 테이블 수를 자동으로 줄여 혼잡도를 낮춤
- 생성 Agent `SYSTEM_ADMIN.cmd` 최초 실행 시 `.env`의 `DATABASE_URL=` 앞에 PostgreSQL URL 형식/로컬 예시 안내를 자동 삽입
- 콘솔의 `[SETUP_REQUIRED]` 화면에도 `DATABASE_URL` 입력 형식과 로컬 예시를 함께 표시
- `.env.example`의 결정적 fallback 생성 시에도 동일한 DATABASE_URL 안내 주석 포함
- v5.361 신규 Agent/프로젝트 Context 분리, v5.360 Deep Requirement Mining, v5.356 DB ERD/PPT 등 기존 기능 유지

자세한 내용은 `docs/ERD_KEY_BADGE_RELATION_ROUTING_DATABASE_URL_GUIDE_V5362.md`를 참고하십시오.

---

## v5.361 NewAgentProjectContextIsolation

v5.359를 기준으로 **첨부 Notebook/문서 요구사항 심층 추출, 인터뷰 Slot 완료 처리, Agent 개발 테스트 Source Repair**를 강화한 버전입니다.

### 핵심 변경

- Notebook Markdown Cell의 문제 문장·bullet·제약·산출물을 우선 보존하는 Deep Requirement Mining
- 첨부 문서별 `REQ-xxx` Requirement Registry와 파일/Cell 출처 표시
- Agent 설계 화면 `첨부 파일 AI 정리` 안에 추출 요구사항 목록과 카테고리/출처 표시
- 첨부 분석 결과와 Requirement Registry를 Draft 저장/복원 및 Workflow/DB/코드 생성 Context에 유지
- `없다 / 필요 없다 / 사용하지 않는다`를 정상 완료 답변으로 처리하여 같은 질문 반복 방지
- 명시적인 `./main.py` 테스트 경로를 동명 `backend/app/main.py`보다 우선하는 Focused Repair 대상 선택
- 생성 Source 전체를 감싼 Markdown code fence를 Patch 적용 시 및 테스트 직전에 결정적으로 제거
- 기존 v5.359 첨부 Summary, Fast Interview, Agent Progress, DB ERD, Agent/Studio PPT 기능 유지

자세한 내용은 `docs/DEEP_ATTACHMENT_REQUIREMENT_MINING_ROOT_SOURCE_REPAIR_V5360.md`를 참고하십시오.

---

## v5.356 이전 변경 이력

v5.355 `SeparatedAgentStudioPptExport`를 기준으로 **DB ERD Workspace + PowerPoint Export**를 추가한 버전입니다.

### v5.356 핵심 변경

- `아키텍처` 탭 오른쪽에 **DB ERD** 탭 추가
- 신규 Agent 생성 시 Agent Factory의 DB 설계를 기준으로 DB별 ERD 자동 생성
- 기존 프로젝트 로드 시 SQL DDL / 기술 스택 / 소스 사용 흔적을 분석해 DB별 ERD 자동 생성
- PostgreSQL, MSSQL, Oracle, SQLite, MySQL 등 관계형 DB를 엔진별로 분리
- `pgvector`는 Vector Store ERD로 별도 표시
- `Redis`는 관계형 ERD 대신 Key Pattern / Purpose / TTL 기반 논리 데이터 모델로 별도 표시
- `Firestore`는 Collection Model로 별도 표시
- DB ERD 탭에 **PPT 다운로드** 추가
- **Agent PPT** 전체 문서에 현재 Agent/프로젝트 DB ERD 포함
- **Studio PPT** 전체 문서에 THEANOVA AgentStudio 자체 DB ERD 포함
- Agent PPT와 Studio PPT의 DB ERD 데이터는 서로 섞이지 않도록 서버에서 분리 생성
- PPT의 ERD Table/Card/Connector/Text는 편집 가능한 PowerPoint 네이티브 객체 기반

### PPT 범위

- 페이지 `PPT 다운로드` → 현재 생성 Agent / 로드 프로젝트만
- `Agent PPT` → 현재 Agent/프로젝트의 Workflow, Run, Analysis, Architecture, DB ERD
- `Studio PPT` → THEANOVA AgentStudio 자체 Workflow, Runtime, Governance, Architecture, DB ERD

### 이전 기능 유지

- v5.355 Agent PPT / Studio PPT 분리
- v5.354 Project Adaptive Workflow / Report / Architecture
- v5.353 Large Architecture Visual PPT
- v5.352 SYSTEM_ADMIN Version Sync
- v5.350 Valid Notebook Create
- v5.349 Notebook Top-Level Await
- 검색 트리 Toggle / Unified Find / Project Text Search

자세한 내용은 `docs/DATABASE_ERD_WORKSPACE_PPT_V5356.md`를 참고하십시오.


### v5.361 NewAgentProjectContextIsolation

- `+ 신규 Agent 만들기`를 프로젝트 컨텍스트의 강한 경계로 처리합니다.
- 이전 프로젝트의 `loadedProjectAnalysis`, Workflow, DB preview/ERD, 분석 리포트, Coding Style, 실행 결과, 확정 요구사항을 신규 Agent에 재사용하지 않습니다.
- 신규 Agent 시작 시 `workflowReq`와 이전 프로젝트 이름/경로를 초기화합니다.
- 비동기 Project Adaptive 분석에 context epoch를 부여하여, 사용자가 신규 Agent로 전환한 뒤 늦게 도착한 이전 프로젝트 응답을 폐기합니다.
- 신규 Agent 모드에서는 `selectedProjectId`가 없으므로 Workflow/Report/PPT 상태가 기존 Project Adaptive Report로 fallback하지 않습니다.


## v5.369 Failed Build Resume Checkpoint
- 신규 Agent 개발 실패 후 요구사항/대화/Workflow/UI Layout/첨부 분석 요약/실패 실행 정보를 프로젝트 `reports/agentstudio_design_checkpoint.json`에 영속 저장합니다.
- 브라우저 localStorage와 프로젝트 Checkpoint를 함께 조회하고 더 최신 기록을 사용자 승인 후 복원합니다.
- v5.367 이하 프로젝트도 `reports/requirements_snapshot.json`, `workflow_state.json`, `current_run.json`을 사용해 가능한 범위에서 복원합니다.
- 이전 실패 Workflow State와 실패 원인을 다음 Agent Factory 실행의 `previous_build_state`/`resume_context`로 전달합니다.
- 신규 Agent 시작은 기존처럼 완전 격리되며, 같은 프로젝트 경로를 다시 선택했을 때만 이전 기록 후보를 제시합니다.
