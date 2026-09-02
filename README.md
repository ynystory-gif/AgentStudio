## v5.499 Media Workflow Editor UI

- 기존 그룹형 Target Agent Workflow를 유지하면서 Media Agent에 Node Palette · 편집 Canvas · Node 설정 · Preview/Job 상태 UI를 추가했습니다.
- Backend Media Node Catalog를 직접 읽고 Typed Port 연결을 `/api/media/workflow/validate-port`로 검증합니다.
- Canvas에서 Node 추가/이동/삭제, Output→Input 연결, Provider/Model/크기/Retry 설정, Workflow JSON 가져오기/내보내기를 지원합니다.
- `/api/media/workflow/validate`와 `/normalize`로 전체 Workflow를 검증·정규화한 뒤 Agent 설계 Draft/Checkpoint에 반영합니다.
- Editor 실행/정지는 설계 단계임을 명시하고 실제 Provider 실행은 생성 대상 Agent Adapter Runtime의 책임으로 유지합니다.

## v5.498 Media Workflow Core

- Agent Creator/Editor 정체성을 유지하면서 미디어 생성·처리 Agent 설계용 고수준 Workflow Core를 추가했습니다.
- Typed Media Port, Media Artifact, Async Media Job, Provider Adapter 계약과 additive Workflow extensions.media Schema를 추가했습니다.
- ComfyUI는 저수준 Node Editor가 아니라 외부 실행 Provider로 취급하며 Provider Capability/Health/Workflow readiness를 기준으로 선택합니다.
- Media Agent 전문화 설계를 추가해 생성→검증→기술 Retry/품질 Retry→Human Approval→저장 Workflow를 Agent Factory가 보존합니다.
- 기존 Workflow와 Agent 실행 기능은 변경 없이 읽히도록 Backward Compatibility를 유지합니다.

## v5.497

- 개인정보 보호 PII 마스킹 Notebook 분석을 기반으로 Agent 생성 코딩 스타일에 Privacy 전용 규칙 7개를 추가했습니다.
- PII 처리 경계, 본문+Metadata 이중 Sanitization, Fail-closed, Raw/Sanitized 분리, PII-safe 로그/Audit, 정책 버전·Data Minimization, 누락·오탐 회귀검사를 기본 ON으로 적용합니다.
- Coding Style Registry를 2.2로 올리고 CS-178~CS-184를 추가했습니다.
- 기존 CS-159 Metadata 보존은 Privacy Sanitization/Allowlist 이후 안전한 Metadata만 보존하도록, CS-176 Retrieval Observability는 Query·Context·Snippet의 원문 PII/Secret을 기록하지 않도록 강화했습니다.

## v5.496

- RAG 최소 파이프라인 Notebook 분석을 기반으로 Agent 생성 코딩 스타일에 운영형 RAG 전용 규칙 8개를 추가했습니다.
- 색인/질의 Pipeline 분리, RAG 품질 설정값 중앙관리, Retrieval 관련도 Gate, Grounded Answer/Abstain, Context Budget, Idempotent Indexing, Retrieval Observability, Retrieved Context Prompt Injection Guard를 기본 ON으로 적용합니다.
- Coding Style Registry를 2.1로 올리고 CS-170~CS-177을 추가했습니다.
- RAG/VectorStore/Embedding/Retrieval/Indexing/Grounding 요청에서 새 규칙을 자동 선택하도록 Selector를 확장했습니다.

## v5.495 Resilient Agent Coding Style

- `2-2. 문서_로딩_OCR.ipynb`의 실제 OCR/환경 검증 코드를 기준으로 Agent 생성 코딩 스타일을 추가 개선했습니다.
- 기존 18개 선택 스타일을 유지하면서 Preflight Validation, 기존 환경 비파괴, 품질 기준 Fallback, Typed Result Contract, 외부 Artifact 검증, 통제된 Benchmark, 조치 가능한 오류 메시지 7개를 추가해 총 25개 기본 ON 스타일을 제공합니다.
- 생성·증분 수정·테스트 실패 Repair·재개발 Prompt가 동일한 `user_coding_style` 정책을 사용합니다.
- OCR/Paddle/EasyOCR/Tesseract/GPU/Benchmark/다운로드 요청을 자동 감지해 CS-163~CS-169 Registry 규칙을 선택합니다.
- 교육용 전역 Warning 숨김, Runtime `%pip`, 무단 패키지 uninstall, 무검증 모델 다운로드, 상대 `result` 경로, raw dict 반환은 Production Agent 기본 스타일로 복사하지 않습니다.

## v5.491

### v5.491
- 사용자 제공 문서 로딩 Notebook의 실제 코드 패턴을 분석해 Agent 생성용 Coding Style에 반영했습니다.
- 기존 10개 선택 규칙에 처리 흐름, 결과 검증, 리소스 관리, 외부 I/O, Metadata, 정규화, Lazy Loading, Warning 정책 8개를 추가했습니다.
- RAG/PDF/CSV/JSON/OCR/Web Loader 요청을 자동 감지해 문서 전용 Registry 규칙을 생성·재개발·수정 Prompt에 적용합니다.
- 교육용 print/고정 파일명/전역 Warning 숨김은 운영 Agent 기본 스타일로 복사하지 않습니다.

## v5.490

### v5.490
- Notebook에서 Python `DeprecationWarning`, `FutureWarning`, `UserWarning`, `RuntimeWarning` 등 정상 경고를 실제 오류와 분리합니다.
- Warning은 셀 실행 성공 상태를 유지하면서 노란 `⚠ 경고 N개` 요약으로 표시하고, 상세 원문은 `자세히 보기`로 접고 펼칠 수 있습니다.
- 일반 `stderr`는 중립적인 안내 색상으로 표시하고, `output_type=error`인 실제 Exception/Traceback만 기존 빨간 오류 스타일을 사용합니다.
- v5.489의 외부 Python Worker Runtime, Windows WinError 206 방지, 패키지 보호 실행 구조를 그대로 유지합니다.

## v5.489

### v5.489
- Windows `WinError 206`의 근본 원인이었던 거대한 `python -c <Worker Code>` 부트스트랩을 제거하고, `backend/app/services/python_worker_runtime.py` 별도 Runtime 파일 실행 구조로 변경했습니다.
- Notebook `%pip`, `!pip`, `!python -m pip`는 Persistent Worker 내부가 아니라 Backend가 프로젝트 `.venv`의 Python으로 직접 실행합니다. 설치 전 기존 Worker를 종료해 DLL/모듈 파일 잠금을 해제하고 설치 후 새 Worker로 이어집니다.
- 같은 셀에 pip 명령 뒤 일반 Python 코드가 있으면 패키지 설치 성공 후 새 Worker에서 나머지 코드를 이어 실행합니다.
- Windows/한글/긴 프로젝트 경로, Persistent 변수, top-level await, pip 보호 실행, Worker 재시작을 포함한 Runtime 회귀검사를 추가했습니다.
- v5.487 이미지 Preview/Rich Image Output 및 v5.488 Streaming 복구 기능을 유지합니다.

## v5.488

### v5.488
- Notebook의 `%pip`, `!pip`, `!python -m pip` 패키지 설치 셀은 Rich Output NDJSON 스트림 대신 보호된 일반 실행 경로를 사용합니다.
- 패키지 설치 중/완료 상태를 표시하고, Worker 비정상 종료 시 실제 native 출력을 보존한 `PythonWorkerExited` 결과와 세션 자동 복구를 제공합니다.
- 일반 Notebook 스트림 최종 결과 누락 시 세션을 자동 Reset합니다. DB INSERT·파일 쓰기·API 호출 중복 방지를 위해 임의 셀 자체는 자동 재실행하지 않습니다.
- v5.487 이미지 Preview와 Notebook Rich Image Output 기능을 그대로 유지합니다.

## v5.483

### v5.483
- `v5.482`를 기준으로 기존 기능을 유지하면서 코딩 스타일 설정 UI를 고정형 오버레이 카드로 정리해 좁은 우측 패널에서도 설명이 세로로 찌그러지지 않도록 개선했습니다. 이름·타입 / 구조·Notebook 그룹 설명, 전체 선택, 기본값 버튼을 정리했습니다.
- 메모 > 실시간 기록의 Transcript 헤더에 `요약정리` 버튼을 배치해 녹음 중에도 현재까지 수집된 확정+임시 텍스트를 즉시 요약할 수 있습니다.
- Backend faster-whisper의 `partial` 이벤트에 임시 구간 시작/종료 시간을 포함하고 Frontend에서 임시 Segment로 즉시 표시합니다. YouTube/화면 오디오 재생 중에도 확정 전 텍스트가 `수집 중` 상태로 Transcript 영역에 바로 반영됩니다.
- 실시간 확정 Segment는 `수집됨`, 종료 후 정밀 보정 Segment는 `보정 완료`로 표시하며, 보정 결과가 들어오면 recording time range 기준으로 기존 임시/실시간 구간을 교체합니다.
- Transcript 처리 흐름을 `수집 중 → 보정 중 → 완료` 3단계 상태로 표시합니다.

## v5.482

### v5.482
- 첨부 파일 AI 정리의 파일 칩을 실제 클릭 가능한 파일 열기 버튼으로 변경했습니다. 프로젝트 내부 첨부 파일은 중앙 코드 편집 탭에서 바로 열립니다.
- Agent Database 설정에 `PostgreSQL 스키마 생성`과 `Firestore Database 생성` 수동 실행 버튼을 추가했습니다. 실제 생성 전 확인 창을 표시하고 연결 정보만 사용 모드에서는 생성 버튼을 비활성화합니다.
- Frontend 전체 CSS/JS/TS의 명시적 글자 크기를 점검하여 13px 미만 `font-size`, `font` shorthand, inline `fontSize`를 모두 13px 이상으로 상향했습니다.
- v5.481의 코딩 스타일 UI 정리, 실시간 Transcript 요약정리, 화면/시스템 오디오 STT 보호 기능을 그대로 포함합니다.

### v5.481
- 코딩 스타일 설정 팝오버를 두 그룹으로 정리하고 우측 제작 카드의 전역 button 폭 규칙 때문에 설명 문구가 세로로 찌그러지던 레이아웃을 수정했습니다.
- 메모 > 실시간 기록에 `요약정리` 버튼을 추가해 현재 Transcript를 사용 중인 LLM 라우팅으로 요약하고 결과를 바로 확인/복사할 수 있습니다.
- 화면/시스템 오디오 STT에서 Audio Track이 없는 공유를 즉시 감지합니다. YouTube는 Chrome 탭 + 탭 오디오 공유가 켜져야 실시간 STT와 종료 후 정밀 보정이 동작합니다.

- Media Session TypeScript Undefined Guard Fix: Windows strict TypeScript build에서 Transcript 마지막 segment 접근 시 발생하던 TS2532 오류를 optional chaining guard로 수정했습니다.
- v5.479 faster-whisper 실시간 STT 기능은 그대로 유지합니다.

- 실시간 음성 텍스트 변환의 기본 엔진을 브라우저 SpeechRecognition에서 Backend `faster-whisper` PCM Streaming으로 전환했습니다.
- 마이크/화면 공유 오디오를 16kHz PCM으로 WebSocket 전송하고, VAD + Overlap Window로 구간 경계의 발화 누락을 줄입니다.
- 실시간 임시 문장과 확정 문장을 분리하며 음성 입력 레벨, STT 엔진, 마지막 인식 시각, 재연결/전송 누락 상태를 표시합니다.
- 녹음 종료 시 전체 PCM을 다시 분석하여 누락/오인식을 보정한 최종 Transcript로 교체합니다.
- `faster-whisper`를 사용할 수 없는 마이크 환경에서는 기존 Chrome SpeechRecognition을 보조 fallback으로 사용합니다.
- STT는 CPU/int8을 기본으로 하며 GPU 사용은 `AGENTSTUDIO_STT_DEVICE=cuda`를 명시한 경우에만 활성화합니다.

## v5.478

- `Agent 제작 진행` 제목 오른쪽에 기존 `변수·메소드 설명 추가`와 함께 `코딩 스타일` 설정 메뉴를 추가했습니다.
- 신규 Agent의 기본 코딩 스타일은 의미 있는 변수명, 상수 UPPER_SNAKE_CASE, Python 함수 snake_case, 클래스 PascalCase, 함수 Type Hint, 함수 Docstring, Notebook 한 셀 한 역할, 반복 로직 함수화, 실행 결과 단계 Label, Magic Number 최소화를 개별 ON/OFF 할 수 있습니다.
- 코딩 스타일 선택값은 Agent 설계 Draft/Checkpoint에 저장되어 프로젝트를 다시 열거나 재개발할 때 유지됩니다.
- 개발/재개발 시작 시 선택한 스타일 Profile을 Agent Factory `design_bundle.user_coding_style`로 전달하고 코드 생성·수정·테스트 실패 Repair·증분 재개발 Prompt에 일관되게 적용합니다.
- 함수 Docstring 항목은 `변수·메소드 설명 추가` 옵션과 연동하여 설명 주석을 원하지 않는 프로젝트에 주석을 강제로 만들지 않습니다.
- 기존 Coding Style Registry의 프로젝트/Framework별 규칙은 유지하며, 이번 사용자 Profile은 그 위에 적용되는 프로젝트별 기본 스타일 정책입니다.


## v5.492 Live Transcript Text File Save
실시간 STT Transcript와 요약정리를 프로젝트 recordings 폴더에 UTF-8 TXT로 저장하고 실제 저장 경로를 UI에 표시합니다.


## v5.493 Runtime Path Policy
Temp/Cache/Output 기본 경로를 실제 런타임과 다운로드 저장 경로에 연결했습니다.

## v5.494 Active Ollama Model Resolver
- Ollama 요청 모델의 Source of Truth를 `active_ollama_model_service` 하나로 통합했습니다.
- 현재 PC에 `theanova-learn:latest`가 적용되어 있으면 모든 일반 Ollama 요청/요청 JSON/상태 표시가 해당 모델을 사용합니다.
- 학습 파생 모델이 없을 때는 `qwen3.5:4b`, 이후에만 설치된 유효 Chat 모델로 fallback하며 `qwen2.5:*` 레거시 기본값은 제거했습니다.
- Backend 시작 시 DB 학습 적용 상태, `backend/.env`, 프로세스 `OLLAMA_MODEL`을 동기화해 상단 표시와 실제 `ChatOllama` 호출의 불일치를 방지합니다.


## v5.500 Interview Question State & Event-Driven Save
- 인터뷰 중 `UI / Layout 뭐가 있어?` 같은 정보 질문은 요구사항 답변으로 오인하지 않고 질문에 대한 답만 반환합니다. 질문 뒤에 다음 인터뷰 질문을 자동으로 붙이지 않습니다.
- 정보 질문은 대기 중 Requirement Slot을 완료 처리하지 않으며, 이미 분석한 첨부 파일을 재분석하지 않습니다.
- 첨부 파일은 Context 준비가 끝나면 Requirement Registry/요약을 한 번 자동 생성해 Memory에 저장하고 이후 인터뷰에서는 해당 Memory를 재사용합니다. 기본 첨부 요약은 LLM 재호출 없이 결정적으로 생성됩니다.
- 요구사항 수집 상태는 Assistant의 예시 문구가 아니라 실제 사용자 요구사항/확정 설정/첨부 분석 결과만 사용합니다. UI Framework와 Layout 상태를 분리했습니다.
- UI Framework(`React + TypeScript` 등)와 Layout Template을 별도 필드로 유지해 Layout 변경이 Frontend Framework 값을 덮어쓰지 않습니다.
- Tool / Prompt 설정 탭을 추가해 Tool 모드, 지정 Tool, System Prompt, 질문 응답 정책을 설계 Snapshot/Workflow 요구사항에 저장합니다.
- DB-backed 설계 자동 저장은 Background 상태 변경으로 실행하지 않고 실제 사용자 Pointer/Keyboard 액션 후에만 debounce 저장합니다. 사용자가 아무 동작도 하지 않으면 저장 시각이 갱신되지 않습니다.
- 첨부 분석 정리 패널의 높이 조절 Handle을 상단으로 이동하고 `▲ 접기 / ▼ 펼치기` 버튼을 추가했습니다.
- 일반 인터뷰 LLM 호출은 60초 hard timeout 후 deterministic interview fallback으로 전환해 2분 이상 무한 대기하지 않습니다.
- `지금 DB 설정`의 PostgreSQL/Firestore/Redis 사용 체크 컨트롤과 하위 옵션 체크박스의 클릭 영역을 복구했습니다.
