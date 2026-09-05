# THEANOVA AgentStudio v5.598 — RAG Studio Integration / UX Fix

v5.597의 RAG Studio 1~6차 기능과 테이블별 PK 명명 정책을 유지하면서, 실제 Windows 실행 화면에서 확인된 RAG API/UX 통합 문제를 수정한다.

## 핵심 수정

1. **RAG API 404 수정**
   - `runtime-config.js`의 `API_BASE_URL`은 이미 `/api`를 포함한다.
   - RAG Frontend가 다시 `/api/rag/...`를 붙여 `/api/api/rag/...`를 호출하던 문제를 수정했다.
   - 모든 RAG API path를 `/rag/...`로 정규화했다.

2. **Embedding `불러오는 중...` 고정 수정**
   - `/rag/index/config`가 정상 호출되므로 Embedding Provider/Model/Vector 저장/Chunk/Index 상태가 실제 Backend 응답으로 갱신된다.

3. **단계 번호 UI 정리**
   - Knowledge `2차`, Retrieval/Test `5차`, Operation `6차` 등 개발 이력용 번호를 제품 UI에서 제거했다.
   - 이는 미완료 상태가 아니라 구현 단계 이력 표시였으며, 운영 UI에서는 기능명만 보여준다.

4. **File / Folder Native 경로 선택**
   - File은 `파일 찾기`, Folder는 `폴더 찾기` 버튼으로 Windows 선택창을 연다.
   - `/system/pick-file`, `/system/pick-folder`를 사용한다.
   - 사용자가 명시적으로 선택한 absolute path는 RAG Source로 사용할 수 있다. 상대 경로는 Agent 프로젝트 밖으로 탈출할 수 없다.

5. **Source Code 붙여넣기 등록**
   - Source Code 선택 시 경로 input 대신 큰 code textarea를 제공한다.
   - 붙여넣은 코드는 프로젝트의 `.agentstudio/rag_sources/pasted/` 아래 UTF-8 파일로 보관한 뒤 기존 Safety Scan → Chunking → Embedding 파이프라인을 그대로 사용한다.

6. **Operation / Security / Evaluation Dark UI 정리**
   - 정의되지 않은 light CSS fallback 때문에 input/select/card가 흰색으로 보이던 부분을 AgentStudio dark theme에 맞게 통일했다.

7. **Operation 404 중복 표시 해소**
   - 상단 RAG Studio 공통 API 오류 + Operation 내부 API 오류가 동시에 표시되던 원인은 동일한 `/api/api/rag/...` 경로 오류였다.
   - API base 정규화로 두 오류가 함께 제거된다.

## 유지 사항

- RAG Studio 1~6차 기능
- Retrieval Router / Reranking / AI 추천 / Diff 적용
- Agent Tool / Prompt & Tool Studio / Workflow / Agent Test 연결
- Sync / 증분 Re-index / Version / Rollback / Role / Access / Audit / Evaluation
- Knowledge Safety / Prompt Injection 강화
- 모든 신규 DB 테이블의 `{logical_table_name}_id` PK 정책
