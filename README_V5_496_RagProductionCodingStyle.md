# THEANOVA AgentStudio v5.496 — RAG Production Coding Style

## 변경 내용

업로드된 `1. RAG_개요_1_최소_파이프라인_정답완성.ipynb`의 최소 RAG 흐름을 분석해,
교육용 코드를 그대로 복사하지 않고 운영형 RAG Agent 생성에 필요한 규칙만 Coding Style Registry에 추가했습니다.

- 기존 사용자 코딩 스타일 25개 유지 + RAG 전용 8개 추가 = 33개 기본 ON
- Registry `2.0 → 2.1`, `CS-170 ~ CS-177` 추가
- Offline Index / Online Query Pipeline 분리
- RAG 품질 Parameter Settings 중앙관리
- Retrieval Relevance Gate
- Grounded Answer / Abstain Contract
- Context Token Budget
- Idempotent Indexing / document version 추적
- Retrieval Observability
- Retrieved Context Prompt Injection Guard

## 적용 범위

Agent 생성, 기존 Agent 수정, 테스트 실패 Repair, 실패 지점 재개발 Prompt의
`design_bundle.user_coding_style`에 동일하게 적용됩니다.

RAG/VectorStore/Embedding/Retriever/Indexing/Grounding/Prompt Injection 관련 요청에서는
Coding Rule Selector가 CS-170~177을 작업 문맥에 맞게 자동 선택합니다.
