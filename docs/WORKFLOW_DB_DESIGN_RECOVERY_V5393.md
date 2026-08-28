# v5.393 Workflow / DB Design Recovery

## 목적

신규 Agent 재설계/Workflow 설계 과정에서 Codex/OpenAI/Ollama 등 AI Provider가 모두 실패하거나 DB Entity 보강/Validator 단계에서 오류가 발생해도 사용자가 막힌 화면에 남지 않도록 복구 경로를 제공합니다.

## 복구 동작

- **AI 설계 다시 시도**: 같은 최신 요구사항으로 Adaptive Provider 체인을 다시 실행합니다.
- **안전 설계로 계속**: AI Provider를 호출하지 않고 AgentStudio deterministic Workflow fallback과 검증된 Database Module Registry로 설계를 계속합니다.
- **DB 초안만 다시 계산**: `/database-design/preview`의 LLM-free Module Registry를 현재 요구사항으로 다시 조립합니다.
- **AI Provider 상태 확인**: `/llm/runtime-status`를 조회해 현재 Provider/모델 상태를 화면에서 확인합니다.
- **설계 인터뷰로 돌아가기 / 요구사항 수정**: 입력 요구사항을 보정한 뒤 재설계를 시작합니다.

## 상태 동기화

Agent Factory Background Job이 terminal 상태가 되면 실행 정지 UI를 즉시 해제합니다. 탭/화면 복귀 시 `/workflow/runtime-status`에서 Backend Job, asyncio Task, validation subprocess를 재조회해 실제 실행 여부를 다시 맞춥니다.

## 요구사항 충돌

최신 사용자 지시가 기존 Headless UI와 충돌할 경우 최신 명시적 Frontend 요구사항이 우선합니다. 예: `UI 없음 / Headless Agent` 이후 `React + TypeScript 화면으로 해줘`가 입력되면 이전 UI Layout은 superseded 처리되고 UI/Layout 재선택 및 Workflow 재설계 대상으로 전환됩니다.
