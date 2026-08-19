# THEANOVA AgentStudio Coding Style Architecture

## 목적

사용자가 강의자료, 개발 가이드, 코드 예제를 단계별로 제공하면
AgentStudio가 이를 단순한 거대 Prompt로 저장하지 않고
실제 에이전트 프로그램 생성에 적용할 수 있는 규칙으로 구조화합니다.

## 구조

```text
사용자 코딩 스타일 자료
        ↓
Coding Style Analyzer
        ↓
Coding Rule Registry
        ├─ required
        ├─ recommended
        ├─ conditional
        ├─ template_candidate
        └─ reference_only
        ↓
Rule Selector
        ↓
관련 Code Template
        ↓
LLM File / Project Coding
        ↓
Coding Rule Validator
        ↓
파일 생성·수정·테스트
```

## 구현 파일

- `backend/app/data/coding_style/rules.json`
- `backend/app/data/coding_style/templates.json`
- `backend/app/data/coding_style/sources/`
- `backend/app/services/coding_style_registry.py`
- `backend/app/services/coding_style_analyzer.py`
- `backend/app/services/coding_rule_selector.py`
- `backend/app/services/code_template_registry.py`
- `backend/app/services/coding_rule_validator.py`

## API

- `GET /api/coding-style/rules`
- `POST /api/coding-style/analyze`
- `POST /api/coding-style/validate`

## LLM 통합

`/api/ai/edit`
- 파일 단위 요청에 관련된 Coding Rule을 선택해 Prompt에 삽입

`/api/ai/project-edit`
- 프로젝트 단위 요청에 관련된 Coding Rule을 선택해 Prompt에 삽입

따라서 이후 사용자가 코딩 스타일 자료를 추가할 때
GPT 대화 내용에만 의존하지 않고 프로젝트 내부의 Registry를 읽어 적용합니다.

## 초기 등록 자료

`module_1_6_1_7`

초기 핵심 규칙:
- SystemMessage / HumanMessage 역할 분리
- dotenv 사용
- API Key 하드코딩 금지
- .env Git 제외
- LangChain 기본 인터페이스
- usage_metadata 관찰 지원
- LangSmith 추적 가능 구조
- 불필요한 LangChain 추상화 최소화
- Colab 전용 코드를 로컬 실행 구조로 이식
- 실제 프로젝트는 역할별 파일 + Git 이력 사용
- 교육 예시 모델명을 스타일에 고정하지 않음


## v5.108 추가 규칙 — Prompt Engineering

입력 자료: 모듈 2-1 ~ 2-5

추가 적용:
- RCIF(Role / Context / Instruction / Format)
- 구체적인 Role
- 명확한 행동 Instruction
- 출력 Format 계약
- Zero-shot / Few-shot 상황별 선택
- Few-shot 출력 포맷 일치
- Prompt Iteration
- 비교 실험 조건 통제
- ChatPromptTemplate 재사용
- 단일 중괄호 및 변수명 일치
- format_messages 기반 템플릿 검증
- 정상/엣지/비정상 입력 테스트
- Few-shot 메시지 배치
- partial_variables 활용
- 비공개 내부 추론 출력에 의존하지 않는 서비스 설계

교육용 예제와 실제 AgentStudio 코딩 규칙은 분리합니다.


## v5.110 추가 규칙 — LCEL / Pydantic / Structured Output

입력 자료: 모듈 3-1 ~ 3-4

핵심 적용:
- LCEL prompt | llm | parser
- invoke / batch / stream / async 실행 구분
- RunnableParallel
- RunnableLambda
- RunnableBranch
- TypedDict vs Pydantic 경계 구분
- Pydantic Field(description=...) + 타입/범위 제약
- Literal 기반 닫힌 분류
- 분류 불가용 기타/Unknown 경로
- with_structured_output 우선
- structured output 체인에서 중복 Parser 제거
- try-except + fallback
- OutputFixingParser는 비용상 최후 수단
- 중첩 Pydantic 모델
- model_dump()
- field_validator / model_validator
- ValidationError 테스트

교육용 제출/스크린샷/LangSmith 링크 제출 항목은 코딩 규칙에서 제외합니다.


## v5.111 추가 규칙 — Function Calling / Tool Design

추가 적용:
- AI는 결정, 실제 Tool 실행은 코드
- @tool 타입 힌트
- Tool docstring = 실행 명세
- 사용 시점 / 사용하지 말 것 / Args / Returns
- bind_tools 명시 등록
- AIMessage 이력 보존
- ToolMessage.tool_call_id 연결
- 빈 tool_calls 분기
- 다중 Tool 이름 Registry
- 복수 tool_calls 처리
- Tool 예외 격리
- Mock → 실제 API Tool 전환
- 외부 API 결과 정제
- Rate Limit / 호출 비용 관리
- eval/exec 기반 Tool 금지
- Tool Routing 테스트
- tool_choice 제한적 사용
- MCP Tool description 품질
- Function / Tool / API / DB / MCP 실행 수단 선택
- Tool 입력 스키마 검증

## v5.113 추가 — Agent Factory 기본 제작 Workflow

AgentStudio의 정체성을 일반 코드 편집기가 아닌 **에이전트를 만들어주는 상위 Agent Factory**로 고정합니다.

제작 Workflow:

`요구사항 분석 → 필요 기능 정의 → Tool/MCP 판단 → Agent 구조 설계 → 대상 Agent Workflow 설계 → 프로젝트 파일 생성 → 코드 작성 → 환경설정 → 실행/테스트 → 오류 수정 → 완성`

중요한 구분:
- AgentStudio Workflow: 에이전트를 분석·설계·생성·검증하는 제작 공정
- 생성 대상 Agent Workflow: 완성된 Agent가 실제 업무를 수행하는 순서

정책 파일:
- `backend/app/data/coding_style/agent_factory_policy.json`
- `backend/app/services/agent_factory_policy.py`

적용 위치:
- `/api/ai/project-edit` 프로젝트 단위 생성 프롬프트
- `agent_builder.build_plan()` Agent 설계 프롬프트

코딩 스타일 Registry와 Agent Factory 제작 정책은 분리하여 관리합니다. 코딩 스타일은 코드 작성 방법을 결정하고, Agent Factory 정책은 무엇을 어떤 제작 단계로 설계할지를 결정합니다.


## v5.114 추가 규칙 — Async Programming

입력 자료: 모듈 6-1 ~ 6-4

핵심 적용:
- async def 내부 동기 invoke/batch/stream 금지
- ainvoke / abatch / astream 우선
- time.sleep 금지, asyncio.sleep 사용
- await 누락 방지
- I/O Bound / CPU Bound 분리
- asyncio.gather 병렬 처리
- gather 실패 정책 명시
- Semaphore / max_concurrency
- Rate Limit 대응
- 지수 백오프
- asyncio.run 사용 위치 제한
- create_task 제한적 사용
- async 코드 정적 검증

교육 예시의 특정 RPM/TPM/고정 Semaphore 값은 규칙으로 고정하지 않고
환경/Provider에 따라 설정하도록 일반화합니다.


## v5.115 추가 규칙 — FastAPI Structure

입력 자료: 모듈 7-1 ~ 7-5

추가 적용:
- main / routers / services / schemas 책임 분리
- main → routers → services 단방향 의존성
- APIRouter + include_router
- REST 자원 중심 URL
- HTTP Method 의미 준수
- Path / Query / Body 역할 분리
- Query 검증 제약
- Pydantic Body / response_model
- /health
- 요청 로깅
- CORS 최소 Origin
- 중앙 Settings / pydantic-settings
- .env.example / requirements.txt
- devcontainer / PYTHONPATH / forwardPorts
- uvicorn 실행 타깃 검증
- --reload 개발 전용
- 422 Validation 테스트
- AgentStudio FastAPI 프로젝트 생성 Profile

교육용 팀 제출/스크린샷/특정 포트·모델·Python 버전 예시는 고정 규칙으로 만들지 않고
설정 가능한 값으로 일반화합니다.
