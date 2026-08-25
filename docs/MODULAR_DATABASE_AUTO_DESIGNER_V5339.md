# v5.339 Modular Database Auto Designer

신규 Agent 설계 인터뷰와 Workflow 결과를 기반으로 대상 Agent의 PostgreSQL DB를 자동 설계합니다.

## 흐름

1. 요구사항 인터뷰 / 첨부 파일 분석
2. Capability 분석
3. DB 필요 여부 판단
4. DB Module Selector
5. Custom Business Entity 추출
6. PK / FK / 타입 / 중복 Validator
7. Workflow 화면에서 사용자 확인
8. PostgreSQL DDL 확정
9. 프로젝트 생성 시 `backend/migrations/001_initial_schema.sql`과 `README.md` 생성
10. Agent Factory 코드 생성 Context에 확정 DB Plan 전달

## Module Registry

- CORE: Agent, version, feature, settings, workflow
- OBSERVABILITY: Agent run, step, artifact
- CONVERSATION: conversation, message
- MEMORY: long-term memory
- FILE: document, version, analysis
- RAG: knowledge base, chunk/vector, retrieval log
- MCP_TOOL: tool, MCP server, binding
- CUSTOMER: customer
- PRODUCT: product
- ORDER: order, order item
- REPORT: report

DB를 명시적으로 사용하지 않는 Agent에는 DB Schema를 강제로 생성하지 않습니다.

## 원칙

- Agent 시스템 데이터와 업무 데이터를 분리합니다.
- JSONB는 설정/metadata 같은 확장 데이터에 사용합니다.
- 검색/JOIN/집계가 필요한 값은 정규 컬럼으로 유지합니다.
- LLM이 제안한 Custom Entity는 Backend Validator를 통과해야 DDL로 확정됩니다.
- DB가 필요한 경우 CORE와 OBSERVABILITY는 기본 Module로 포함됩니다.
- RAG는 FILE Module을 의존하고, ORDER는 CUSTOMER/PRODUCT Module을 보강합니다.
