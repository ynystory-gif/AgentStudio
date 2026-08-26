# v5.351 Editable PowerPoint Export

## 목표

AgentStudio의 `워크플로우`, `실행 결과`, `분석 리포트`, `아키텍처` 화면을 PowerPoint 문서로 다운로드할 수 있도록 한다.
화면을 하나의 이미지로 캡처하는 방식이 아니라 PowerPoint 네이티브 도형·텍스트·카드·화살표를 생성하여 다운로드 후 직접 수정할 수 있게 한다.

## UI

- 워크플로우: `PPT 다운로드`
- 실행 결과: `PPT 다운로드`
- 분석 리포트: `PPT 다운로드`
- 아키텍처: `PPT 다운로드`
- 위 4개 탭 공통 상단: `전체 PPT`
- 생성 중에는 버튼을 잠그고 `PPT 생성 중...` 상태를 표시한다.

## PPT 구성

### 전체 PPT

1. 표지
2. AgentStudio 제작 Workflow
3. 개발 대상 Agent Workflow
4. 실행 결과
5. 분석 리포트
6. Design Architecture
7. As-Built Architecture & Conformance
8. THEANOVA AgentStudio Platform Architecture

### 개별 탭

- WORKFLOW: 제작 Workflow + 대상 Agent Workflow
- RUN: 실행 결과
- REPORT: 분석 리포트
- ARCHITECTURE: Design + As-Built/Conformance + Platform Architecture

## 아키텍처 표현

Architecture 슬라이드는 레이어형 구조로 정리한다.

- Client / User
- Interface / API
- Agent / Service Components
- State / Feedback Loop
- Persistence / Data
- Security

AgentStudio Platform 슬라이드는 다음 구조를 도형으로 표현한다.

- User
- React Frontend UI
- FastAPI Backend
- Agent Orchestrator
- LLM Layer
- Execution Layer (MCP / Local Tool / Python / Terminal / SQL)
- Persistence (PostgreSQL / Redis / pgvector / 기타 DB)
- Project State / Report / Recovery

모든 핵심 박스와 텍스트는 PowerPoint에서 이동·수정·삭제할 수 있는 네이티브 객체이다.

## Backend

- `POST /api/presentation/export`
- `python-pptx` 기반 생성
- PPTX는 메모리에서 생성 후 바이너리 응답으로 즉시 다운로드
- 프로젝트 이름을 포함한 파일명 사용
- 토큰, API Key, DB URL Password 등 주요 Secret 패턴은 PPT에 기록하기 전에 마스킹

## 회귀 검증

`backend/validate_v5351_editable_presentation_export_contract.py`

- Frontend v5.351
- 5개 Export Scope 연결
- PPT Export API 연결
- PowerPoint 네이티브 도형 생성 여부
- 전체 Export 8 Slides 생성 여부
- 핵심 슬라이드 제목/내용 존재 여부
