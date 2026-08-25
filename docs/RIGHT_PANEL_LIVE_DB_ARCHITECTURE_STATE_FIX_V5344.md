# v5.344 Right Panel Live DB + Architecture State Fix

## 1. 우측 Agent 제작 진행 버튼 정리

기존에는 Workflow/DB 설계와 같은 기능을 실행하는 버튼이 `Agent 제작 진행`, `요구사항 수집 현황` 등 여러 위치에 중복 노출되었습니다.

v5.344부터 우측 핵심 진행 액션은 다음 세 개로 정리합니다.

- `설계 검토`
- `프로젝트 생성`
- `개발 시작`

`프로젝트 생성`은 REQUIREMENTS 단계에서 실행하면 필요한 Workflow/DB 설계를 먼저 자동 완료한 뒤 생성 흐름으로 이어집니다. 요구사항 카드 내부의 중복 Workflow 버튼은 제거했습니다.

## 2. DB 실시간 설계 · 초안

Agent 설계 인터뷰의 사용자 답변이 바뀌는 시점에만 `/database-design/preview`를 호출합니다. Idle polling이나 고성능 LLM 반복 호출은 하지 않습니다.

Preview는 검증된 DB Module Registry를 결정적으로 조립하여 다음을 표시합니다.

- Module
- Entity / Column / PK / FK
- Relationship
- PostgreSQL DDL Preview
- 사용 기술 PostgreSQL / pgvector / Redis
- Redis Session / Search Cache / Recent Search / Cart / Order Draft Key 초안

이 Preview는 `초안`이며 Migration 파일을 생성하지 않습니다. 최종 DB Entity/관계 설계는 Workflow 설계 단계에서 Codex → OpenAI → Ollama 고성능 라우팅과 Backend Validator를 거쳐 확정합니다.

## 3. Architecture Raw Requirement State 노출 차단

Workflow Context 생성 코드가 실제 줄바꿈 대신 `\\n` 문자열을 사용하던 문제를 수정했습니다. 또한 설계 LLM fallback이 전체 인터뷰 Context를 requirement goal로 저장하지 않도록 사용자 개발 요청만 추출하는 Sanitizer를 추가했습니다.

Frontend에서도 다음 문자열/구조를 Architecture 설명으로 표시하지 않습니다.

- `original_request`
- `user_answers`
- `confirmed_requirements`
- `latest_analysis`
- `attachment_summary`
- `USER:` / `ASSISTANT:` transcript
- JSON State dump

## 4. Architecture Lifecycle UI

아키텍처 탭은 다음 상태로 분리합니다.

1. Design Architecture
   - 아직 설계 전이면 `NOT STARTED` Empty State
   - 설계 검토 후에만 실제 component/interface/persistence를 렌더링
2. As-Built Architecture
   - 코드 생성 전에는 `PENDING`
   - 생성 코드 정적 분석 후 실제 구조 렌더링
3. Architecture Conformance
   - As-Built 분석 전에는 `PENDING`
   - 이후 Design ↔ As-Built 점수/Critical mismatch 표시

따라서 Architecture 데이터가 없는 상태에서 Requirement JSON을 대신 출력하지 않습니다.
