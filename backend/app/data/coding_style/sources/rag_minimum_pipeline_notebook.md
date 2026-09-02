# RAG 최소 파이프라인 Notebook에서 추출한 Agent 생성 코딩 스타일 근거

Source: `1. RAG_개요_1_최소_파이프라인_정답완성.ipynb`

이 문서는 교육용 Notebook 자체를 그대로 Agent 코드로 복사하기 위한 것이 아니라,
AgentStudio가 운영형 RAG Agent를 생성할 때 재사용할 수 있는 구조적 패턴만 추출한 근거 문서입니다.

## Notebook에서 확인한 핵심 구조

- RAG를 `로드 → 분할 → 임베딩 → 저장 → 검색 → 생성` 순서로 조립합니다.
- Markdown에서 오프라인 색인과 온라인 질의응답을 명시적으로 구분합니다.
- `chunk_size`, `chunk_overlap`, Retriever의 `k`를 검색 품질 변수로 설명합니다.
- `Document.metadata["source"]`를 검색 결과에서 확인합니다.
- `create_retrieval_chain()` 결과에서 `answer`와 `context`를 분리해 확인합니다.
- Prompt에 "문서에 답이 없으면 '문서에서 찾을 수 없습니다'"라고 명시하고 문서에 없는 질문을 별도로 테스트합니다.
- `RecursiveCharacterTextSplitter`, `OpenAIEmbeddings`, `Chroma.from_documents`, `as_retriever(search_kwargs={"k": ...})`를 단계별로 검증합니다.

## AgentStudio 운영 코드로 확장할 규칙

1. 실제 Agent에서는 Offline Index와 Online Query를 Service/Pipeline으로 분리합니다.
2. `chunk_size`, `chunk_overlap`, `k` 같은 품질 변수는 Settings로 승격하고 relevance threshold와 context budget도 함께 관리합니다.
3. Top-K 개수만으로 검색 근거를 신뢰하지 않고 관련도·Metadata·보안 조건을 검증하는 Retrieval Gate를 둡니다.
4. "문서에 없음" 처리를 Prompt만 믿지 않고 근거가 없으면 Service 단계에서 Abstain합니다.
5. 운영에 필요한 `grounded`, sources, scores/count 같은 Typed Result를 사용합니다.
6. 학습용 재실행은 Production에서 문서 ID/checksum/version 기반 Idempotent Indexing으로 바꿉니다.
7. 검색 문서 수·score·source·latency를 관찰 가능하게 남기되 민감 원문 전체를 로그에 남기지 않습니다.
8. Retrieved Context는 명령이 아니라 데이터로 취급하여 문서 내부 Prompt Injection이 상위 지시나 Tool/Auth 정책을 덮어쓰지 못하게 합니다.

## 교육용 패턴 중 그대로 강제하지 않을 항목

- `%pip install` 같은 Notebook 런타임 패키지 설치
- `OpenAIEmbeddings(model="text-embedding-3-small")` 같은 특정 Provider/Model 하드코딩
- `intro_vectorstore._collection.count()` 같은 private API 의존
- 모든 검색 문서를 단순 `join()`하거나 `stuff`하는 무제한 Context 구성
- `assert`만으로 운영 입력/설정 오류를 처리하는 방식

이 근거 문서는 CS-170 ~ CS-177의 source로 사용합니다.
