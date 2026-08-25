# v5.345 Generated Agent Setup Gate / Live Build Trace / Incremental Regeneration

## 1. Generated Agent: 설정 완료 전 Runtime 금지

생성된 Agent의 `SYSTEM_ADMIN.cmd`는 더 이상 첫 실행부터 Python/Frontend 의존성 설치와 `app.main:app` import 검증을 강제로 시작하지 않습니다.

실행 순서:

1. `.agentstudio/setup_requirements.json` 확인
2. `.env`가 없으면 `.env.example`을 기반으로 생성
3. DB / Redis / LLM / 외부 API 등 필수 환경값 확인
4. 미설정이면 `SETUP_REQUIRED (ExitCode=2)`로 종료하고 `.env`를 엽니다.
5. 사용자가 값을 저장한 뒤 `SYSTEM_ADMIN.cmd`를 다시 실행합니다.
6. 설정이 완료된 경우에만 `.venv` / pip / npm / FastAPI import / Backend / Frontend를 진행합니다.

`ExitCode=2`는 프로그램 오류가 아니라 **초기 설정 필요 상태**입니다.

## 2. Agent 개발 실제 진행 로그

Agent Factory LangGraph가 실제 Node를 완료할 때 Job Event를 남깁니다.

예:

- Requirement Analysis
- Project Analysis
- Capability Design
- Architecture
- Database Design
- Target Workflow
- File Plan
- Code Generation
- Artifact Validation
- As-Built Architecture
- Architecture Conformance
- Environment
- Test
- Package / Final Review

로그 때문에 별도의 LLM 호출을 하지 않습니다. Token streaming도 하지 않고 Node 경계 이벤트만 메모리/WebSocket으로 전달하기 때문에 생성 시간에 미치는 영향은 매우 작습니다.

Frontend에는 최근 진행 이벤트를 간단한 `생성 진행 로그`로 표시합니다.

## 3. 재작업 시 증분 설계 / 증분 코드 생성

재작업은 변경 범위를 분석해 세 모드로 나눕니다.

### FULL_REUSE

이전 설계와 요구사항에 변화가 없으면 기존 Workflow / Architecture / DB 설계를 그대로 재사용합니다. 설계 LLM 호출은 0회입니다. 필요한 파일이 모두 존재하면 Code Generation LLM도 호출하지 않습니다.

### PARTIAL_REVISE

일부 요구사항만 변경되면 영향받는 설계 섹션과 파일만 다시 생성합니다.

예:

- UI 변경 → UI/File Plan/관련 Frontend 파일
- DB 변경 → DB Entity/관계/Repository/Model/Migration
- MCP 변경 → Tool/MCP/Workflow 관련 파일
- LLM 설정 변경 → Provider/Settings/관련 코드

기존에 변하지 않은 설계 섹션과 파일은 재사용합니다.

### FULL_REDESIGN

목적, 주요 Workflow, DB/MCP/Architecture 등 구조적 요구사항이 크게 바뀌면 전체 설계를 다시 수행합니다.

## 4. As-Built Architecture 증분 처리

실제 프로젝트 Source Fingerprint를 저장합니다.

- 변경 없음 + 동일 프로젝트 → 기존 As-Built 의미 분석 재사용
- 비구조적 부분 변경 → 정적 재스캔만 수행하고 고성능 LLM 생략 가능
- Architecture / Workflow / DB / MCP 구조 변경 → Codex → OpenAI → Ollama 순서로 의미 분석 재수행

Design ↔ As-Built Conformance Gate는 계속 실행되어 증분 작업이 설계와 어긋나지 않는지 검사합니다.

## 5. 재사용 안전 조건

- 이전 결과는 동일 프로젝트 경로에서만 재사용합니다.
- 변경 영향 범위 밖의 설계/파일만 보존합니다.
- 필수 파일 누락, Architecture Conformance 실패, Test 실패 시 기존 Repair 경로를 사용합니다.
- 큰 구조 변경으로 판단되면 자동으로 FULL_REDESIGN으로 승격합니다.
