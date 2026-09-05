# THEANOVA AgentStudio

## Current baseline: v5.602

v5.600의 계정/프로젝트 설정 DB와 수정 이력 구조를 유지하면서, 이력 SQL 임시 파일, Workflow 명시 저장/복원, 변경 없는 저장 차단, 기존 프로젝트 Prompt/Tool Source 동기화와 `신규/변경/동일` 표시를 추가했습니다. DB 비밀번호 같은 민감정보는 DB에 평문 저장하지 않고 기존 Windows DPAPI 보관 방식을 유지합니다.
See `README_V5_601_HistorySqlWorkflowPromptToolSync.md`.

## Current distribution baseline

- v5.602 HistoryListSqlSchemaQualifiedDbBindingSemanticQwenDynamicModel
- v5.601 HistorySqlWorkflowSaveExistingPromptToolSyncNoopSave
- v5.600 ProjectHistoryStrictTypeSafetyBuildFix
- v5.599 AccountProjectSettingsDbHistory
- v5.598 RagStudioIntegrationUxFix
- v5.597 RagLegacyPkPreCreateMigrationFix
- v5.596 TablePkUiBuildFix
- v5.595 TableSpecificPrimaryKeyNamingPolicy
- v5.594 RagStudioPhase6OperationSecurityEvaluation


## Current baseline
- v5.519 RagChunkingCodingStyle: RAG chunking strategy selection, provenance, evaluation, semantic-chunking guard, safe empty retrieval rules

- v5.516 InPlaceFeatureCleanupFix

- v5.517 SharedLayersAndKoreanFilenameRestore: 한글 파일명 복원 + stores/types/utils/common components 공통 계층 분리

- v5.518 CodexAndLiveTranscriptPanelFix: Codex selector visibility + narrow-panel live Transcript layout/scroll fix

- v5.520: RAG Document Type Detection + Chunk Strategy Routing coding-style baseline.

- v5.521: RAG document-type-aware Chunking Standard, validation, incremental reindex/versioning, retrieval evaluation, and shared chunking engine.

- v5.522: Capability/LLM recommendation labels keep the English technical name and append a short Korean explanation for user readability.
- v5.523: Request Analyzer와 RAG Query Analyzer/Query Rewrite를 분리하고 Search Plan·Search Type·Conversation Rewrite·Permission Filter·Multi-hop 규칙을 Coding Style과 UI 설명에 반영했습니다.
- v5.524: RAG Metadata Filter 표준을 반영해 Hard/Soft 분리, Canonical Normalization, Neutral Filter Schema, Security/Permission 분리, Fail-Closed, Filter Relaxation, Filter Source Lock, Metadata Schema/Version 규칙을 추가했습니다.
- v5.525: RAG Hybrid Search 표준을 Coding Style에 반영해 Vector/BM25 역할 분리, Search Strategy Router, RRF Fusion, Deduplicate Trace, Reranker, 한국어 BM25 Tokenizer, Search Debug, Retrieval Preset/평가 규칙을 추가했습니다.
- v5.526: RAG 후보 문서 결과 UI 표준을 Coding Style에 반영해 문서 단위 그룹, Final Context/Candidate 분리, 일반/Debug UI 분리, 검색 근거, Pipeline Summary, 문서 다양성, Near Duplicate, 원문 위치 열기, Result View Filter 규칙을 추가했습니다.
- v5.527: Structured Chat Response 및 Dynamic Renderer 설계 표준을 Coding Style에 반영해 Response Planner, Response Schema Registry, Renderer Registry, Presentation Resolver, Source/Action Validation, Streaming Event, History JSON, Creator/Editor 응답 설계 규칙을 추가했습니다.
- v5.528: 첨부 파일 AI 정리 패널의 상단 높이 조절 방향을 수정했습니다. 위로 드래그하면 패널이 커지고 아래로 드래그하면 작아지며, 키보드 ArrowUp/ArrowDown 동작도 동일한 방향으로 맞췄습니다.
- v5.529: 요구사항 수집 현황의 완료/미수집 항목을 클릭해 중앙 AI 질문과 추천 선택 카드 또는 직접 텍스트 입력으로 최신 요구사항을 적용하는 Interactive Requirement Editor를 추가했습니다.
- v5.530: 요구사항 추천 선택 카드를 AI 질문 메시지 자체에 저장·렌더링하여 텍스트만 보이고 추천 항목이 사라지는 문제를 수정했습니다.
- v5.531: 실행 환경 Frontend에서 React + Vite의 TypeScript/JavaScript를 구분하고, 명시적으로 설정된 Frontend/Backend를 요구사항 수집 현황의 UI Framework/Backend 완료 상태와 동기화했습니다.
- v5.532: 요구사항 수집 현황을 전체 설계 Navigation Hub로 개선했습니다. UI/Backend/실행 환경, Tool/Prompt, Database, Layout은 기존 전용 폼으로 이동하고 나머지 항목은 공통 Requirement Editor에서 추천 선택 또는 직접 입력으로 수정합니다.
- v5.533: 요구사항 항목 클릭 시 실제 Workspace 우측 패널의 탭 전환 후 스크롤 위치가 남아 설정 폼이 보이지 않던 문제를 수정했습니다. 공통 편집기는 목록 위에 즉시 표시하고, 기존 전용 폼은 우측 패널을 상단으로 이동한 뒤 대상 카드를 강조합니다.
- v5.534: Tool / Prompt를 Agent Logic / Tool 구성으로 확장하고 Prompt Registry·Tool Registry를 Workflow Node와 연결했습니다. 요구사항 분석에서 선택된 추천 Tool은 기본 자동 적용되며 Workflow/코드 생성 Context에 Prompt/Tool 바인딩을 전달합니다.
- v5.535: Database Provider 사용 체크가 즉시 되돌아가는 문제를 수정했습니다. 현재 `enabled` 값을 Source of Truth로 사용하고 legacy `use_in_agent`를 동기화하여 PostgreSQL/Firestore/Redis 체크 상태가 정상 유지됩니다.
- v5.536: 실행 환경이 실제로 설정/확정되어 있는데 요구사항 수집 현황에서 미수집으로 표시되던 문제를 수정했습니다. Runtime Setup의 기술/PORT/USER_FIXED/approved 상태를 요구사항 `실행 환경`과 동기화합니다.
- v5.537: Firestore Service Account JSON 파일 찾기/자동 등록을 추가하고, localhost Redis에서 TLS로 인한 Timeout 발생 시 비TLS 안전 재시도 후 성공하면 TLS를 자동 해제하도록 개선했습니다.
- v5.538: 새 ZIP/PC에서 root `.env`의 비밀값이 아닌 Runtime bootstrap 설정이 빠져도 SYSTEM_ADMIN이 안전 기본값(Backend 8000, Frontend 5173, Ollama auto-start)을 자동 보완합니다. 기존 `.env` 값은 절대 덮어쓰지 않으며 DB/API 비밀값은 자동 생성하지 않습니다.
- v5.539: 프로젝트 전환 시 다른 프로젝트의 설계 Snapshot/Design Project ID/경로가 섞여 저장되는 것을 차단했습니다. 프로젝트 DB의 실제 project_root를 복원·자동저장 Source of Truth로 사용하고, 경로가 다른 Snapshot은 복원하지 않으며 Backend도 기존 Agent Design Project의 경로 변경 저장을 409로 차단합니다.
- v5.540: Firestore 연결 테스트가 예약된 Document ID `__probe__`를 사용해 HTTP 400으로 실패하던 문제를 수정했습니다. 비예약 ID `connection_probe`를 사용하는 read-only GET으로 교체해 유효한 Service Account 연결이 정상 판정됩니다.
- v5.541: Workflow 실행 현황을 움직이는 Node/Connector/Pulse/Elapsed/Loop 중심 Live View로 개선하고, 3D·Blender가 현재 요구사항에 명시적으로 포함된 경우에만 Blender 3D Workflow 카드를 표시하도록 Capability Gate를 추가했습니다.
- v5.542: v5.541 Workflow Live Motion의 Blender Capability 판정 코드가 `requirementManualOverrides` 선언 전에 실행되어 발생한 TypeScript TS2448/TS2454 빌드 오류를 수정했습니다. Capability Gate 동작은 유지하면서 해당 계산을 state 선언 이후로 이동했습니다.
- v5.543: App.tsx 2차 구조 분리 1단계. SystemPage의 State/Ref/Effect/Handler/API/UI 소유권을 `features/system/SystemPage.tsx`로 이전하고 App route shell을 `app/AppShell.tsx`로 분리했습니다. TopBar Brand/Version도 `components/layout/StudioBrand.tsx`로 이동했습니다. App.tsx 23,524줄 → 22,328줄.
- v5.544: Workspace Shell/Tab 소유권 분리. Workspace Layout State/Ref/Effect/Resize Handler를 Feature Hook으로 이전하고 10개 Tab Registry/Shell/Tabs를 `features/workspace`로 이동했습니다. v5.543 미완료 System API orchestration도 `features/system/services/systemService.ts`로 분리했습니다. App.tsx 22,328 → 22,160 lines.
- v5.545: v5.544 WorkspaceShell TypeScript TS18048 빌드 오류를 수정했습니다. workspaceTabDefinition이 항상 WorkspaceTabDefinition을 반환하도록 명시적 fallback object를 사용하고 Shell에서도 compactResult를 안전하게 Boolean 정규화합니다. DB 인증 오류는 코드 회귀가 아니라 별도 환경 설정 문제이므로 자동 변경하지 않습니다.
- v5.546: Terminal Controller 실제 소유권 분리. terminalSessions/connection/error/completion state, WebSocket refs 및 reconnect timers, xterm refs, command buffers/history/cursor/prompt, resize/fit, socket send/close lifecycle을 `features/terminal/hooks/useTerminalController.ts`로 이전하고 Socket URL/생성을 service로 분리했습니다. App.tsx 22,160 → 22,076 lines.
- v5.547: v5.546 Terminal Controller 분리 후 발생한 TS2345를 수정했습니다. `sendSocketMessage()`의 payload를 `LegacyRecord`가 아니라 실제 `TerminalClientMessage` union type으로 제한하여 serializer 계약과 일치시켰습니다. Terminal Controller 분리 구조와 reconnect/xterm ownership은 그대로 유지됩니다.
- v5.548: v5.547 TerminalClientMessage import 경로 오류(TS2459)를 수정했습니다. `TerminalClientMessage`는 `utils/terminal.ts`가 아닌 실제 정의 소스인 `types/terminal.ts`에서 type-only import하도록 변경했습니다. Terminal Controller 구조는 유지됩니다.
- v5.549: Project + Editor Controller 분리. Project Search/Filter/Load lifecycle 상태를 Project Feature로, Editor code/focus/file-root/search/bookmark/scroll/selection 상태를 Editor Feature로 이전하고 실제 파일 read/write API를 Editor File Service로 이동했습니다. App.tsx 22,076 → 22,052 lines.
- v5.550: Database + Workflow State/Service 분리. SQL connection/query/object/database-preview State/API/Handler를 Database Controller/Service로, Workflow preview/progress/recovery State와 progress clock Effect, definition/provider Handler/API를 Workflow Controller/Service로 이전했습니다. App.tsx 22,052 → 21,834 lines.
- v5.551: v5.550 Database/Workflow 분리 중 실수로 함께 제거된 Agent Development bridge state(`developmentProgress`, `developmentFinalStatus`, `builderMessagesEndRef`)를 복원하고 Database Controller의 strict TS7006를 수정했습니다. Database/Workflow Controller/Service 분리 구조는 유지됩니다.
- v5.552: Agent Builder / Agent Development / External Project / Codex 잔여 분리 1단계. 요구사항/인터뷰 설계 상태, 개발/재개발 상태, 외부 프로젝트 분석 상태/API, Codex 코드 제안 Handler를 각 Feature Hook/Service로 이전했습니다. App.tsx 21,845 → 21,794 lines.
- v5.553: 설계 검토/개발 시작 진행 화면에 사용자 가시성 패널을 추가했습니다. 현재 Stage/요청 내용, 확정 요구사항, Workflow/DB 정리 결과, 실제 Backend 개발 이벤트를 아이콘·진행 애니메이션과 함께 표시하며 AI 내부 사고 과정은 표시하지 않습니다. App.tsx 21,794 → 21,820 lines.
- v5.554: SYSTEM_ADMIN Backend Health Check 조기 실패 수정. 실제 Backend가 30초 이후 정상 기동되는 환경을 위해 FastAPI startup 대기를 30초에서 최대 90초로 늘리고 15초마다 초기화 진행 상태와 마지막 Health 오류를 로그에 남깁니다. v5.553 진행 가시성 UI는 그대로 유지됩니다.
- v5.555: Windows SYSTEM_ADMIN의 localhost Health Check가 프록시/WinHTTP 경로에 가로채져 실제 Backend가 아닌 응답을 읽을 수 있는 문제를 수정했습니다. 127.0.0.1 Health/DB Health는 Proxy=null 직접 연결로 검증하고 THEANOVA AgentStudio 응답인지 확인하며, Backend 포트의 실제 Listen PID/Command를 진단 로그에 기록합니다.
- v5.556: 프로젝트 로드 시 이전/혼합 Workflow의 `three_d_agent_plan`만으로 3D 제작 Agent · Blender MCP 카드가 활성화되던 문제를 수정했습니다. Blender UI는 현재 프로젝트의 명시적 3D/Blender 요구사항 또는 사용자가 직접 선택한 Blender 전문 유형에서만 표시됩니다.
- v5.557: Blender 3D Workflow 카드를 Agent Builder 전용 Component로 분리하고, 설계 검토 전에 승인된 DB Resource Plan이 있으면 Workflow 생성 후 DB 설계를 자동 확정하여 동일 내용을 다시 승인하라고 요구하지 않도록 수정했습니다.
- v5.558: Workflow 탭의 좌측 패널을 프로젝트 목록 대신 Agent 설계와 동일한 `신규 Agent 설계` 요구사항 요약 패널로 변경했습니다. Workflow를 보면서 목적/기능/MCP·Tool/DB/UI/실행환경/개발계획 등 현재 설계 Context를 계속 확인할 수 있습니다.
- v5.559: 코드 편집 > 메모 > 실시간 기록의 Transcript 세로 높이를 크게 확장하고, 메모 우측 패널 전체가 세로 스크롤되도록 변경했습니다. 하단 Transcript 작업 버튼/요약/저장경로/상태가 화면 아래에서 가려지지 않도록 bottom 여백도 추가했습니다.
- v5.560: 실시간 Transcript 버튼 순서를 `파일 저장 → 요약정리 → 요약 파일 저장`으로 변경했습니다. AI Provider가 빈 응답/호출 실패를 반환하면 `logs/media_stt_summary.log`에 진단을 남기고 Transcript 원문 기반 로컬 안전 요약으로 자동 대체합니다. 실제 실패 시 UI에 오류 로그 전체 경로를 표시합니다.
- v5.561: Agent 설계 프로젝트 자동 저장 범위를 수정했습니다. 이제 document 전체 클릭/키 입력이 아니라 `에이전트 설계` 탭 내부의 버튼 클릭, 값/옵션 변경, 입력 작업에만 자동 저장이 반응합니다. 코드 편집, Notebook, 메모, Workflow, DB 등 다른 Workspace 작업은 Agent 설계 저장을 발생시키지 않습니다.
- v5.562: Ollama/LangChain 응답 정규화 및 빈 응답 1회 재시도, AI Provider 경고와 성공 요약 분리, Transcript 요약 결과를 실시간 기록 하단의 독립 영역으로 이동했습니다.
- v5.563: Notebook 타이핑 성능을 최적화했습니다. 셀 입력마다 전체 ipynb를 structuredClone/JSON.stringify하고 App 상태를 갱신하던 경로를 제거하고, Monaco 로컬 버퍼를 즉시 사용하며 420ms idle/blur/Ctrl+S 시점에만 전체 Notebook을 직렬화합니다. Ctrl+S는 debounce 대기 중인 최신 셀 내용도 즉시 저장합니다.
- v5.564: Notebook 연속 타이핑 중 전체 ipynb 직렬화를 900ms idle + requestIdleCallback으로 더 늦춰 입력 부하를 줄였습니다. 프로젝트별 코드 편집 열린 파일/활성 탭/Pin 탭도 저장하고 프로젝트 재로드 뒤 자동 복원합니다.
- v5.565: Notebook 외 일반 키 입력 지연을 줄이기 위해 LLM 대화형 코드 편집 Prompt를 App 전역 State에서 분리해 React.memo 로컬 Component로 이전했습니다. 또한 6천개 이상 프로젝트 파일 트리를 매 App render마다 재구성/정렬하던 경로를 useMemo로 캐시하고 파일 검색은 useDeferredValue로 지연 처리합니다.
- v5.566: Agent 설계 자동 저장을 완전히 제거했습니다. pointer/keydown 저장, 350ms/800ms debounce 저장, Requirement Draft/Checkpoint 자동 저장, 기능 변경 전 자동 Snapshot을 제거하고 Toolbar의 `지금 저장` 수동 저장만 유지합니다.
- v5.567: v5.566 자동 저장 제거 후 restoreRequirementDraft에 남아 있던 잔여 checkpoint 호출을 제거해 Windows TypeScript 빌드 오류 TS2304를 수정했습니다. 기존 Draft 복원은 LocalStorage 마이그레이션만 수행하고 Backend checkpoint를 자동 저장하지 않습니다.
- v5.568: Agent 설계 Tool/Prompt의 Prompt Registry에서 기본 Prompt, AI 추천, 사용자 정의를 각각 독립적으로 표시·편집할 수 있습니다. AI 추천 모드에는 Agent 요구사항 Context를 사용한 추천 Prompt 생성 버튼을 추가했고, 선택된 모드의 실제 Prompt가 Workflow/코드 생성 Context에 전달됩니다.
- v5.569: Prompt Registry AI 추천 오류의 원인이었던 존재하지 않는 `LLMTask.ANALYSIS`를 `LLMTask.REQUIREMENTS_ANALYSIS`로 수정했습니다. Prompt Registry는 처음에는 간단한 목록으로 표시하고 각 항목의 `수정`을 눌렀을 때만 기본/AI 추천/사용자 정의 Prompt 편집폼이 열리도록 UI를 정리했습니다.
- v5.570: 완료 Agent/Studio PPT 다운로드의 HTTP 422 null payload 문제를 수정했습니다. 선택적 object 필드를 null-safe하게 정규화하고 Agent 전체/Workflow/실행결과/분석리포트/아키텍처/DB ERD 및 Studio 전체 PPT 7개 조합을 실제 PPTX 생성으로 검증합니다.
- v5.571: 모든 Agent/Studio PPT 다운로드가 파일 저장 완료 후 해당 PPT/PPTX를 OS 기본 PowerPoint/프레젠테이션 앱으로 자동 실행합니다. 자동 열기 실패 시 저장 성공은 유지하고 저장 경로와 열기 오류만 별도로 안내합니다.
- v5.572: Workspace 탭 순서를 `에이전트 설계 → 워크플로우 → 실행 결과 → 코드 편집`으로 변경했습니다. 실행 결과 탭의 좌측도 프로젝트 목록 대신 `신규 Agent 설계` Context 패널을 사용합니다.
- v5.573: 메인페이지에 Hugging Face AI Trends Feature를 분리 구조로 추가하고 `Asia/Seoul` 기준 일 단위 수집 Cache를 적용했습니다. 오늘 이미 수집한 데이터가 있으면 재수집하지 않고 그대로 표시하며, 오늘 데이터가 없을 때만 최근 7일 Models/Papers/News/Spaces/Datasets를 수집합니다.
- v5.574: 녹음 중 임시 STT와 녹음 종료 후 정밀 STT를 분리하고, 분석용 Transcript에서 시간 문자열을 제거하며, 이전 녹음 기록/요약 재열람 구조를 추가했습니다.
- v5.575: Hugging Face AI Trends 수집 결과를 한국어 자동 번역하고 번역 완료 결과만 일일 캐시에 저장하도록 개선했습니다.
- v5.576: Hugging Face의 실제 상위 모델/논문/뉴스/Spaces와 현재 사용 모델 관련 Dataset 표시 기준을 강화했습니다.
- v5.577: 인기 모델 설명 + 최신 논문 + AI 뉴스를 한 번의 한국어 번역 배치로 묶고, Spaces/Datasets는 두 번째 배치로 처리합니다. OpenAI/Codex를 우선 사용하고 번역 결과를 일일 캐시에 저장합니다.

## v5.581
- Prompt & Tool Studio `service.ts`의 공통 `src/api.ts` 상대경로 오류(`TS2307`)를 수정했습니다.


## v5.582
- Agent 설계 중앙 영역의 2개 상위 탭을 전용 grid row로 고정해 인터뷰 탭이 아래로 밀리던 레이아웃을 수정했습니다.
- Prompt & Tool Studio는 중앙 전체 세로 스크롤을 사용하도록 변경해 AI 추천, Response Plan/Preview 및 하단 작업 버튼까지 끝까지 확인할 수 있습니다.
- Studio Header/Input 탭은 전체 스크롤 중에도 접근할 수 있도록 sticky 처리하고 하단 상태바에 가려지지 않도록 여백을 추가했습니다.

## v5.583
- Prompt & Tool Studio 프로젝트 영구 저장 연동: Studio 설정을 Agent Design Project snapshot의 `prompt_tool_studio`에 포함하고 수동 저장/불러오기 시 복원합니다.
- Studio의 USER 확정/변경 State를 기존 Agent 설계 요구사항에 명시적으로 적용할 수 있는 `Agent 설계에 적용` 동작을 추가했습니다.
- Test 탭을 INPUT/EXTRACTION/VALIDATION/ROUTING/TOOL/PROMPT/FULL로 확장했습니다. PROMPT/FULL은 현재 AgentStudio의 실제 LLM Router를 호출하고 Runtime Trace를 반환합니다.
- TOOL 테스트는 임의 사용자 코드를 실행하지 않고 Tool Registry와 Routing target 계약을 검증합니다.
- 이미지/비디오 Agent 유형별 Prompt Template과 Negative Prompt 구조를 추가했습니다.
- Prompt/Tool version history를 프로젝트 snapshot에 보존합니다.


## v5.584 Prompt & Tool Studio Runtime Registry / Trace / Restore
- Prompt & Tool Studio Tool 탭에서 실제 AgentStudio MCP Registry 조회 및 명시적 동기화, Registry Tool 가져오기를 지원합니다.
- MCP Tool은 registry id/server id/risk/confirmation/runtime status를 Studio Tool Snapshot에 연결합니다.
- TOOL/FULL Runtime Test는 실제 DB Tool Registry와 Studio Routing Target을 교차 검증합니다.
- Runtime Test Trace는 ROUTING/TOOL_REGISTRY/TOOL_CONTRACT/PROMPT_COMPILE/LLM_RUNTIME 단계별 상태와 소요시간을 기록합니다.
- Prompt Version과 Tool Version 복원을 지원하고, Input 상세 분석에서 State Before/After History를 표시합니다.
- 임의 Python/source text를 자동 실행하지 않습니다. MCP Registry 동기화는 사용자가 버튼을 눌렀을 때만 수행합니다.

## v5.585 Prompt & Tool Studio Runtime Executor / LangGraph / Trace / Versioning
- 실제 MCP Registry Tool의 명시적 실행 테스트(`TOOL_EXECUTE`, `FULL_EXECUTE`) 추가
- Tool JSON Schema validation, confirmation gate, retry/timeout 적용
- Studio Routing Rule의 LangGraph 실제 compile 검증 및 Routing Visual Graph 추가
- Routing Version / Agent State Snapshot 저장·복원 추가
- Runtime Trace에 Tool 실행, LangGraph, Prompt/LLM 단계 Raw 결과와 소요시간 표시

## v5.586 Prompt & Tool Studio Unified Executor / Execution Trace / Diff / Reports

- MCP/API/Database/Python Tool 테스트를 하나의 명시적 Unified Executor 흐름으로 통합했습니다.
- Database Tool은 SQL Preview 후 읽기 전용 SELECT/WITH/EXPLAIN/SHOW 한 문장만 실제 실행합니다.
- Python Tool은 현재 Agent 프로젝트 경로를 사용해 AgentStudio의 격리 Python Worker에서 실행하며 확인 정책을 적용합니다.
- API Tool은 Source JSON의 method/url/headers/query/body 계약을 사용하며 쓰기 method는 확인 정책을 적용합니다.
- Studio Routing은 LangGraph StateGraph compile뿐 아니라 test runtime에서 실제 `ainvoke`하여 target/state를 trace에 기록합니다.
- LLM Runtime trace에 모델명과 provider가 제공한 token usage를 기록합니다. 가격표를 추측하지 않으므로 cost는 계산하지 않습니다.
- Studio 전체 Snapshot 버전 저장/복원, 마지막 버전 대비 변경 항목 Diff, Full Test Report 프로젝트 저장을 추가했습니다.



## v5.590 RAG Studio Phase 3 Retrieval
- v5.589 Indexing 결과를 실제 검색하는 Vector / Keyword / Hybrid Retrieval을 추가했습니다.
- Vector Search는 현재 Embedding Provider/Model과 일치하는 pgvector Embedding을 cosine HNSW 경로로 검색하며 Similarity Threshold를 적용합니다.
- Keyword Search는 Chunk content/heading/symbol/path/filename을 검색하고 기본 Keyword Score를 계산합니다.
- Hybrid Search는 Vector/Keyword 후보를 기본 RRF K=60으로 결합합니다.
- Top K와 Collection/Source/Document Type/Language/Path Metadata Filter 기본형을 제공합니다.
- Test 탭에서 질문 → 검색 → Retrieved Chunk 본문/Score/Source를 직접 확인할 수 있습니다.
- 검색 이력은 `rag_search_logs`에 저장하며 프로젝트별 Retrieval 설정은 `rag_retrieval_settings`에 저장합니다. 신규 테이블 모두 자동 증가 Primary Key `id`를 포함합니다.

## v5.589 RAG Studio Phase 2 Indexing
- v5.588 1차 Knowledge Collection/Source 승인 흐름을 유지하면서 실제 Indexing 파이프라인을 추가했습니다.
- 문서 유형 자동 판별, Duplicate checksum 검사, Secret/Prompt Injection Safety Scan 및 마스킹을 적용합니다.
- Markdown/Python/SQL/Table/일반 문서별 자동 Chunking과 Source별 Chunk Preview를 제공합니다.
- AgentStudio 현재 Embedding Provider를 사용해 `rag_embeddings` pgvector에 저장하며, 1536 미만 Vector는 zero-padding하고 1536 초과는 자동 truncate하지 않습니다.
- Index Job이 cosine HNSW `ix_rag_embeddings_embedding_hnsw`를 생성하고 PostgreSQL `pg_indexes`에서 존재 여부까지 검증합니다.
- 신규 `rag_documents`, `rag_chunks`, `rag_embeddings`, `rag_index_jobs` 테이블은 모두 자동 증가 Primary Key `id`를 포함합니다.
- RAG Studio에서 Index Job 진행률, 문서/중복/Safety/Chunk/Embedding 수, HNSW PASS 여부를 확인할 수 있습니다.

## v5.588 RAG Studio Phase 1 Knowledge Skeleton
- Agent 설계 인터뷰 / Prompt & Tool Studio 옆에 RAG Studio 탭 추가
- Knowledge Collection CRUD, PostgreSQL + pgvector 연결 테스트, File/Folder/Source Code 등록
- Source Analyse → Review → Approve 흐름 및 1차 적합성/위험도/추천 Chunking 표시
- 신규 RAG DB 테이블은 모두 자동 증가 Primary Key `id` 필수
- RAG UI 및 공통 OptionHelp 텍스트 최소 13px

## v5.587 Prompt & Tool Studio Readability / Role Separation / Toolbar Polish

- Frontend의 13px 미만 고정 텍스트 크기를 모두 13px로 상향해 작은 글씨 가독성을 개선했습니다.
- 우측 `Agent Logic / Tool 구성`을 `Agent 실행 정책`으로 재정의했습니다. 상세 Prompt/Tool 편집은 중앙 `Prompt & Tool Studio`가 담당하고, 우측 패널은 Workflow 적용 정책과 Studio 연동 요약을 담당합니다.
- 기존 Prompt Registry / Tool Registry / 고급 Prompt 설정은 기능 회귀를 막기 위해 `세부 Registry / 기존 Agent 호환 설정` 접기 영역에 보존했습니다.
- 우측 패널에 Studio Prompt 규칙/Tool/Routing 요약과 `Studio 열기` 버튼을 추가했습니다.
- Prompt & Tool Studio 헤더의 `상세 분석`, `Studio 버전 저장`, `Agent 설계에 적용`, `AI 추천`을 가로형 Toolbar로 정리하고 적용 버튼을 Primary Action으로 강조했습니다.







## v5.602 History List SQL / Schema-qualified SQL / DB Binding Semantics / Dynamic Qwen Model

- 프로젝트 수정 이력의 SQL 버튼을 개별 리스트 아이템에서 제거하고, 목록 조회 영역에 하나의 `SQL` 버튼으로 통합했습니다. 현재 프로젝트/분류/limit 조건을 그대로 반영한 임시 SQL을 생성합니다.
- 수정 이력 목록/상세 SQL과 LLM 학습 센터 SQL 내보내기는 현재 Runtime PostgreSQL Schema를 명시한 `"schema"."table"` 형식을 사용합니다.
- 계정 DB Profile을 Agent 프로젝트에 적용할 때 PostgreSQL/Redis/Firestore를 각각 독립 binding key로 저장합니다. 처음 추가한 Provider는 `신규(CREATE)`, 동일 Provider의 실제 변경만 `변경(UPDATE)` 이력으로 기록합니다. v5.601의 legacy cross-provider UPDATE 이력은 audit 원문을 바꾸지 않고 화면에서 `신규` 의미로 보정합니다.
- 변경사항이 없는 Project/Account/Workflow/Prompt/Tool 저장은 기존 v5.601 no-op 저장 방지 정책을 유지합니다.
- Qwen 최신 권장 모델을 `qwen3.8:27b-mtp-q4_K_M`으로 변경했습니다. 기존 프로젝트의 qwen3.5 설정 및 QLoRA qwen3.5-4B 호환 경로는 유지합니다.
- 메인 AI Trends와 LLM 학습 센터는 동일한 project-aware Qwen resolver를 사용해 프로젝트 → 계정 → 현재 AgentStudio 설정/기본값 → 설치 모델 fallback 기준으로 실제 표시 모델을 동적으로 결정합니다. 프로젝트가 바뀌면 Dataset 카드도 해당 Qwen 모델로 다시 조회합니다.
- Qwen 정보는 provider/family/model/version/parameter/quantization/MTP/install 상태 구조로 전달하며, Frontend에 qwen3.8 문자열을 현재 사용 모델로 하드코딩하지 않습니다.

## v5.601 History SQL / Workflow Save / Existing Prompt·Tool Sync / No-op Save

- `이력 정보` 목록과 상세에 SQL 버튼을 추가했습니다. 선택한 이력은 프로젝트 `.agentstudio/sql_scratch/` 아래 임시 `.sql` 파일로 생성되며 자동 실행하지 않습니다.
- Workflow 탭 상단에 명시적 `저장` 버튼을 추가하고 `WORKFLOW/default` 프로젝트 설정으로 저장·복원합니다. 실제 Workflow 내용이 바뀌지 않으면 버튼은 `✓ 저장됨` 상태가 되고 DB 저장/이력을 추가하지 않습니다.
- Account DB Profile, 프로젝트 설정, Agent 설계 Snapshot/Version, Prompt/Tool/Routing/State/Test Report/Studio Version 저장 경로에 동일 내용 저장 방지 규칙을 적용했습니다. 프로젝트 이력도 동일한 연속 이벤트는 중복 Row를 만들지 않습니다.
- 기존 프로젝트 로드시 저장된 `PROMPT_TOOL_STUDIO/default` 설정과 현재 프로젝트 소스의 Prompt/Tool 정의를 함께 복원합니다. Prompt 변수, LangChain PromptTemplate, Python/MCP Tool decorator/registration 등을 제한된 Source Scan으로 감지합니다.
- 기존 소스와 동일하면 `동일`, 새 설계 Tool/Prompt가 아직 소스에 생성되지 않았으면 `신규`, 기존 Source fingerprint 또는 Studio 편집 내용이 달라지면 `변경`으로 표시합니다.
- v5.600의 Account/Project Settings 및 Project History DB 구조를 그대로 사용하며 신규 테이블은 추가하지 않습니다.

## v5.600 Project History Strict Type Safety Build Fix

- Windows SYSTEM_ADMIN의 실제 `npm run build`에서 `ProjectHistoryPanel.tsx(49,49) TS2532`가 발생하던 문제를 수정했다.
- `noUncheckedIndexedAccess: true` 환경에서 `next[0].id`를 직접 읽지 않고 `const firstItem = next[0]` 후 존재 여부를 확인한다.
- v5.599의 계정 DB Profile / 프로젝트별 설정 / 이력 정보 기능은 그대로 유지한다.
- 회귀 검증에서 `next[0].id` 같은 unsafe 첫 항목 접근 패턴을 금지한다.

## v5.599 Account / Project Settings DB + History
- 로그인 계정별 재사용 DB 연결 목록을 `account_database_profiles`에 저장합니다. 비밀번호/DPAPI blob/private key/token/API key는 DB JSON에 저장하지 않습니다.
- 프로젝트별 설정을 `account_project_settings`에 `member_id + project_key + setting_group + setting_key` 기준으로 분리 저장합니다.
- 코드 편집 > DB 연결은 현재 프로젝트에 저장된 연결이 없을 때 계정의 저장 DB 목록을 먼저 보여주고 선택한 연결을 프로젝트에 적용할 수 있습니다.
- Agent 설계 > Database와 RAG Studio > DB / Vector Store에도 계정 저장 DB 목록을 표시하고, 프로젝트별 선택/바인딩을 별도로 저장합니다.
- `지금 저장` 수동 저장 시 요구사항, Runtime, Database, DB Resource Plan, UI Layout, Tool/Prompt, 개발 Stage, 추천 설정, Coding Style 등 주요 설계 설정을 프로젝트별 정규 설정 Row로 동기화합니다. 기존 전체 Snapshot/Version 저장도 유지합니다.
- RAG Studio 오른쪽에 `이력 정보` 탭을 추가해 프로젝트 설정/RAG/DB 수정 이력을 시간순으로 조회하고 항목 클릭 시 변경 전/후 JSON 상세를 확인합니다.
- 신규 테이블 PK는 전역 규칙대로 `account_database_profiles_id`, `account_setting_profiles_id`, `account_project_settings_id`, `project_setting_histories_id`를 사용합니다.

## v5.598 RAG Studio Integration / UX Fix

- RAG Frontend API path의 중복 `/api/api/rag` 404를 `/api` base + `/rag/...` 구조로 수정
- 개발 단계 번호(2차/5차/6차)를 제품 UI에서 제거
- File/Folder Windows Native 경로 찾기 추가
- Source Code 붙여넣기 textarea 및 프로젝트 내부 보관 파일 생성 추가
- Embedding config 404로 인한 `불러오는 중...` 고정 문제 해결
- Operation / Security / Evaluation의 흰색 form/card 스타일을 dark theme으로 통일

## v5.597 Legacy RAG PK Pre-Create Migration Fix

- 기존 v5.588~v5.594 DB에서 `rag_sources.id` 같은 legacy PK가 남아 있어도 신규 RAG Operation 테이블의 FK 생성 전에 `sources_id`, `chunks_id` 등으로 먼저 Rename 합니다.
- local bootstrap, Runtime DB 재바인딩, Supabase schema initialize 모두 `Legacy PK Rename → create_all → full migration` 순서를 사용합니다.
- PostgreSQL `UndefinedColumn: sources_id` 때문에 startup이 중단되고 저장된 Runtime DB Provider 적용이 건너뛰어져 로그인 계정이 로컬 DB에서 검색되던 401 연쇄 문제를 차단합니다.
- Rename은 기존 데이터 삭제 없이 idempotent하게 수행되며 v5.595의 전역 `{logical_table_name}_id` 정책과 v5.596의 TSX literal build fix를 그대로 유지합니다.

## v5.595 Table-Specific Primary Key Naming Policy

- 모든 신규 DB 테이블의 기본 Primary Key는 단순 `id`가 아니라 테이블명 기반 `{logical_table_name}_id`를 사용합니다.
- 기술 접두어는 기본 PK명에서 제외합니다. 예: `rag_evaluation_cases` → `evaluation_cases_id`, `rag_chunks` → `chunks_id`, `app_users` → `users_id`.
- v5.588~v5.594에서 생성된 RAG 테이블의 기존 `id` PK는 시작 시 데이터 삭제 없이 새 컬럼명으로 자동 Rename migration 됩니다.
- RAG ORM의 Python 속성 `row.id`는 API/서비스 호환성을 위해 유지하되 실제 PostgreSQL 컬럼명은 테이블별 명시적 PK명을 사용합니다.
- Agent DB Module Designer도 Registry/LLM Custom Table 모두 동일 규칙을 적용하고 기존 `target.id` FK reference를 실제 생성된 PK명으로 자동 보정합니다.
- 프로젝트별 기술 접두어는 `common_policy.id_prefixes`로 추가 지정할 수 있습니다.


## v5.596 Table PK UI Build Fix

- Windows `SYSTEM_ADMIN.ps1` full frontend build failed in `AgentDatabaseSetup.tsx` with `TS2304: Cannot find name 'table_name'`.
- The UI help text intended to display the literal `{table_name}_id` was interpreted by TSX as a JavaScript expression.
- The literal is now rendered safely with `{'{table_name}_id'}` so the table-specific PK naming policy remains visible without creating an undefined identifier.
- v5.595 table-specific PK/FK naming behavior and RAG Studio phases 1–6 are otherwise unchanged.
- Verification adds a regression guard that rejects raw `{table_name}` JSX in the DB setup UI and runs the full frontend build when dependencies are installed.
