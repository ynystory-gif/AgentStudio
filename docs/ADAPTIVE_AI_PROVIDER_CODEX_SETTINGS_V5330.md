# v5.330 Adaptive AI Provider / Codex Settings

## 목적

AgentStudio의 AI 기능을 하나의 Provider 정책으로 통합합니다.

- 가능한 텍스트/분석 작업은 **Ollama 로컬 LLM을 먼저 사용**합니다.
- Ollama 호출이 실패하면, 사용 설정과 자격정보가 있는 경우 **OpenAI API**를 다음 후보로 사용합니다.
- 요구사항 분석, Agent 설계, 코드 생성/수정, 패치, 일반 디버깅처럼 Codex가 적합한 작업은 **Codex를 마지막 fallback**으로 사용할 수 있습니다.
- Codex는 사용자가 시스템 설정에서 명시적으로 켜야 하며, ChatGPT OAuth 자격정보는 AgentStudio DB나 `.env`에 복사하지 않습니다.

## 기본 자동 라우팅

`AI_PROVIDER_STRATEGY=ollama_first`가 기본값입니다.

| 작업 | 기본 시도 순서 |
| --- | --- |
| 프로젝트 탐색 / Tool 분류 / 로그 1차 진단 / 간단 질문 / Memory 정리 | Ollama → OpenAI API |
| Agent 설계 인터뷰 / 요구사항 분석 | Ollama → OpenAI API → Codex |
| 코드 생성 / LLM 대화형 코드 편집 / AI 변경 제안 / Patch 생성 | Ollama → OpenAI API → Codex |
| 일반 디버깅 / 실패 원인 분석 | Ollama → OpenAI API → Codex |
| Embedding | Ollama 우선. Codex는 Embedding Provider로 사용하지 않음 |

OpenAI 사용을 끄면 OpenAI만 후보에서 제거됩니다. Codex를 켜 둔 경우 지원 작업은 `Ollama → Codex`가 됩니다. OpenAI와 Codex를 모두 끄면 LLM 작업은 Ollama만 사용합니다.

## 수동 Provider 모드

시스템 설정의 **AI Provider 라우팅**에서 수동 모드를 선택할 수 있습니다.

- 로컬/일반 작업: Auto / Ollama / OpenAI API
- 코딩: Auto / Ollama / OpenAI API / Codex
- 요구사항/Agent 설계: Auto / Ollama / OpenAI API / Codex

IDE 상단의 AI 모드 메뉴에서도 AUTO, OpenAI, Ollama, Codex를 빠르게 선택할 수 있습니다. Codex 모드는 가벼운 일반 작업은 Ollama에 남겨 두고 코딩/요구사항 계열만 Codex로 지정합니다.

## Codex 설정 / ChatGPT 연결

시스템 설정에 **Codex / ChatGPT 계정** 패널이 추가되었습니다.

1. `Codex 사용` 체크
2. `Codex 설정 저장`
3. Codex CLI 설치 여부 확인
4. `Codex 시작/상태 확인`
5. `ChatGPT 계정 연결`
6. 브라우저에서 공식 ChatGPT OAuth 완료
7. `Codex 시작/상태 확인` 또는 `남은 사용량 새로고침`

`Codex 사용`을 끄고 저장하면 현재 실행 중인 AgentStudio용 Codex app-server도 즉시 종료합니다. 공식 Codex CLI가 보관하는 OAuth 자격정보 자체는 삭제하지 않습니다. 계정 연결을 완전히 해제하려면 `계정 연결 해제`를 사용합니다.

## 일반 AI 기능에서 Codex를 안전하게 사용하는 방법

오른쪽 Codex 패널은 프로젝트 파일 변경이 가능한 전용 코딩 Agent UX를 유지합니다.

반면 AgentStudio의 일반 Provider fallback으로 Codex를 호출할 때는 별도의 **ephemeral + read-only** thread를 사용합니다.

- `ephemeral: true`
- `approvalPolicy: never`
- thread sandbox: `read-only`
- turn sandboxPolicy: `readOnly` + `networkAccess=false`
- Codex `UserInput` text payload: `text_elements: []` 포함 (현재 app-server v2 스키마 호환)

따라서 Agent 설계 인터뷰나 일반 LLM 응답을 만들기 위한 Codex fallback이 프로젝트 파일을 직접 바꾸지 않습니다. 파일 변경은 기존 AgentStudio 변경 제안/적용 흐름 또는 오른쪽 Codex 전용 패널에서 수행합니다.

## Codex 남은 사용량

Codex app-server가 계정의 rate-limit 데이터를 제공하는 경우 시스템 설정에서 다음 정보를 표시합니다.

- 1차/2차 rate window의 사용률을 기준으로 계산한 남은 비율
- reset 시각
- 개별 limit이 있는 경우 remaining percent
- credits 정보가 제공되는 경우 balance / unlimited 상태
- reset credit 수가 제공되는 경우 available count

요금제나 app-server 버전에 따라 일부 항목이 제공되지 않을 수 있습니다. AgentStudio는 반환되지 않은 월간 크레딧/사용량을 추정해서 만들어내지 않고 **사용량 정보 없음**으로 표시합니다.

## 주요 코드 위치

- `backend/app/services/model_router.py`: Adaptive Provider Router
- `backend/app/services/codex_app_server_service.py`: Codex app-server/OAuth/rate-limit/read-only fallback
- `backend/app/services/llm_runtime_status_service.py`: IDE AI 모드 상태
- `backend/app/services/settings_service.py`: Provider/Codex 설정 저장 및 검증
- `frontend/src/components/codex/CodexSettingsPanel.tsx`: 설정 화면의 Codex 계정/사용량 UI
- `frontend/src/components/codex/CodexPanel.tsx`: 오른쪽 Codex 패널

## 회귀 검사

- `python backend/validate_codex_protocol_contract.py`
- `python backend/validate_adaptive_ai_provider_contract.py`
- `node frontend/validate_frontend_contracts.cjs`
- `python -m compileall backend/app`
