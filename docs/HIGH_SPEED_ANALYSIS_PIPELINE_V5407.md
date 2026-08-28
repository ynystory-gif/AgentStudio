# v5.407 High-Speed Analysis Pipeline

Agent 설계/개발 진행에서 LLM이 전체 프로젝트를 반복해서 읽는 비용을 줄이기 위해 로컬 고속 분석 계층을 추가했습니다.

## 적용 흐름

```text
User Requirement
  -> Incremental File Index Cache
  -> BM25 Local Ranking
  -> Path / Symbol Matching
  -> Python AST + JS/TS Import Structure Parser
  -> File Dependency Graph Expansion
  -> Optional PyTorch Tensor Score Fusion
  -> Candidate Compression
  -> Validator / LLM / Agent Workflow
```

## 핵심 변경

- 기존 `local_project_summary()`가 같은 프로젝트를 한 번의 요청에서 2회 스캔하던 중복 I/O를 제거했습니다.
- 파일 `mtime + size` 기반 Incremental Cache를 사용해 변경되지 않은 파일은 다시 읽거나 Symbol 분석하지 않습니다.
- 변경된 파일은 최대 8개 Worker로 병렬 인덱싱합니다.
- BM25를 외부 패키지 없이 로컬 구현해 요구사항과 관련된 파일 후보를 빠르게 정렬합니다.
- Python은 `ast`, JavaScript/TypeScript는 import parser를 이용해 파일 간 Dependency Graph를 구성합니다.
- 직접 문자열이 없어도 관련 파일이 import/imported-by 관계에 있으면 후보 점수를 보정합니다.
- PyTorch가 설치되어 있으면 Feature Fusion을 Tensor Matrix 연산으로 처리합니다.
- PyTorch가 없으면 동일한 결과 공식을 Python으로 처리하므로 AgentStudio 실행이 차단되지 않습니다.
- CUDA가 있어도 작은/중간 후보군은 GPU 전송 오버헤드를 피하기 위해 CPU Tensor를 사용하고, 매우 큰 후보군에서만 CUDA를 선택합니다.
- 1차 후보 압축에서는 OpenAI/Ollama/Embedding API를 호출하지 않습니다.

## 통합 위치

- `/project/analyze`는 자동으로 High-Speed Pipeline을 사용합니다.
- `/project/high-speed-analysis`에서 같은 분석을 명시적으로 실행할 수 있습니다.
- `/project/high-speed-analysis/status`에서 Torch/CUDA/tree-sitter/pgvector 사용 가능 상태를 확인할 수 있습니다.
- Agent Workflow의 `analyze_project_node`는 `local_project_summary()`를 사용하므로 신규 설계/개발/증분 개발에서도 자동으로 적용됩니다.
- Workflow Preview의 `project_context`에도 압축된 관련 파일과 Pipeline 메타데이터가 전달됩니다.

## 역할 분리

- 정확 문자열/텍스트 순위: BM25 + Path/Symbol
- 실제 코드 구조: AST / import parser
- 영향 범위: Dependency Graph
- 대량 점수 결합: PyTorch Tensor(선택)
- 최종 의미/설계 판단: Validator + LLM

Tensor가 코드 생성 자체를 대체하지 않습니다. 대신 LLM에게 전달할 프로젝트 Context를 먼저 줄여 설계 검토, 관련 파일 선정, 증분 수정의 대기 시간과 토큰 사용량을 줄이는 구조입니다.

## 확장 포인트

`tree-sitter`와 `pgvector`가 설치되어 있는지는 Status API에서 감지합니다. v5.407의 기본 경로는 별도 대용량 의존성 설치 없이 즉시 동작하도록 Python AST/JS·TS parser/BM25/Graph를 우선 사용합니다. 이후 프로젝트 규모와 Benchmark에 따라 tree-sitter multi-language parser, persistent pgvector code index, local embedding reranker를 선택적으로 연결할 수 있습니다.
