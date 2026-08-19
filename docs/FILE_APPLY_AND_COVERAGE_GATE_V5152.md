# v5.152 File Apply Verification + Requirement Coverage Gate

## 1. 개발 시작 즉시 실행 결과 탭 이동
`개발 시작` 클릭 직후 RUN 탭으로 이동합니다.
Progress / 완료 / 실패 / 진단 자료를 같은 화면에서 확인합니다.

## 2. Workflow Preview 설계 재사용
개발 시작 시 `targetWorkflowPreview` 전체를 `design_bundle`로 Backend에 전달합니다.
Agent Factory는 더 이상 짧은 최초 요청만으로 요구사항을 다시 설계하지 않습니다.

이 변경으로 인터뷰에서 확정한:
- React + Vite
- FastAPI + Uvicorn
- MCP local stdio
- OpenAI gpt-4o-mini
- Ollama 전환 가능
등을 개발 단계까지 유지합니다.

## 3. Requirement Coverage Gate
File Plan 직후 실제 코드 생성 전에 요구사항 Coverage를 검사합니다.

FastAPI 요구 시:
- backend/app/main.py
- router
- service
- config

React 요구 시:
- frontend/package.json
- frontend/src/main.jsx
- frontend/src/App.jsx
- frontend/src/services/api.js

MCP 요구 시:
- MCP Client
- Transport
- Server

stdio 요구 시 Transport 계획에 stdio가 명시되어야 합니다.

누락 시:
`REQUIREMENT_COVERAGE_FAILED`

코드 생성으로 진행하지 않습니다.

## 4. 실제 File Apply 검증
LLM Patch의 상대경로는 project_root 기준 절대경로로 변환합니다.
쓰기 직후:
1. exists/is_file
2. size
3. read-back 내용 일치
를 확인합니다.

검증 성공 후에만:
`created=true`, `verified=true`

검증 실패 시:
`FILE_APPLY_FAILED`

## 5. 동일 실패 반복 차단
동일한 missing/placeholder/coding-style 오류가 다시 발생하면:
`BUILD_ARTIFACT_STALLED`

같은 code_generation을 반복 호출하지 않습니다.

## 6. Architecture Contract 검사
stdio 요구 프로젝트에서 Flask/requests/localhost:5000/app.run 패턴을 감지하면 실패합니다.
gpt-4o-mini 확정 상태에서 `model_name='gpt-4'` 직접 하드코딩도 실패합니다.
