# AgentStudio LLM 자동 라우팅

AgentStudio는 작업 난이도에 따라 Provider 우선순위를 다르게 적용합니다.

## 일반 / 반복 작업

기본 자동 순서:

`Ollama → OpenAI → Codex`

주요 대상:
- 프로젝트 탐색
- MCP Tool 분류
- 실행 로그 1차 triage
- 간단한 질의
- Memory 정리
- 요구사항 인터뷰의 일반 질문/요약
- 단일 파일 코드 편집

## 고난도 / 구조 결정 작업

기본 자동 순서:

`Codex → OpenAI → Ollama`

주요 대상:
- Workflow 전체 설계
- LangGraph 상태/분기/재시도/실패 경로 설계
- DB Entity/PK/FK/관계 설계
- 복잡한 다중파일 코드 변경
- 프로젝트 전체 코드 변경
- 코드 실행/테스트 실패 분석
- 디버깅 및 대규모 Repair

Codex가 활성화되어 있지만 ChatGPT 계정 연결이 없거나 실행에 실패하면 OpenAI로 내려가고, OpenAI가 비활성/미설정/실패하면 Ollama로 자동 fallback합니다.

## Debug 흐름

실행/테스트 실패
→ Ollama: 긴 로그의 핵심 오류 1차 추출
→ Codex 우선: 원인 판단/복구 전략
→ Codex 우선: 관련 Patch/Repair
→ 재테스트
→ 실패 시 OpenAI/Ollama fallback

## DB 설계 흐름

Workflow 고성능 설계
→ DB Module Registry 자동 조립
→ 고성능 DB Entity/관계 보강 (`Codex → OpenAI → Ollama`)
→ Backend PK/FK/타입 Validator
→ 사용자 확정
→ PostgreSQL Migration 생성

## 수동 모드

설정에서 수동 Provider를 지정하거나 API 요청에서 Provider를 명시하면 사용자 선택을 우선합니다.
