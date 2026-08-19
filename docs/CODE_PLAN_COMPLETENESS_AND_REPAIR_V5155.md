# v5.155 Code Plan Completeness + Targeted Repair

## 이번 실패에서 확인된 문제
- File Plan 13개 중 Code Plan은 9개만 생성
- React/Vite 파일 6개 누락
- MCP stdio 요구를 Flask HTTP로 구현
- gpt-4 직접 하드코딩
- 실패 후 최초 Code Plan을 다시 반복하여 같은 실패 발생
- `.env.example`은 실제 생성됐지만 진단 Scanner가 산출물로 집계하지 못함
- 인터뷰의 FastAPI/처리제한 요구가 개발 design bundle에서 약화됨

## 수정

### 1. Code Plan Completeness Gate
required=true File Plan과:
- 실제 기존 프로젝트 파일
- 생성 예정 changes[]
의 합집합을 비교합니다.

누락이 있으면 File Apply 전에 보강 Plan을 한 번 생성합니다.
그래도 누락되면:
`CODE_PLAN_INCOMPLETE`

### 2. Targeted Repair
Build Artifact Validation 실패 후 최초 Code Plan을 반복하지 않습니다.

다음만 Repair 대상으로 전달합니다.
- missing_files
- architecture_errors
- placeholder_files
- coding_style_errors

Repair Plan이 대상 파일을 모두 포함하지 않으면:
`REPAIR_PLAN_INCOMPLETE`

### 3. Architecture Validation 확대
File Plan에 포함된 파일뿐 아니라 실제 프로젝트의 전체 생성 소스 파일을 검사합니다.

검사:
- MCP stdio인데 Flask/requests/localhost HTTP 사용
- gpt-4 직접 하드코딩
- FastAPI 필수 계층 누락
- React 필수 실행 파일 누락

### 4. Interview Requirement 보존
Workflow Preview 응답에:
- full_request
- interview_context
- interview_messages
- confirmed_requirements
- file_plan
- environment_plan
- settings_plan
을 보존합니다.

개발 시작 시 최신 confirmed requirements와 전체 interview를 다시 merge합니다.

### 5. Artifact Scanner
`.env.example`, `.gitignore`, requirements.txt, package.json 등 특수 설정 파일도
실제 Agent 산출물로 집계합니다.
