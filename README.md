# THEANOVA AgentStudio v5.356
## DatabaseErdWorkspacePpt

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
