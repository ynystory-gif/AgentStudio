# v5.343 Workspace Live Requirement Summary Binding Fix

## 문제

v5.342에서는 실시간 요구사항 요약 계산 함수가 존재했지만 실제 WORKSPACE > Agent 설계 좌측 패널은 고정 문구 배열을 렌더링했습니다. 우측 요구사항 State는 갱신되어도 좌측 목적/기능/MCP/DB/실행환경/확인 카드가 변하지 않았습니다.

## 수정

- WORKSPACE 설계 좌측 패널을 `getBuilderConversationSummary()`에 직접 연결
- 목적/기능/MCP Tool/DB 설계/실행 환경/확인 6개 카드를 최신 대화 State에서 매 렌더 계산
- DB와 MCP를 분리하여 PostgreSQL/Redis/pgvector는 DB 설계 카드에 표시
- 수집된 세부 요구사항을 좌측 `대화 요구사항 요약`에 표시
- 긴 기술 스택 문장에서도 `... Agent를 만들...` 목적 문구를 우선 추출
- 기존 Question Quality Gate와 우측 요구사항 수집 현황은 그대로 유지

## 예시

사용자가 PostgreSQL, Redis, pgvector 기반 AI 상품 검색·추천·주문 Agent 요구사항을 입력하면 좌측은 다음처럼 갱신됩니다.

- 목적: AI 상품 검색·추천·주문 Agent
- 기능: 자연어 검색 · Hybrid Search · 상품 추천 · 재고 확인 · 주문 처리
- MCP / Tool: 미확정 시 확인 중
- DB 설계: PostgreSQL · Redis · pgvector
- 실행 환경: 수집된 Backend/LLM/Runtime 정보
- 확인: 요구사항 n/11 · 인터뷰 진행 중 또는 Workflow 설계됨
