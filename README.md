# THEANOVA AgentStudio v5.382



## v5.382 SourceTextLineBookmarkNavigation

- 북마크 위치를 찾기 어렵던 문제를 개선해 Notebook 상단에 **`🔖 현재 줄`** 버튼을 추가했습니다. 이제 왼쪽 여백을 정확히 찾지 않아도 현재 커서 줄에 바로 북마크를 추가/해제할 수 있습니다.
- Notebook Code Cell에서는 **줄 번호 또는 줄 번호 왼쪽 여백**을 클릭해도 북마크가 토글되도록 클릭 영역을 넓혔습니다.
- `.py`, `.js`, `.ts`, `.tsx`, `.java`, `.cs`, `.sql`, `.ps1`, `.cmd`, `.json`, `.yaml`, `.md`, `.txt` 등 일반 Source/Text Editor에도 동일한 줄 북마크를 적용했습니다.
- 일반 Source/Text Editor 상단에는 `🔖 현재 줄`, `◀`, 북마크 개수, `▶`, `해제` 컨트롤을 표시합니다. 위쪽 코드를 확인한 뒤 `▶`를 누르면 다음 북마크로 즉시 복귀할 수 있습니다.
- 일반 Source/Text Editor에서도 Monaco의 glyph margin/줄 번호 영역을 클릭하면 해당 줄의 파란 리본 북마크를 추가/해제합니다.
- 북마크는 **프로젝트 + 파일 경로** 단위로 localStorage에 저장되어 파일을 바꾸거나 AgentStudio를 다시 열어도 유지됩니다. PDF/PowerPoint/DB Diagram 같은 비텍스트 Viewer에는 표시하지 않습니다.

## v5.381 NotebookLineBookmarkNavigation

- Notebook Code Cell의 **줄 번호 왼쪽 glyph margin**을 클릭하면 Visual Studio처럼 해당 코드 줄에 북마크를 찍거나 해제할 수 있습니다.
- 북마크는 파란 리본 마커로 표시되며 Notebook 상단에 `북마크 N`, `◀`, `▶`, `모두 해제` 탐색 컨트롤을 제공합니다.
- 위쪽 코드를 확인한 뒤 `▶`를 누르면 다음 북마크 줄로, `◀`를 누르면 이전 북마크 줄로 자동 스크롤하고 해당 코드 줄에 커서를 이동합니다.
- 북마크는 `프로젝트 + Notebook 파일` 단위로 브라우저 localStorage에 보존되어 다른 탭/페이지를 다녀오거나 AgentStudio를 다시 열어도 복원됩니다.
- Code Cell 삽입/삭제 시 기존 북마크의 Cell index를 자동 보정해 가능한 한 원래 코드 위치를 유지합니다.

## v5.380 CodexUsageSettingsPopover

- 오른쪽 Codex 영역의 `⚙` 설정 버튼을 누르면 ChatGPT 사용량 메뉴와 유사한 팝오버를 표시합니다.
- Codex app-server의 공식 `account/rateLimits/read` 결과를 사용해 `5시간`, `1주` 남은 사용량(%), 각 초기화 시각/날짜를 표시합니다.
- 설정 팝오버를 열 때 사용량을 강제 새로고침하고, 팝오버 내부의 `↻` 버튼으로도 즉시 다시 조회할 수 있습니다.
- 사용 가능한 Rate Limit Reset Credit이 있으면 `재설정 N회 가능` 항목을 함께 표시합니다.
- 기존 CLI/PID/프로젝트/현재 파일 정보는 `Codex 상세 정보`에 접어서 유지하고, `Codex 설정`에서 시스템 설정 화면으로 이동할 수 있습니다.

## v5.379 NotebookCaretPersistenceManualPairTyping

- Notebook Code Cell을 controlled Monaco `value` 재주입 방식에서 안정적인 cell model 유지 방식으로 변경해 입력/삭제/붙여넣기 후 커서가 마지막 줄로 이동하는 현상을 방지합니다.
- Notebook 변경 시 전역 source-editor ref를 강제로 다시 focus하지 않도록 분리해 현재 Cell의 focus/caret를 유지합니다.
- Code Cell과 일반 Source Editor에서 `(`, `"`, `'`, `[`, `{` 입력 시 닫는 괄호/따옴표를 자동 삽입하지 않는 수동 입력 모드를 적용합니다. 예: `print(` 입력은 `print(` 그대로 유지합니다.
- Notebook 외부 Reload/Agent 수정은 사용자가 Cell을 편집 중일 때 caret를 건드리지 않고 blur 이후 안전하게 동기화합니다.
- 붙여넣기/중간 삭제/중간 문자열 삽입 시 Monaco 자체 selection/caret를 유지하여 연속 코딩이 가능하도록 합니다.

## v5.378 PdfMultiExtractorSearchNotebookRuntimeIsolation

- PDF 통합 찾기는 pypdf layout/plain과 PyMuPDF sorted text를 함께 사용해 텍스트 레이어 순서/분절 차이를 보정합니다.
- 공백/줄바꿈/zero-width뿐 아니라 PDF 내부의 구두점/기호 분절까지 fallback 검색하며 같은 페이지의 중복 결과를 통합합니다.
- 새 PDF 검색을 시작하면 이전 선택 위치를 즉시 해제하고 request sequence로 오래된 비동기 응답이 최신 결과를 덮어쓰지 못하게 합니다.
- Notebook 실행 Context는 검색/탭 상태가 아니라 Notebook이 열린 projectRoot와 파일 경로에 고정합니다.
- Notebook Python runtime session은 터미널 탭과 분리해 Notebook 파일별로 유지하며, 프로젝트 venv Python이 변경되면 stale worker를 자동 폐기하고 새 interpreter로 재바인딩합니다.


## v5.377 ExecutionStopErdRoutingEnvExampleOnly

- Agent 개발 완료/실패/취소 후 상단 `실행 정지` 버튼 상태를 즉시 해제합니다.
- DB ERD 관계선을 table obstacle을 피해 전용 lane/corridor로 라우팅하여 겹침과 table 관통을 줄입니다.
- 생성 Agent의 `SYSTEM_ADMIN.cmd`는 `.env`를 생성/수정하지 않으며, 필수 설정 가이드는 `.env.example`에만 예시와 함께 기록합니다.

## v5.376 GpuAccelerationRecommendationControl

- Ollama 로컬 LLM 전용, 로컬 Embedding 모델, 이미지/영상 AI Agent 작업에서 GPU가 정지 상태이면 설계 검토/개발 시작 전에 GPU 사용 권장 확인을 표시합니다.
- 확인을 누르면 AgentStudio GPU 가속을 활성화하고, AgentStudio가 관리 중인 Ollama는 안전하게 재시작한 뒤 작업을 계속합니다.
- 설정 화면에 GPU 시작/정지/상태 새로고침을 추가했습니다. GPU 정지는 물리 GPU 전원을 끄는 것이 아니라 AgentStudio 관리 작업을 CPU 모드로 전환합니다.
- 생성 Agent 테스트 명령에도 GPU 모드 환경을 전달해 GPU 정지 상태에서는 CUDA/ROCm 장치를 숨깁니다.

## v5.375 PdfWhitespaceInsensitiveSearchFix

- PDF 통합 찾기에서 화면상 띄어쓰기와 PDF 텍스트 레이어의 띄어쓰기가 달라도 검색합니다.
- 예: `데이터조작어` ↔ `데이터 조작어`, 줄바꿈으로 분리된 어절도 같은 검색어로 찾습니다.
- Unicode NFKC 및 zero-width 문자 정규화를 적용하고 페이지 이동/중복 제거는 v5.374 규칙을 유지합니다.


## v5.374 PdfSearchDedupPageNavigationFix

PDF 통합 찾기의 검색 결과 중복과 잘못된 페이지 이동을 보정했습니다. PDF 텍스트 레이어에서 동일한 문자열이 중복 추출되는 경우 같은 페이지의 동일 결과를 하나로 합치고, 결과 목록에는 주변 문맥을 함께 표시해 반복되는 제목도 구분하기 쉽게 했습니다. PDF 추출 텍스트의 line/column은 실제 화면 좌표가 아니므로 결과 위치는 실제 PDF 페이지를 기준으로 표시합니다. 결과 클릭 시 Chromium PDF Viewer에 `#search`를 함께 전달하지 않고 `#page`만 전달하여, 내장 PDF 검색이 페이지 이동을 덮어써 모든 결과가 같은 위치로 가는 문제를 방지합니다.

## v5.373 PdfUnifiedFindSupport

- 코드 편집기의 통합 `찾기`가 현재 PDF에서도 동작합니다.
- PDF 텍스트는 Backend `pypdf`로 페이지별 추출하여 현재 파일 검색 결과에 표시합니다.
- 검색 결과에는 `페이지 N · Lx:Cy` 위치와 문맥 snippet을 표시합니다.
- PDF 검색 결과를 클릭하면 브라우저 PDF Viewer를 해당 페이지로 이동시키고 검색어 fragment도 전달합니다.
- 프로젝트 전체 텍스트 검색에서는 성능 보호를 위해 PDF를 자동 전수검색하지 않습니다. PDF는 현재 파일 범위에서 명시적으로 검색합니다.
- 이미지로만 구성되어 텍스트를 추출할 수 없는 PDF는 OCR 필요 가능성을 안내합니다.
- v5.372 Ctrl+S Notebook Save Root Fix 및 이전 기능을 모두 포함합니다.


- `Ctrl+S`가 상단 프로젝트 선택값(`root`)에 의존하던 문제를 제거했습니다.
- 프로젝트 파일 트리에서 연 Notebook/소스/SQL 파일은 `editorFileRoot → fileTreeRoot → workspaceRoot → terminalRoot`를 기준으로 저장합니다.
- Notebook Cell 수정 직후 바로 `Ctrl+S`를 눌러도 마지막 입력이 누락되지 않도록 현재 편집 내용을 Ref에 즉시 미러링합니다.
- `Ctrl+Shift+S` 역시 상단 프로젝트 선택이 비어 있어도 열린 수정 파일을 저장할 수 있습니다.
- 저장 완료 시 터미널에 `[저장 완료 · Ctrl+S]` 로그를 남기고 Dirty 표시를 해제합니다.
- 브라우저의 기본 `웹페이지 저장` 동작은 기존처럼 차단합니다.

---

## v5.371 GlobalCommandPaletteAgentWorkCenterHelpNotebookRootFix

- 상단 `⌕ 명령어 검색...`을 실제 전역 Command Palette로 연결하고 `Ctrl + K`, ↑/↓, Enter, Esc 키보드 탐색을 지원합니다.
- 프로젝트/워크스페이스/찾기/PPT/DB ERD/UI Layout/재개발/MCP/시스템/도움말 등 20개 이상의 명령을 즉시 검색·실행할 수 있습니다.
- 상단 `♢` 버튼을 Agent 작업 센터로 연결해 현재/최근/실패 Background Job, 개발 진행률, Workflow 진행률, 실패 Checkpoint 및 `재개발 시작`을 한 곳에서 확인합니다.
- 상단 `?` 버튼을 검색 가능한 AgentStudio Help Center로 연결해 탭별 사용법, 첨부파일, 재개발, PPT/ERD, 단축키, Notebook 실행 방법을 안내합니다.
- 프로젝트 선택이 비어 있어도 프로젝트 파일 트리에서 연 Notebook/Python/CMD 파일은 `editorFileRoot → fileTreeRoot → workspaceRoot → terminalRoot` 우선순위로 실행 Root를 자동 해석합니다.
- Notebook 셀 실행 시 `Notebook을 실행할 프로젝트 경로가 없습니다.`가 잘못 뜨던 Workspace Root 바인딩 문제를 수정했습니다.

---

## v5.370 GlobalMinimumReadableTextSize

- AgentStudio 전체 UI의 명시적 텍스트 크기 하한을 13px로 통일했습니다.
- 사용자가 지정한 `DB 실시간 설계 · 초안`의 안내 문구 크기를 최소 가독성 기준으로 사용합니다.
- 기존 5~12px 텍스트 스타일은 13px로 상향합니다.
- 버튼, 탭, 상태표시, 프로젝트 목록, 경로, 로그, 터미널, 분석 태그, 배지 등 작은 텍스트도 같은 하한을 적용합니다.
- DB ERD SVG의 관계명, Schema, 컬럼명, PK/FK 배지, 데이터 타입 역시 13px 이상으로 조정합니다.
- 화면 공간이 부족한 경우 글자를 작게 줄이는 대신 기존 스크롤/줄바꿈/ellipsis 레이아웃을 사용합니다.
- 신규 Contract Validator가 CSS/SVG에 13px 미만의 명시적 텍스트 크기가 다시 들어오는 것을 차단합니다.

## v5.370 FailedBuildRedevelopmentCheckpoint

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

## v5.370 ReactTypeScriptLegacySourceCleanupFix

### v5.370 changes

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


## v5.370 Failed Build Resume Checkpoint
- 신규 Agent 개발 실패 후 요구사항/대화/Workflow/UI Layout/첨부 분석 요약/실패 실행 정보를 프로젝트 `reports/agentstudio_design_checkpoint.json`에 영속 저장합니다.
- 브라우저 localStorage와 프로젝트 Checkpoint를 함께 조회하고 더 최신 기록을 사용자 승인 후 복원합니다.
- v5.367 이하 프로젝트도 `reports/requirements_snapshot.json`, `workflow_state.json`, `current_run.json`을 사용해 가능한 범위에서 복원합니다.
- 이전 실패 Workflow State와 실패 원인을 다음 Agent Factory 실행의 `previous_build_state`/`resume_context`로 전달합니다.
- 신규 Agent 시작은 기존처럼 완전 격리되며, 같은 프로젝트 경로를 다시 선택했을 때만 이전 기록 후보를 제시합니다.
