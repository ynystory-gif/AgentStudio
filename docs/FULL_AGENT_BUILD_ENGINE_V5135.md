# v5.135 Full Agent Build Engine

## 문제

기존 Code Generator는 전체 설계를 전달받아도 LLM이 `service.py` 한 파일만 생성하거나
핵심 기능을 placeholder로 남겨도 다음 단계로 넘어갈 수 있었습니다.

## 개선

### 1. 전체 설계 산출물 강제 소비

Code Generator에 다음을 함께 전달합니다.

- requirement_spec
- capability_plan
- tool_mcp_plan
- agent_architecture
- target_agent_workflow
- file_plan
- settings_plan / schema / UI plan
- Coding Style Registry
- 신규 파일 절대경로 Manifest
- Debug/검증 실패 Context

### 2. 실행 가능한 최소 Project Artifact Manifest

요구사항에 따라 자동 보강:

- FastAPI backend entrypoint/router/schema/service/LLM service/config/tests
- MCP client/transport/server/tool/tests
- React/Vite entrypoint/page/API client/package
- Settings Generator 파일
- README / .env.example

### 3. Coding Style 실제 적용

`create_patch()` 자체가 Coding Rule Selector를 호출합니다.

따라서 사용자가 등록한 rules.json의
required/recommended/conditional 규칙을 System Prompt에 직접 삽입합니다.
관련 Code Template도 선택해서 구조 참고로 전달합니다.

### 4. Build Artifact Validation Gate

코드 생성 이후 다음을 검사합니다.

- file_plan required 파일 실제 존재
- 핵심 코드에 TODO/placeholder/stub 없음
- Coding Style Validator Error 0
- Settings Generator 산출물 검증

실패하면 Debug Context에 누락/위반 내용을 넣고 Code Generation으로 돌아갑니다.

### 5. Completion Gate

Artifact 검증이 성공하지 않으면 `COMPLETED` 상태가 될 수 없습니다.
이후 기존 Test 단계까지 통과해야 최종 Review에서 COMPLETED 처리됩니다.
