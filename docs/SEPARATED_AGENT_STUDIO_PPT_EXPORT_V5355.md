# v5.355 Separated Agent / Studio PPT Export

## 목적

PPT 문서에서 대상 Agent/로드 프로젝트의 정보와 THEANOVA AgentStudio 자체 정보를 혼합하지 않는다.

## UI 계약

상단 공통 다운로드 영역:

- `Agent PPT`: 현재 생성 Agent 또는 로드 프로젝트의 전체 PPT
- `Studio PPT`: THEANOVA AgentStudio 자체 전체 PPT

페이지 다운로드:

- Workflow PPT: Target Agent/Project Workflow만
- Run PPT: Target Agent/Project 실행 결과만
- Report PPT: Target Agent/Project 분석 리포트만
- Architecture PPT: Target/As-Built/Project Stack만

## Backend 계약

`POST /api/presentation/export`

- `deck_type=AGENT|STUDIO`
- `scope=ALL|WORKFLOW|RUN|REPORT|ARCHITECTURE`
- `STUDIO`는 `scope=ALL`만 허용
- Project Adaptive 재분석은 `AGENT`만 수행

## Agent PPT

- Cover
- Target Workflow
- Execution Result
- Analysis Report
- Target Project Architecture
- As-Built Architecture (사용 가능한 경우)
- Project Technology & Runtime

AgentStudio Factory Workflow 및 AgentStudio Platform Architecture는 포함하지 않는다.

## Studio PPT

- THEANOVA AgentStudio Cover
- AgentStudio 제작 Workflow
- Workspace & Core Capabilities
- Execution & Runtime
- Analysis & Governance
- THEANOVA AgentStudio Platform Architecture
- AgentStudio Foundation & Infrastructure

현재 선택한 프로젝트의 이름/Workflow/Architecture는 Studio PPT에 포함하지 않는다.
