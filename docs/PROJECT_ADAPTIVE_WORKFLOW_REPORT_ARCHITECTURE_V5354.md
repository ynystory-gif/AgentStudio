# v5.354 Project Adaptive Workflow / Report / Architecture

## 목표

신규 Agent 설계와 기존 프로젝트 로드 모두에서 `워크플로우`, `실행 결과`, `분석 리포트`, `아키텍처`, PPT Export가 대상 프로젝트 성격과 실제 소스에 맞게 변하도록 한다.

## 우선순위

1. Agent Factory가 실제로 만든 `target_agent_workflow`, `agent_architecture`, 실행/테스트 결과가 있으면 이를 최우선 사용한다.
2. 실제 Agent Factory 상태가 없으면 프로젝트 소스를 deterministic 방식으로 분석해 `Project Adaptive Snapshot`을 생성한다.
3. 감지되지 않은 기술은 추측해서 Architecture/PPT에 넣지 않는다.

## Project Adaptive Snapshot

Backend `POST /api/project/adaptive-report`가 프로젝트 루트를 스캔해 다음을 생성한다.

- 프로젝트 유형: `RAG_AGENT`, `MCP_AGENT`, `AI_AGENT`, `WEB_API`, `DATA_APP`, `DATABASE_APP`, `GENERAL`
- 감지 기술 스택과 언어
- 프로젝트 성격별 Workflow
- Components / Interfaces / Persistence / Security / State / Infrastructure
- Capability / MCP Tool 판단
- 프로젝트 로드 시 실행 baseline과 권장 test command
- 분석 리포트 요약

LLM은 호출하지 않으며 현재 프로젝트 소스의 실제 문자열/Framework/Dependency 증거만 사용한다.

## 프로젝트 전환 보호

프로젝트를 로드할 때 이전 프로젝트의 Workflow/Agent Factory Snapshot을 초기화한 뒤 새 프로젝트의 Adaptive Snapshot을 생성한다. 따라서 이전 프로젝트의 Workflow/Architecture가 새 프로젝트 화면이나 PPT에 섞이지 않는다.

## PPT Export

PPT Export 요청 시 Backend가 프로젝트 루트를 다시 분석한다. UI가 오래된 Snapshot을 갖고 있더라도 실제 프로젝트 소스 기반 Adaptive Snapshot을 보완한다.

기존 고정 슬라이드:

- THEANOVA AgentStudio 플랫폼 아키텍처
- AgentStudio Foundation & Infrastructure

를 대상 프로젝트 PPT에서 제거하고 다음으로 교체한다.

- Project Adaptive Architecture
- Project Technology & Runtime

기존 프로젝트 로드에서 `targetWorkflow.source == PROJECT_SOURCE_INFERENCE`이면 AgentStudio 제작 Workflow 슬라이드도 기본 생략하여 대상 프로젝트 Workflow를 우선한다.

## 감지되지 않은 기술 처리

예를 들어 단순 Python 프로젝트에서 PostgreSQL, Redis, OpenAI, Kubernetes가 감지되지 않았다면 해당 기술은 PPT Architecture Component로 생성하지 않는다. 데이터/인프라 계층에는 `미감지` 안내만 표시한다.

## 회귀 기준

- v5.354 Project Adaptive Workflow / Report / Architecture
- v5.354 Large Architecture Visual Asset
- v5.354 SYSTEM_ADMIN Launcher Version Sync
- v5.354 Editable PowerPoint Export
- v5.354 Valid Notebook Create
- v5.354 Notebook Top-Level Await
- v5.354 Search Tree Toggle & Unified Find
- v5.354 Project Search & Text Find
- v5.354 Project File Tree Root Binding
