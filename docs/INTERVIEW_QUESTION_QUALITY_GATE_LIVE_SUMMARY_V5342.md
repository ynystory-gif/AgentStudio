# v5.342 Interview Question Quality Gate + Live Requirement Summary

## 목적
Agent 설계 인터뷰가 이미 답한 내용을 반복하거나 Hybrid Search, LangGraph 분기, DB PK/FK 같은 구현 세부사항을 사용자에게 다시 결정하라고 묻는 문제를 방지합니다.

## Question Quality Gate
- 비완료 응답은 질문이 정확히 하나인지 검사합니다.
- 검색 알고리즘/벡터 결합/LangGraph/PK·FK/Redis Key/Retry Route 등 AgentStudio가 자동 설계할 기술 세부 질문을 차단합니다.
- 차단 시 현재 대화에서 이미 확인된 기술 요구사항을 짧게 확인한 뒤 UI, 인증, 외부 API/MCP, 실행환경, 업무 승인 정책 등 사용자 의사결정 항목 중 가장 중요한 미확정 항목 하나로 교체합니다.
- 요구사항 완료 응답은 기존 완료 Gate를 유지합니다.

## 좌측 실시간 요구사항 요약
신규 Agent 설계 좌측 메뉴가 고정 안내문 대신 현재 인터뷰 내용을 실시간 반영합니다.
- 목적: 만들 Agent의 핵심 목적
- 기능: 검색/추천/주문/RAG/파일분석 등 대화에서 확인된 핵심 기능
- MCP / Tool·데이터: PostgreSQL, Redis, pgvector, MCP, OpenAI, Ollama 등
- 실행 환경: UI/Backend/LLM/OS 등 확정 정보
- 확인: 요구사항 수집 수와 Workflow 상태

추가로 `대화 요구사항 요약` 카드에서 수집 완료된 요구사항 값을 최대 8개까지 표시합니다.
