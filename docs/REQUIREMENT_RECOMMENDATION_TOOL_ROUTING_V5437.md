# Requirement Recommendation + Two-Stage Tool Routing — v5.437

## 목적
AgentStudio의 요구사항 분석 단계에서 사용자가 모든 세부 기능/메뉴/Tool을 직접 떠올려야 하는 부담을 줄이고, Agent Creator가 필요한 구성을 먼저 제안한 뒤 사용자가 선택·해제할 수 있게 한다.

## 흐름
`사용자 요구사항 → Interview Requirement Analysis → Recommendation Layer → 기능/메뉴/Tool 기본 설정 → 사용자 수정 → Confirmed Requirements → Workflow Design`

Recommendation Layer는 인터뷰와 별도의 LLM 호출을 만들지 않는다. 현재 대화, 첨부 Requirement Memory, 전문 Agent 유형, Tool Registry를 deterministic하게 분석한다.

## Tool Routing
`User Intent → 1차 Intent/Capability Router → Candidate Category/Capability → 2차 Tool Registry Selector → Validator → Tool Invoke`

### 1차
- deterministic 분류를 우선한다.
- confidence가 낮거나 복수 Category 충돌 시 LLM structured classification을 사용한다.
- 출력: primary_category, secondary_categories, capabilities, confidence.

### 2차
- 실제 Tool Registry만 사용한다.
- name, description, input_schema, capability, risk, permission, enabled 상태를 평가한다.
- 후보가 여러 개이고 deterministic score 차이가 작을 때만 LLM을 보조적으로 사용한다.
- disabled/high-risk/confirmation 정책을 우회하지 않는다.

## Agent Editor
추천 설정 자체도 Confirmed Requirement 그룹이므로 변경 시 전체 프로젝트를 재생성하지 않는다. Incremental Designer가 capability/tool/workflow/file/settings 영향 범위만 다시 설계하고 나머지 기존 기능을 재사용한다.
