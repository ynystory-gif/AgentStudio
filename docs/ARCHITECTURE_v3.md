# AgentStudio v3 Architecture

## 적용된 1~5 항목

### 1. Debug 자동 반복 Loop
Project Analyze → Patch → Test → 실패 로그 분석 → 재Patch → 재Test
- `MAX_DEBUG_ITERATIONS`
- 반복 횟수 제한
- 실패 로그 기반 새로운 Patch 생성

### 2. Project Analyzer
사용자가 파일을 직접 고르지 않아도 요청어, 파일명, 심볼, 코드 내용을 기반으로 관련 파일을 자동 탐색합니다.

### 3. LangGraph 영속 Runtime
FastAPI lifespan 동안 PostgreSQL Checkpointer와 compiled graph를 유지합니다.
`thread_id` 기반으로 중단/재개합니다.

### 4. MCP Registry + 승인 정책
- DB에 MCP Server/Tool Registry 저장
- 주기적으로 서버 `tools/list` 재동기화
- `listChanged` capability 기록
- Tool 제거 시 Registry에서 disabled 처리
- Trust Level + Capability + Risk 기반 승인 판단

### 5. PostgreSQL + pgvector Memory
- SESSION / PROJECT / KNOWLEDGE
- OpenAI 또는 Ollama Embeddings
- cosine similarity 검색
- PostgreSQL `vector` extension 자동 초기화

## 암호화 / Secret Manager
이번 버전에는 사용자의 요청에 따라 포함하지 않았습니다.
