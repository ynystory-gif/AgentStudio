# v5.340 High Performance Provider Priority

AgentStudio의 자동 AI Provider 정책을 작업 난이도에 따라 이원화합니다.

## 일반 작업

`Ollama 우선`

필요한 지원 작업에서 OpenAI 또는 Codex로 fallback합니다. 단순 질의처럼 Codex가 필요하지 않은 작업은 로컬/일반 Provider만 사용합니다.

- 요구사항 인터뷰의 일반 질문/정리
- 첨부 파일 1차 요약
- Intent/Schema 추출
- 단순 질의
- 단일 파일 코드 편집
- 가벼운 로그 triage

## 고난도 작업

`Codex → OpenAI → Ollama`

- Workflow 전체 설계
- LangGraph 상태/분기/재시도/실패 경로 설계
- DB Entity/PK/FK/관계 설계
- 복잡한 다중파일 코드 변경
- 프로젝트 전체 코드 변경
- 실행/테스트 오류 분석
- 디버깅 및 대규모 Repair

Provider는 설정에서 활성화된 경우 후보가 되며 실제 호출이 실패하면 다음 Provider로 자동 fallback합니다. Codex는 ChatGPT OAuth 연결이 필요하고, OpenAI는 API Key가 필요합니다. 두 유료/외부 Provider가 모두 사용할 수 없어도 Ollama로 계속 동작합니다.

수동 Provider 모드와 명시적 Provider override는 사용자 선택을 우선합니다.

## DB 설계 안전장치

DB Entity/관계는 고성능 LLM이 Custom Business Entity를 제안한 뒤에도 바로 DDL로 사용하지 않습니다. 기존 Module Registry와 `validate_database_plan()`이 테이블명, 컬럼명, PK/FK, 참조 대상, 타입, 중복을 다시 검증합니다.

## 사용자 확인

Workflow 화면에는 실제 설계에 사용된 Provider를 표시합니다.

- Workflow / LangGraph Provider
- DB Entity / 관계 Provider

이를 통해 자동 fallback이 발생했는지 사용자가 확인할 수 있습니다.
