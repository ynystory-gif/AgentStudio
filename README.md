# THEANOVA AgentStudio v3

에이전트 스튜디오는 **AI Agent + MCP 프로그램 전문 코딩 에이전트 IDE**입니다.

## v3 추가 사항
1. 자동 Debug Loop
2. Project Analyzer / 관련 파일 자동 탐색
3. FastAPI lifespan 기반 LangGraph PostgreSQL 영속 Runtime
4. MCP Registry 자동 갱신 + Trust/Risk 기반 승인 정책
5. PostgreSQL + pgvector 장기 Memory

일반 Secret Manager는 별도 기능이지만, SQL Workspace에 저장하는 DB 비밀번호는 Windows에서 DPAPI 현재 사용자 범위로 암호화 저장합니다.


## v5.239 Multi Database Connection Profiles
- 프로젝트 하나에 MSSQL/PostgreSQL/Oracle/SQLite3 연결을 종류별 제한 없이 여러 개 등록할 수 있습니다.
- 같은 MSSQL도 운영/개발/테스트처럼 연결 이름을 달리해 여러 개 저장할 수 있습니다.
- 여러 연결을 동시에 유지하고, SQL Workspace에서 현재 실행 대상으로 사용할 연결을 선택할 수 있습니다.
- Host/Port/Database/Service Name/User/Driver 등 연결 정보는 LOCALAPPDATA의 AgentStudio 영속 설정에 저장됩니다.
- Windows의 DB 비밀번호는 평문으로 저장하지 않고 DPAPI(Current User)로 암호화합니다.
- v5.238 이전의 DB 종류별 단일 연결 설정은 처음 읽을 때 다중 연결 프로필 구조로 호환됩니다.

## 기술 스택
- FastAPI
- PostgreSQL + pgvector
- React + Monaco Editor
- LangChain + LangGraph
- LangSmith
- OpenAI API / Ollama
- Tavily
- MCP
- WebSocket / Async Jobs

## 실행
PostgreSQL/pgvector를 Docker로 띄울 경우:
```powershell
docker compose up -d postgres
```

그 다음:
```text
SYSTEM_ADMIN.cmd
```

> v5.276부터 사용자가 직접 실행하는 시스템 관리 진입점은 `SYSTEM_ADMIN.cmd` 하나만 사용합니다. `SYSTEM_ADMIN.ps1`은 `SYSTEM_ADMIN.cmd`가 내부적으로 호출하는 구현 파일입니다.

## UTF-8 CMD
모든 CMD는 다음 기준을 사용합니다.
```bat
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
```

## 주요 환경설정
- `MAX_DEBUG_ITERATIONS=3`
- `MCP_REGISTRY_REFRESH_SECONDS=15`
- `MEMORY_EMBEDDING_PROVIDER=ollama`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`

Ollama Memory를 사용할 경우 embedding 모델이 로컬에 설치되어 있어야 합니다.


## v4 LLM 비용 최적화 라우팅
- Ollama: 프로젝트 탐색, Tool 분류, 로그 1차 분석, 간단한 질문, Memory 정리
- GPT-5 mini: 요구사항 분석, 코드 생성, Patch, 일반 디버깅
- UI는 AUTO Router를 기본 사용합니다.


## v4.1 CMD 안정화
- `start /D` 방식으로 Backend/Frontend 시작 경로 처리
- 경로 따옴표 충돌 수정
- Python 3.12 우선 탐색 후 일반 Python fallback
- Frontend 준비 상태 최대 30초 확인
- 성공/실패 모두 메인 CMD 창 유지
- `logs/system_manager.log` 기본 로그 생성
- UTF-8 (`chcp 65001`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`) 유지


## v4.2 Frontend 설치 안정화
- npm `allow-scripts`로 esbuild postinstall이 차단되는 경우 자동 처리
- `npm approve-scripts esbuild` 우선 시도
- 자동 승인이 불가능하면 package.json의 `allowScripts.esbuild=true` 설정
- npm install 재시도
- `npx --no-install esbuild --version`으로 실제 설치 검증
- 필요 시 `npm rebuild esbuild`
- `npm run build`로 React/Vite 사전 빌드 검증
- `npm audit fix`는 의존성 변경 위험 때문에 자동 실행하지 않음
- 실패 단계별 메시지와 로그 유지


## v4.3 시스템 관리 설정 폼
시스템 관리 화면에서 다음 설정을 직접 입력/저장/연결 테스트할 수 있습니다.
- PostgreSQL / LangGraph DB
- OpenAI API Key / 모델
- Ollama URL / 모델
- Tavily API Key
- LangSmith API Key / Project / Tracing
- Ollama/OpenAI 자동 모델 라우팅
- 허용 프로젝트 경로
- Sandbox 경로
- 명령 Timeout
- 자동 승인 Risk Level
- Debug 반복 횟수
- Project Analyzer 최대 파일
- MCP Timeout / Registry 갱신 주기

Secret 필드는 저장된 값을 화면에 다시 노출하지 않으며, 빈 값으로 저장하면 기존 Key를 유지합니다.
일부 Backend 런타임 설정은 저장 후 Backend 재시작 시 완전히 적용됩니다.


## v4.4 포트 자동 관리
- Backend는 8000부터 사용 가능한 포트를 자동 탐색합니다.
- Frontend는 5173부터 사용 가능한 포트를 자동 탐색합니다.
- 실제 선택된 포트를 `frontend/public/runtime-config.js`에 자동 기록합니다.
- React는 더 이상 Backend 8000 포트에 고정되지 않습니다.
- WebSocket도 실제 Backend 포트를 사용합니다.
- CORS는 localhost / 127.0.0.1의 개발 포트를 허용합니다.
- CMD는 실제 Frontend 포트의 `/system` 페이지를 엽니다.
- Backend `/api/health`와 Frontend `/system`을 각각 실제 응답 확인한 뒤 완료로 판단합니다.


## v4.5 PYTHONUTF8 오류 수정
Windows CMD에서 `set PYTHONUTF8=1 && ...` 형식은 `&&` 앞의 공백이 환경변수 값에 포함되어
`PYTHONUTF8` 값이 `1 `로 설정될 수 있습니다. Python은 `PYTHONUTF8`에 `0` 또는 `1`만 허용하므로
`Fatal Python error: preconfig_init_utf8_mode: invalid PYTHONUTF8 environment variable value`가 발생합니다.

v4.5에서는 다음처럼 안전한 SET 문법을 사용합니다.

```bat
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
```

Backend 별도 CMD 실행 명령에서도 동일하게 수정했습니다.

## v4.6 PostgreSQL 18 Windows pgvector 자동 설치
시스템 관리 화면에 `PostgreSQL 18 x64 pgvector 다운로드 및 설치` 버튼을 추가했습니다.
PostgreSQL 18 설치 경로를 자동 탐지하고, GitHub 커뮤니티 Windows 빌드를 다운로드한 뒤
UAC 관리자 권한으로 `vector.dll`, `vector.control`, SQL 파일을 설치하고
`CREATE EXTENSION IF NOT EXISTS vector`까지 실행합니다.


## v4.7 pgvector 설치 Job 안정화
`Failed to fetch` 문제를 줄이기 위해 pgvector 설치를 동기 HTTP 요청에서 비동기 Job으로 변경했습니다.

동작:
1. 버튼 클릭
2. Backend가 즉시 Job ID 반환
3. 다운로드/압축검사/UAC 설치/CREATE EXTENSION은 Background Job에서 처리
4. WebSocket으로 진행률과 상태를 UI에 실시간 표시
5. 실패 시 Python traceback을 UI에서 확인 가능
6. 성공 시 pgvector 테스트 자동 재실행

PG18 Windows release 조회는 우선 `0.8.6_18` tag를 확인하고, 실패하면 release 목록으로 fallback합니다.

## v4.8 Frontend 문자열 오류 수정
`App.jsx`의 pgvector 설치 확인창 문자열에 실제 줄바꿈이 작은따옴표 문자열 내부로 들어가면서
Vite/esbuild의 `Unterminated string literal` 오류가 발생하던 부분을 수정했습니다.
확인창 문구는 여러 줄을 안전하게 처리하는 JavaScript template literal로 변경했습니다.


## v4.9 Background Job 실행 수정
- `JobManager.create()`가 실제 `asyncio.create_task()`를 생성하도록 재구성
- QUEUED → RUNNING 상태 전환 보장
- pgvector 설치 Job 중복 생성 방지
- `/api/jobs/{job_id}` 상태 조회 API 추가
- WebSocket 누락 시에도 1초 간격 polling으로 진행 상태 복구
- 같은 상태가 오래 유지되면 `응답 대기 중` 메시지 표시
- 성공/실패/취소 상태에서 설치 버튼 자동 해제


## v5.0 PostgreSQL 18 설치 경로 수정
시스템 관리에 `PostgreSQL 18 설치 경로` 입력란을 추가했습니다.
현재 PC에서는 `<PostgreSQL 18 설치 경로>`을 입력하면 됩니다.
수동 입력 경로를 최우선으로 사용하며 C:~Z: 자동 탐색도 강화했습니다.


## v5.1 Windows ZIP 파일명 깨짐 수정
Windows 압축 해제 프로그램에 따라 한글 CMD 파일명이 깨지는 문제를 피하기 위해
기준 실행 파일명을 ASCII 영문으로 변경했습니다.

기준 실행 파일:
`SYSTEM_ADMIN.cmd`

CMD 파일 내용은 UTF-8로 유지하며 다음 설정을 사용합니다.

```bat
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
```

앞으로 AgentStudio의 시스템 설치/설정/실행 진입점은 `SYSTEM_ADMIN.cmd` 하나를 기준으로 사용합니다.


## v5.2 PostgreSQL 설치 경로 직접 검증
pgvector 설치 전에 `PostgreSQL 경로 확인` 버튼으로 다음을 검증합니다.

- 입력 경로 정규화
- `bin\psql.exe` 존재 확인
- `psql --version` 실행
- PostgreSQL 18 여부 확인

현재 PC 권장 입력:
`<PostgreSQL 18 설치 경로>`

브라우저 또는 `.env`에서 `F:\\Program Files\\PostgreSQL\\18`처럼 중복 백슬래시가 들어와도 자동 정규화합니다.


## v5.3 PostgreSQL 경로 저장 방식 변경
- PostgreSQL 설치 경로 하드코딩 제거
- 시스템 관리 화면에서 사용자가 직접 경로 입력
- `PostgreSQL 경로 저장` 버튼으로 `.env`의 `POSTGRESQL18_ROOT`에 저장
- 다음 실행 시 저장된 경로 자동 로드
- pgvector 설치/경로 확인은 현재 입력값 또는 저장값을 사용
- 특정 드라이브(C:, F: 등)나 `Program Files\PostgreSQL\18` 경로를 코드에 고정하지 않음


## v5.4 PostgreSQL 18 버전 판정 수정
기존에는 `psql --version` 결과에 `PostgreSQL 18` 문자열이 정확히 포함되어야 통과했습니다.

Windows PostgreSQL 18.4의 실제 출력:
`psql (PostgreSQL) 18.4`

이 형식도 정상적으로 인식하도록 정규식으로 major version을 추출해서 판정하도록 수정했습니다.


## v5.5 기존 AgentStudio 자동 종료 후 시작
`SYSTEM_ADMIN.cmd` 실행 시 새 서비스를 시작하기 전에 기존 AgentStudio 프로세스를 정리합니다.

정리 대상:
- 현재 AgentStudio 프로젝트 경로에서 실행된 Uvicorn/Python
- 현재 AgentStudio 프로젝트 경로에서 실행된 Node/Vite/npm dev
- 이전 `runtime-config.js`에 기록된 AgentStudio Backend/Frontend 포트를 사용 중인 관련 프로세스

다른 프로젝트에서 실행 중인 Python/Node 프로세스를 무조건 종료하지 않도록
프로젝트 경로와 명령줄을 함께 확인합니다.

실행 순서:
기존 AgentStudio 확인 → 관련 프로세스 종료 → 사용 가능한 포트 탐색 → Backend/Frontend 새로 시작


## v5.6 pgvector 버전 검사 오류 수정
`pgvector_installer.py`에서 PostgreSQL 버전 문자열을 정규식으로 검사할 때
`re` 모듈 import가 누락되어 발생하던 `NameError: name 're' is not defined` 오류를 수정했습니다.


## v5.7 SYSTEM_ADMIN 자기 종료 문제 수정
v5.5의 기존 프로세스 정리 로직이 현재 실행 중인 `SYSTEM_ADMIN.cmd`의 cmd.exe까지
종료 대상으로 잡을 수 있는 문제를 수정했습니다.

이제 종료 대상은 다음으로 제한합니다.
- 현재 AgentStudio 프로젝트의 Python/Uvicorn
- 현재 AgentStudio 프로젝트의 Node/Vite
- 이전 runtime-config 포트를 점유한 Python/Node

현재 `SYSTEM_ADMIN.cmd` 프로세스(cmd.exe)는 종료하지 않습니다.


## v5.8 pgvector 설치 모듈 재구성
누적된 부분 수정으로 함수 의존관계가 깨지는 문제를 제거하기 위해
`pgvector_installer.py`를 전체 재작성했습니다.

검증 항목:
- PostgreSQL 경로 저장/검증
- PostgreSQL 18.4 버전 인식
- `_release_from_json` 정의 후 사용
- GitHub release 조회
- ZIP asset 선택
- 다운로드
- ZIP 손상 검사
- vector.dll / vector.control / SQL 탐색
- UAC 관리자 복사
- CREATE EXTENSION vector
- 진행률 callback


## v5.9 실행 전 AgentStudio 전체 종료

`SYSTEM_ADMIN.cmd`를 실행하면 기존 AgentStudio 실행 환경을 모두 종료한 뒤 새로 시작합니다.

종료 대상:
- 이전 `SYSTEM_ADMIN.cmd` 창
- Backend CMD 창
- Backend Uvicorn/Python 프로세스
- Frontend CMD 창
- Frontend Node/Vite/npm 프로세스
- 이전 runtime-config에 기록된 Backend/Frontend 포트의 관련 프로세스

현재 새로 실행한 `SYSTEM_ADMIN.cmd` 자기 자신만 PID로 식별하여 종료 대상에서 제외합니다.

다른 프로젝트의 Python/Node 프로세스는 프로젝트 경로를 확인하여 종료하지 않습니다.


## v5.10 pgvector UAC 권한 오류 수정
관리자 권한 PowerShell이 사용자 Temp 폴더에 만든 `install_result.txt`를
Backend가 다시 읽으면서 발생하던 `PermissionError: [Errno 13] Permission denied`를 제거했습니다.

이제 설치 성공 여부는 다음으로 확인합니다.
- UAC PowerShell 종료코드
- PostgreSQL `lib\vector.dll`
- PostgreSQL `share\extension\vector.control`
- PostgreSQL `share\extension\vector--*.sql`

관리자 권한 결과 파일을 일반 프로세스가 다시 읽지 않습니다.


## v5.11 Backend/Frontend CMD 창 자체 종료

`SYSTEM_ADMIN.cmd` 재실행 시 기존 서버 프로세스뿐 아니라 화면에 열려 있는
다음 콘솔 창 자체도 먼저 닫습니다.

- `AgentStudio Backend`
- `AgentStudio Frontend`

종료 방식:
1. `WINDOWTITLE` 기준 `taskkill /T /F`
2. cmd.exe 명령줄의 Uvicorn/npm/Vite 패턴 fallback
3. 남은 Python/Uvicorn/Node/Vite 프로세스 종료
4. 이전 runtime-config 포트 점유 프로세스 종료
5. 이전 SYSTEM_ADMIN.cmd 종료
6. 새 Backend/Frontend CMD 창 생성

즉 이전 Backend/Frontend 콘솔 창이 남아 있는 상태로 새 창을 추가 생성하지 않습니다.


## v5.12 pgvector DB 활성화 자동화

pgvector 바이너리 설치 뒤 `CREATE EXTENSION vector`도 AgentStudio에서 자동 실행합니다.

시스템 관리 입력:
- PostgreSQL 관리자 사용자
- PostgreSQL 관리자 비밀번호

보안 처리:
- 관리자 비밀번호는 `.env`/DB/로그에 저장하지 않음
- 설치 요청 시 Backend 메모리로만 전달
- 자식 `psql.exe`에 `PGPASSWORD` 환경변수로만 전달
- Job 성공/실패 후 Frontend 비밀번호 입력값 삭제

흐름:
1. pgvector Windows 바이너리 다운로드
2. UAC 관리자 권한으로 PostgreSQL 폴더에 파일 설치
3. PostgreSQL 관리자 계정으로 대상 DB에 접속
4. `CREATE EXTENSION IF NOT EXISTS vector`
5. 설치된 vector 버전 확인
6. 완료


## v5.13 AgentStudio 전용 DB 자동 생성

시스템 관리에서 `theanova_agentstudio` 데이터베이스를 생성부터 권한까지 자동 구성할 수 있습니다.

자동 처리:
1. PostgreSQL 관리자 계정 접속
2. AgentStudio 앱 Role 생성 또는 비밀번호 갱신
3. `theanova_agentstudio` DB 생성 (OWNER = 앱 Role)
4. CONNECT 권한
5. public schema USAGE / CREATE 권한
6. pgvector extension 생성
7. 기존 테이블/시퀀스 권한
8. 기본 테이블/시퀀스 권한
9. 앱 계정으로 최종 접속 확인
10. DATABASE_URL / LANGGRAPH_DATABASE_URL 자동 저장

관리자 비밀번호와 AgentStudio 앱 비밀번호는 UI 작업 중에만 사용하며 별도 평문 설정 필드로 저장하지 않습니다.


## v5.14 DB 생성 시 AgentStudio/LangGraph 테이블까지 자동 초기화

`theanova_agentstudio DB 생성 + 권한 + pgvector 설정` 실행 시 다음을 한 번에 처리합니다.

1. PostgreSQL 관리자 접속
2. AgentStudio 앱 Role 생성/갱신
3. `theanova_agentstudio` DB 생성 또는 OWNER 보정
4. CONNECT / public schema 권한
5. pgvector extension
6. AgentStudio SQLAlchemy 모델 테이블 생성
   - projects
   - conversation_messages
   - requirements
   - mcp_servers
   - tool_registry
   - approval_requests
   - memory_records
   - project_file_index
   - evaluation_records
   - usage_records
   - jobs
7. LangGraph PostgreSQL Checkpointer `setup()` 실행
8. 전체 테이블 목록/개수 확인
9. 앱 계정으로 최종 접속/pgvector/테이블 수 검증
10. DATABASE_URL / LANGGRAPH_DATABASE_URL 저장

DB가 이미 존재하는 경우에도 빠진 테이블은 생성하고 기존 테이블은 유지합니다.


## v5.15 신규 Agent 프로젝트 경로 설정
신규 Agent 생성 시 프로젝트 경로, Cache, Temp, Output, 가상 디렉터리(venv) 경로를 각각 지정할 수 있습니다.

프로젝트 경로는 필수이며, 나머지를 비워두면 자동으로 아래 폴더를 만듭니다.

- `<project_root>\cache`
- `<project_root>\temp`
- `<project_root>\output`
- `<project_root>\venv`

사용자가 별도 경로를 입력하면 해당 경로를 그대로 생성하여 사용합니다.


## v5.16 신규 Agent 공통 모델 경로

신규 Agent 프로젝트 생성 시 `공통 모델 경로(Common Models Path)`를 추가로 지정할 수 있습니다.

지정 가능한 경로:
- 프로젝트 경로
- Cache 경로
- Temp 경로
- Output 경로
- 가상 디렉터리(venv) 경로
- 공통 모델 경로

공통 모델 경로를 비워두면 다음 위치를 자동 생성합니다.

`<project_root>\models`

예를 들어 여러 Agent가 동일 모델을 공유해야 할 경우 사용자가
`<사용자 지정 경로>` 같은 별도 공통 경로를 직접 지정할 수 있습니다.


## v5.17 신규 Agent FastAPI → PostgreSQL 저장

신규 Agent 생성 시 `/api/projects/create-agent` FastAPI를 통해 다음 순서로 처리합니다.

1. 프로젝트/Cache/Temp/Output/Venv/Models 경로 확정
2. 필요한 폴더 생성
3. PostgreSQL `projects` 테이블 중복 경로 확인
4. Project 레코드 저장
5. DB commit
6. 생성된 Project ID 반환

저장 항목:
- name
- root_path
- cache_path
- temp_path
- output_path
- venv_path
- models_path

`GET /api/projects`로 저장된 Agent 프로젝트 목록도 조회할 수 있습니다.


## v5.18 프로젝트 불러오기

신규 Agent 영역에 `불러오기` 버튼을 추가했습니다.

흐름:
1. `불러오기` 버튼 클릭
2. `GET /api/projects`로 PostgreSQL에 저장된 프로젝트 목록 조회
3. 프로젝트 목록 팝업 표시
4. 프로젝트 아이템 클릭
5. `GET /api/projects/{project_id}`로 상세정보 조회
6. 현재 화면에 이름/Project/Cache/Temp/Output/Venv/Models 경로 로드
7. 현재 선택된 Project ID 표시

프로젝트 목록은 FastAPI를 통해 PostgreSQL `projects` 테이블에서 가져옵니다.


## v5.19 UI/UX 재설계
AgentStudio 메인 흐름을 홈 → 신규 Agent 대화형 설계 → 작업공간의 3단계로 재구성했습니다.

- 홈: 신규 생성 / 불러오기 / 사용 방법
- 신규 생성: 질문을 한 번에 하나씩 진행하는 AI 인터뷰
- 우측 Project 구성: 이름/Project/Cache/Temp/Output/Venv/Models 경로
- 고급 경로는 기본 접힘 상태
- 경로 미지정 시 실제 생성될 기본 경로 미리보기
- 프로젝트 생성 성공 시 바로 작업공간 이동
- 불러오기 성공 시 바로 작업공간 이동
- 작업공간: 파일/코드/AI 코딩 Agent/Terminal/MCP/Workflow/Memory


## v5.20 PostgreSQL 경로 하드코딩 제거
PostgreSQL 설치 경로는 PC마다 다를 수 있으므로 특정 C:/F: 드라이브를 고정하지 않습니다.

탐색 순서:
1. 시스템 관리에서 입력한 POSTGRESQL18_ROOT
2. 저장된 POSTGRESQL18_ROOT
3. PATH의 psql.exe
4. Windows Registry의 PostgreSQL 설치 정보


## v5.21 PC 종속 경로 하드코딩 제거

AgentStudio는 노트북/데스크톱마다 드라이브와 설치 위치가 다를 수 있으므로
`C:`, `D:`, `F:`, `G:` 같은 특정 드라이브 경로를 기본값으로 고정하지 않습니다.

변경 사항:
- `ALLOWED_PROJECT_ROOTS` 기본값 비움
- `SANDBOX_ROOT` 기본값 비움
- `POSTGRESQL18_ROOT` 기본값 비움
- Frontend 기본 프로젝트 경로 비움
- 시스템 관리/신규 프로젝트 생성에서 사용자가 입력한 실제 경로 사용
- PostgreSQL 경로는 사용자 입력 → 저장값 → PATH → Registry 순서로 탐색
- 허용 프로젝트 루트가 비어 있으면 빈 문자열을 실제 경로로 잘못 판단하지 않도록 보정

즉 노트북이 C:만 있어도, 데스크톱이 F:/G:를 사용해도 동일 코드로 동작합니다.


## v5.22 Windows PostgreSQL 드라이버 안정화
노트북 테스트에서 psycopg 3 Async + Windows SelectorEventLoop 조합이 정상 접속되는 것을 확인했습니다.

변경:
- SQLAlchemy AsyncEngine: `postgresql+psycopg://`
- 기존 `postgresql+asyncpg://` 설정은 자동 변환
- Uvicorn 실행 전에 Windows SelectorEventLoop 정책 적용
- Backend 진입점: `backend/run_server.py`
- SelectorEventLoop에서 지원되지 않는 asyncio subprocess를 제거하고
  `subprocess.run()`을 `asyncio.to_thread()`에서 실행
- Backend `--reload` 제거


## v5.23 Windows Psycopg SelectorEventLoop 강제 실행

v5.22의 `WindowsSelectorEventLoopPolicy` 방식은 최신 Uvicorn에서
Windows 단일 프로세스 실행 시 ProactorEventLoop로 다시 선택될 수 있어
Psycopg Async 오류가 계속 발생할 수 있었습니다.

v5.23은 Uvicorn의 loop 선택에 의존하지 않습니다.

실행 구조:

```text
SYSTEM_ADMIN.cmd
  ↓
backend/run_server.py
  ↓
asyncio.Runner(loop_factory=SelectorEventLoop)
  ↓
SelectorEventLoop 실제 생성
  ↓
uvicorn.Server(...).serve()
  ↓
FastAPI
  ↓
SQLAlchemy AsyncEngine
  ↓
psycopg 3 Async
  ↓
PostgreSQL
```

Backend 콘솔 시작 시 실제 Event Loop 종류를 표시합니다.

정상:
`Event Loop : _WindowsSelectorEventLoop`

오류:
`ProactorEventLoop`

진단 API:
`GET /api/system/db-runtime`


## v5.24 DB 생성 전에 pgvector 자동 설치

노트북 신규 설치 환경에서는 PostgreSQL은 설치되어 있어도 pgvector 바이너리가 없을 수 있습니다.

이제 AgentStudio DB 생성 순서는 다음과 같습니다.

1. PostgreSQL 18 경로 확인
2. vector.dll / vector.control / vector SQL 파일 존재 확인
3. 없으면 pgvector Windows 바이너리 자동 다운로드/설치
4. 설치 파일 재확인
5. AgentStudio 앱 Role 생성
6. `theanova_agentstudio` DB 생성/OWNER 설정
7. `CREATE EXTENSION vector`
8. public schema 권한
9. AgentStudio SQLAlchemy 테이블 생성
10. LangGraph Checkpointer 테이블 생성
11. 최종 접속 검증
12. DATABASE_URL / LANGGRAPH_DATABASE_URL 저장

또한 DB 초기화 실패 시 Backend 500으로 브라우저에서 `Failed to fetch`만 보이지 않고,
실제 오류 메시지를 JSON으로 반환하도록 수정했습니다.


## v5.25 pgvector Release helper 누락 수정

`latest_pg18_windows_release()`가 호출하는 `_release_from_json()` 함수가
v5.24 설치 모듈에서 누락되어 발생하던 다음 오류를 수정했습니다.

`NameError: name '_release_from_json' is not defined`

추가 검증:
- pgvector installer 내부 helper 정의 여부
- `_release_from_json` 정의 순서
- 전체 Python AST 문법 검사
- 내부 helper 호출 누락 검사


## v5.26 기본 경로 저장 + Ollama 설치

시스템 관리에서 저장:
- 프로젝트 기본 경로
- Cache 기본 경로
- Temp 기본 경로
- Output 기본 경로
- 공용 모델 경로

신규 Agent 생성 시:
사용자 입력 → 시스템 기본 경로 → 프로젝트 하위 기본 폴더 순으로 결정합니다.

Ollama:
- Windows `Ollama 설치` 버튼 추가
- Ollama 공식 Windows install.ps1 사용
- 공용 모델 경로가 있으면 `OLLAMA_MODELS` 사용자 환경변수로 저장
- 공용 모델 경로가 없으면 Ollama 자체 기본 모델 저장 경로 사용


## v5.27 모든 경로 입력에 Windows 폴더 선택 기능

모든 주요 경로 입력칸에 `경로 찾기` 버튼을 추가했습니다.

적용:
- 프로젝트 기본 경로
- Cache 기본 경로
- Temp 기본 경로
- Output 기본 경로
- 공용 모델 경로
- PostgreSQL 18 설치 경로
- 허용 프로젝트 경로
- Sandbox 경로
- 신규 Agent의 Project / Cache / Temp / Output / Venv / Models 경로

동작:
1. `경로 찾기` 클릭
2. Backend가 Windows FolderBrowserDialog 실행
3. 사용자가 폴더 선택
4. 선택 경로가 텍스트 박스에 자동 입력

Windows 폴더 선택창은 `ShowNewFolderButton=True`로 실행하므로
선택 과정에서 새 폴더를 생성할 수 있습니다.


## v5.28 시스템 설정 PostgreSQL 저장

시스템 관리 설정의 기본 저장소를 PostgreSQL로 변경했습니다.

테이블:
`app_settings`

DB 저장 대상:
- 기본 Project / Cache / Temp / Output / Common Models 경로
- Ollama 설정
- OpenAI 설정
- Tavily 설정
- LangSmith 설정
- LLM 라우팅 설정
- 프로젝트/Sandbox/실행 정책
- MCP Timeout/Registry 설정

Bootstrap 용도로 `.env`에도 유지하는 항목:
- DATABASE_URL
- LANGGRAPH_DATABASE_URL
- POSTGRESQL18_ROOT

이 세 항목은 PostgreSQL에 접속하기 전부터 필요하므로 bootstrap 설정으로 남깁니다.

기존 `.env`의 일반 설정은 Backend 시작 시 `app_settings` 테이블로 1회 자동 이관하며,
시스템 관리의 `설정 DB 이관` 버튼으로 수동 이관도 가능합니다.


## v5.29 모든 DB 저장 FastAPI Gateway 통일

DB 저장 구조를 다음으로 고정했습니다.

`Frontend / Agent / MCP Tool → FastAPI → Service → DatabaseGateway → SQLAlchemy → PostgreSQL`

추가:
- `DatabaseGateway` 공통 DB 쓰기 계층
- 프로젝트 생성도 DatabaseGateway 사용
- 시스템 설정 저장도 DatabaseGateway 사용
- 요구사항 저장 API
- 대화 기록 저장 API
- 사용량 저장 API
- DB Write Policy 진단 API
- Frontend 직접 PostgreSQL 연결 금지 정책 문서

Frontend에는 PostgreSQL 드라이버/SQLAlchemy/DB 세션을 두지 않습니다.
DB 계정/비밀번호 역시 Backend 밖으로 노출하지 않습니다.


## v5.30 DB 미등록 기존 프로젝트 불러오기/분석

`불러오기` 화면을 두 가지 모드로 확장했습니다.

### 1. DB 등록 프로젝트
- PostgreSQL `projects` 목록 조회
- 항목 클릭
- 저장된 프로젝트 정보 로드
- 작업공간 열기

### 2. DB 미등록 기존 프로젝트
- `경로 찾기`로 기존 프로젝트 폴더 선택
- FastAPI `/api/projects/analyze-external` 호출
- 프로젝트 구조/주요 파일/기술 스택/진입점 분석
- DB 등록 없이 작업공간에서 파일 분석/수정 가능
- 필요 시 `DB에 등록` 버튼으로 projects 테이블에 등록

DB 미등록 프로젝트 분석 역시 Frontend에서 파일시스템을 직접 읽지 않고
FastAPI를 통해 Backend가 프로젝트 폴더를 분석합니다.


## v5.31 기존 프로젝트 분석 → DB 자동 저장 → 프로젝트 구성 노출

DB에 없는 기존 프로젝트를 선택하면 다음 흐름으로 동작합니다.

1. 기존 프로젝트 경로 선택
2. FastAPI `/api/projects/analyze-external`
3. Backend 프로젝트 구조/기술 스택/진입점/주요 파일/MCP Tool 분석
4. `projects` 테이블 자동 등록
5. `project_analyses` 테이블에 분석 결과 저장
6. 프로젝트 ID 반환
7. 신규 Agent 설계 화면으로 이동
8. 오른쪽 프로젝트 구성 영역에 저장 정보 자동 표시

저장 분석 항목:
- 프로젝트 요약
- 기술 스택
- 실행 진입점
- 주요 파일
- MCP/Tool
- 구조 정보
- 원본 분석 JSON

프로젝트를 나중에 DB 목록에서 다시 불러와도 `project_analyses` 정보를 함께 조회해 표시합니다.


## v5.32 기존 프로젝트 분석 Progress + 자동 작업공간 이동

기존 프로젝트 분석을 동기 HTTP 호출에서 Background Job으로 변경했습니다.

진행 단계:
- 5%: 프로젝트 경로 확인
- 15%: 파일 구조 스캔
- 40%: 기술 스택/주요 파일 분석
- 70%: 분석 결과 정리
- 82%: projects DB 저장
- 90%: project_analyses DB 저장
- 98%: 저장 결과 검증/작업공간 준비
- 100%: 완료

Frontend는 `/api/jobs/{job_id}`를 polling하여 진행률을 표시합니다.

성공 시:
1. projects / project_analyses DB 저장
2. Project ID 확인
3. 분석 결과 UI state 반영
4. 파일 목록 로드
5. 프로젝트 불러오기 Dialog 닫기
6. 작업공간으로 자동 이동

실패 시:
진행률 영역이 FAILED 상태로 바뀌며 Backend Job의 실제 오류 메시지를 표시합니다.


## v5.33 프로젝트 분석 호출 오류 수정 + 실패 로그 전체 경로

v5.32 실패 원인:
- `local_project_summary(root, request)` 함수에 존재하지 않는 `project_root=` 키워드를 전달함
- 또한 다음 단계의 `scan_project(root)`도 v5.32 호출부가 실제 시그니처와 맞지 않았음

수정된 호출:
- `await local_project_summary(root, req.request)`
- `await scan_project(root)`

Job 실패 로그:
- 모든 Background Job 예외 발생 시 traceback을 파일로 저장
- 기본 경로: `backend/logs/jobs`
- 실제 절대 로그 경로를 Job result의 `log_path`로 Frontend에 전달
- 분석 실패 화면에 실패 원인 / 전체 로그 경로 / 상세 Traceback 표시


## v5.34 사용자가 선택한 외부 프로젝트 동적 허용

기존 오류:
`PermissionError: 허용된 프로젝트 경로 밖입니다`

원인:
외부 프로젝트 분석이 기존 `ALLOWED_PROJECT_ROOTS`만 검사했기 때문에,
사용자가 폴더 선택기로 명시적으로 선택한 프로젝트도 차단되었습니다.

수정:
- 특정 C:/D:/F:/G: 경로 하드코딩 없음
- 사용자가 분석/불러오기/생성한 프로젝트 루트를 현재 Backend 세션에 동적 등록
- 등록된 프로젝트 루트의 하위 경로만 파일 읽기/쓰기/명령 실행 허용
- `Path.relative_to()` 기반 containment 검사 사용
- 문자열 `startswith()` 방식 제거
- 상위 폴더 및 다른 프로젝트로 빠져나가는 경로 접근은 계속 차단
- DB에 저장된 프로젝트를 다시 불러올 때도 해당 root를 동적 등록

진단:
`GET /api/system/project-roots`


## v5.35 Source-only 프로젝트 분석

외부 프로젝트 분석에서 Ollama/OpenAI/LangChain LLM 호출을 제거했습니다.

- 프로젝트 소스 파일만 분석
- 모델 실행/검증/평가 금지
- 소스/설정에 적힌 모델명만 model_references로 수집
- 모델 설치 여부와 관계없이 프로젝트 분석 가능
- 기술 스택 / 실행 진입점 / 주요 파일 / MCP-Agent 관련 소스 / 관련 소스 후보를 로컬 규칙으로 분석
- local_project_summary()는 analysis_mode=SOURCE_ONLY, llm_called=False 반환


## v5.36 텍스트 입력 포커스 소실 수정

증상:
- 텍스트 박스에 한 글자를 입력하면 포커스가 사라짐
- 다음 글자를 입력하려면 다시 클릭해야 함

원인:
`SystemPage`와 `IDE` 함수 내부에서 React 하위 컴포넌트를 매 render마다 새 함수 객체로 정의했습니다.

문제가 있던 구조:
- `PathField`
- `Field`
- `TestResult`
- `HomeScreen`
- `BuilderScreen`
- `WorkspaceScreen`

state가 한 글자 입력마다 갱신되면 부모가 다시 render되고,
React가 위 하위 컴포넌트를 새로운 component type으로 판단하여 unmount/mount했습니다.
이 과정에서 input DOM이 새로 생성되어 focus가 사라졌습니다.

수정:
- 내부 하위 컴포넌트를 ordinary render function으로 변경
- `<Field />` → `renderField(...)`
- `<PathField />` → `renderPathField(...)`
- `<TestResult />` → `renderTestResult(...)`
- `<HomeScreen />` → `renderHomeScreen()`
- `<BuilderScreen />` → `renderBuilderScreen()`
- `<WorkspaceScreen />` → `renderWorkspaceScreen()`

따라서 state가 변경되어도 동일 input DOM reconciliation이 유지되어 연속 입력이 가능합니다.


## v5.37 이미지 기준 UI/UX 재구성

참고 디자인의 핵심 구조를 AgentStudio에 적용했습니다.

- 상단 글로벌 바
- 좌측 아이콘 네비게이션
- 작업공간 좌측 프로젝트 패널
- 중앙 Agent 설계 / 코드 / 실행 / 분석 탭
- 하단 코드 편집기 + Terminal
- 우측 프로젝트 정보 / 기술 스택 / MCP 도구 / 파일
- 하단 연결 상태바

기존 기능은 유지:
신규 생성, DB 프로젝트 불러오기, 외부 프로젝트 분석, 코드 편집,
AI 대화, 터미널, MCP, 시스템 관리, 프로젝트 분석 정보.


## v5.38 다중 터미널

작업공간 Terminal을 다중 탭 구조로 변경했습니다.

기능:
- `+ 터미널` 버튼으로 터미널 무제한 추가
- 각 터미널 별 독립 Command 입력값
- 각 터미널 별 독립 실행 로그
- 터미널 이름 사용자 지정
- 탭 이름 더블클릭 또는 연필 버튼으로 이름 변경
- 터미널별 닫기 버튼
- 마지막 터미널 1개는 유지하여 터미널 영역이 빈 상태가 되지 않도록 처리

예시:
- PowerShell
- Backend
- Frontend
- MCP Server
- Agent Test

명령 실행은 기존 FastAPI `/api/command`를 통해 Backend에서 처리합니다.


## v5.39 DB 설정 저장/런타임 동기화 수정

문제:
- 시스템 관리 화면에서 OpenAI/Tavily/LangSmith API Key를 저장
- `app_settings` 테이블에는 저장됨
- 하지만 `system_status.py`, `connection_test_service.py`, `llm_provider.py` 등은
  `get_settings()`를 사용하여 기존 `.env` 값만 읽음
- 따라서 상태 화면에는 `확인 필요`로 표시됨

수정:
1. FastAPI `/api/settings`를 통해 `app_settings`에 저장
2. 저장 직후 DB 값을 Backend OS runtime environment에 반영
3. `get_settings.cache_clear()` 실행
4. OpenAI/Tavily/LangSmith/Ollama/LLM 라우팅 등 모든 `get_settings()` 사용 코드가 즉시 새 값을 사용
5. Backend 재시작 시 `app_settings` 값을 다시 런타임에 자동 로드
6. API Key 실제 값은 Frontend에 반환하지 않고 `configured/masked` 상태만 반환

따라서 이제:
`UI 입력 -> FastAPI -> PostgreSQL app_settings -> Backend runtime -> 상태/연결테스트`
순서로 일관되게 동작합니다.


## v5.40 하단 LLM 대화형 코드 편집기

중앙 상단 탭 구조는 그대로 유지합니다.

하단 왼쪽 코드 편집기를 다음 구조로 확장했습니다.

- 왼쪽: 실제 Monaco 코드 편집기
- 오른쪽: 선택된 파일 전용 LLM 코드 수정 대화
- 사용자 요청 예:
  - "이 함수에 예외처리 추가"
  - "FastAPI 구조로 리팩터링"
  - "이 오류를 수정"
  - "로그를 남기도록 변경"
- LLM은 현재 선택된 파일 내용과 사용자 요청을 함께 받아 수정안 생성
- 수정안은 즉시 파일에 쓰지 않고 `편집기에 적용` 버튼으로 검토 후 적용
- 실제 저장은 기존 `저장` 버튼 사용

FastAPI:
`POST /api/ai/edit`
→ Coding LLM
→ 수정된 전체 코드 반환
→ Frontend 검토/적용


## v5.41 하단 코드 편집기 제거 + LLM 대화 패널 전환

사용자 의도에 맞게 작업공간 구조를 수정했습니다.

중앙 상단:
- 에이전트 설계
- 코드 편집
- 실행 결과
- 분석 리포트
- 상단 코드 편집기는 기존 그대로 유지

중앙 하단:
- 왼쪽 Monaco 코드 편집기 완전 제거
- 왼쪽 전체 영역을 LLM 코드 수정 대화로 사용
- 오른쪽 다중 터미널 유지

동작:
1. 프로젝트 파일 선택
2. 중앙 상단 코드 편집기에서 실제 코드 확인
3. 하단 LLM 대화 패널에서 수정 요청
4. LLM 수정안 생성
5. `상단 코드 편집기에 적용`
6. 상단 코드 편집기에서 검토
7. 저장

따라서 동일 코드를 보여주는 코드 편집기 중복이 사라집니다.


## v5.42 우측 프로젝트 파일 트리

우측 프로젝트 파일 영역을 단순 텍스트 목록에서 폴더 트리로 변경했습니다.

기능:
- 텍스트 크기 확대
- 폴더/파일 아이콘 표시
- 폴더 접기/펼치기
- 파일 클릭 시 중앙 상단 코드 편집기에서 열기
- `+ 폴더` 버튼으로 신규 폴더 생성
- 선택 항목 `이름 변경`
- 항목 더블클릭으로 이름 변경
- 폴더 선택 후 `+ 폴더`를 누르면 해당 폴더 하위에 생성
- 파일 선택 후 `+ 폴더`를 누르면 파일의 부모 폴더 하위에 생성

파일시스템 변경:
Frontend → FastAPI → local_control → 프로젝트 루트 내부 파일시스템

보안:
동적 허용 프로젝트 루트 내부에서만 생성/이름 변경이 가능합니다.


## v5.43 프로젝트 전체 / 최근 / 즐겨찾기

`projects`에 추가:
- `last_opened_at`
- `is_favorite`

동작:
- 프로젝트 생성 시 last_opened_at 갱신
- DB 미등록 프로젝트 분석 후 DB 저장 시 last_opened_at 갱신
- DB 프로젝트 불러오기 시 last_opened_at 갱신
- 최근 탭: last_opened_at 기준 최신순
- 즐겨찾기 탭: is_favorite=true 프로젝트만 표시
- 프로젝트 항목 ★ 클릭으로 즐겨찾기 설정/해제
- 즐겨찾기는 FastAPI를 통해 PostgreSQL에 저장

API:
- GET /api/projects
- GET /api/projects/{project_id}
- POST /api/projects/{project_id}/favorite

프로젝트를 열거나 분석 완료하면 프로젝트 목록을 즉시 새로고침하여
최근 탭에 바로 반영됩니다.


## v5.44 기존 PostgreSQL 스키마 자동 마이그레이션

v5.43 오류:
`psycopg.errors.UndefinedColumn: projects.last_opened_at 칼럼 없음`

원인:
SQLAlchemy `Base.metadata.create_all()`은 이미 존재하는 테이블에
새 컬럼을 자동 추가하지 않습니다.

v5.43에서는 Project ORM 모델에:
- last_opened_at
- is_favorite

를 추가했지만 기존 PostgreSQL `projects` 테이블에는 실제 컬럼이 없었습니다.

v5.44 수정:
Backend 시작 시 기존 데이터베이스를 삭제하지 않고 아래 SQL을 자동 수행합니다.

ALTER TABLE projects
ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMP NULL;

ALTER TABLE projects
ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE;

따라서 기존 프로젝트/분석 데이터는 그대로 유지됩니다.

수동 진단/보정 API:
POST /api/system/database/migrate


## v5.45 DatabaseGateway 메서드 수정
- touch_project_opened를 DatabaseGateway 클래스 내부 staticmethod로 수정
- set_project_favorite를 DatabaseGateway 클래스 내부 staticmethod로 수정
- routes.py 호출명과 실제 클래스 메서드 일치 검증
- v5.44 DB 스키마 자동 보정 기능 유지


## v5.46 프로젝트 폴더 트리 개선

문제:
- 기존 트리는 파일 목록으로만 트리를 생성하여 비어 있는 신규 폴더가 표시되지 않음
- 프로젝트 파일 카드 아래 공간을 충분히 사용하지 않음
- 폴더 접기/펼치기 표시가 작아서 식별이 어려움

수정:
- GET /api/folders 추가
- Backend가 빈 폴더를 포함한 프로젝트 디렉터리 목록 반환
- Frontend는 files + folders를 합쳐 트리 생성
- 새 폴더 생성 후 즉시 목록 새로고침/선택/부모 펼침
- 우측 프로젝트 파일 영역 높이를 최대 58vh/640px까지 사용
- 접기/펼치기를 큰 + / − 버튼으로 변경
- 파일/폴더 글자와 아이콘 크기 추가 확대


## v5.47 sendChat 화면 렌더 오류 수정

브라우저 오류:
`Uncaught ReferenceError: sendChat is not defined`

원인:
Workspace와 Builder JSX는 `sendChat()`을 사용하고 있었지만,
공통 대화 전송 함수 정의가 누락되어 화면 렌더 단계에서 React가 중단되었습니다.

수정:
- `sendChat()` 공통 함수 복원
- FastAPI `POST /api/chat/interview`와 연결
- 현재 chat history + 사용자 message + provider 전달
- 응답을 assistant message로 chat state에 추가
- Builder의 `sendBuilderAnswer()`는 공통 `sendChat()` 호출
- Workspace Agent 설계 탭의 Enter/전송 버튼도 동일 함수 사용
- 실패 시 화면 전체 중단 대신 대화창에 오류 메시지 표시

참고:
WebSocket `/api/ws` 연결 경고는 별도 상태 연결 문제이며,
화면이 완전히 사라진 직접 원인은 `sendChat` ReferenceError였습니다.


## v5.48 Workspace 미정의 핸들러 수정

브라우저 오류:
`Uncaught ReferenceError: saveFile is not defined`

원인:
UI 재구성 과정에서 JSX 버튼/화면은 남아 있었지만 일부 실행 함수 정의가 누락되었습니다.

수정:
- saveFile() 구현
  - FastAPI POST /api/file/write 사용
  - 선택된 상대 경로를 프로젝트 root와 결합해 실제 파일 저장
  - 저장 성공/실패를 Terminal 로그에 표시
- refreshMcp() 누락 시 구현
  - 현재 Backend의 MCP 조회 API에 연결 가능한 경우 자동 연결
- openFile() 누락 여부 검사 및 보완
- runCmd() 누락 여부 검사 및 보완
- sendChat() 유지

이번 버전은 단일 오류만 고치는 대신 Workspace에서 사용하는 주요 handler 정의를 함께 검사합니다.


## v5.49 좌측 아이콘 화면 라우팅 수정

문제:
4번째 아이콘이 독립 화면을 열지 않고 1번째(Home)와 동일 화면으로 돌아가며,
active 표시도 1번째 아이콘에 적용되는 문제가 있었습니다.

수정:
좌측 아이콘마다 고유 screen 값을 사용합니다.

1. HOME
2. WORKSPACE
3. MCP
4. PROJECTS
5. TOOLS
6. SYSTEM

4번째 아이콘:
- screen='PROJECTS'
- 프로젝트 관리 전용 페이지 표시
- 전체 / 최근 / 즐겨찾기 프로젝트 확인
- 프로젝트 클릭 시 작업공간으로 불러오기

3번째 아이콘:
- MCP 전용 페이지

5번째 아이콘:
- 도구/실행 전용 페이지

따라서 서로 다른 아이콘이 같은 screen 값을 공유하지 않습니다.


## v5.50 상단바 겹침 / 버튼 가림 수정

문제:
- 프로젝트 관리 페이지에서 우측 상단 액션 버튼이 보이지 않음
- 홈 화면 클릭 시 일부 버튼/콘텐츠가 상단바에 가려짐
- 기존 sticky topbar + 각 화면의 `calc(100vh - ...)` 높이 계산이 중복되어 레이아웃이 겹침

수정:
- App 전체를 3행 Grid로 고정
  1. Topbar 58px
  2. Content minmax(0,1fr)
  3. Statusbar 30px
- Topbar/Statusbar sticky 제거
- 각 화면은 content 영역의 100% 높이만 사용
- nav-page-shell / home / workspace의 상단 padding 보정
- 프로젝트 관리 페이지 액션 버튼 강제 표시
- 좁은 화면에서는 페이지 헤더를 세로 배치하여 버튼 잘림 방지


## v5.51 프로젝트 파일 스크롤 / 최근 프로젝트 갱신

### 작업공간 스크롤
- 브라우저 전체 우측 세로 스크롤 제거
- workspace 자체 overflow hidden
- 우측 프로젝트 정보 패널 전체 스크롤 제거
- `프로젝트 파일` 카드가 우측 남은 세로 공간을 모두 사용
- 스크롤은 `.project-tree-view` 내부에만 표시
- 파일이 많아도 트리 영역 안에서만 위/아래 이동

### DB 미등록 프로젝트 분석 후 목록
분석 성공 후:
1. projects / project_analyses DB 저장
2. last_opened_at 갱신
3. commit / refresh
4. GET /api/projects 재호출
5. 방금 생성된 Project ID를 loadProject()로 다시 불러오기
6. 최근 프로젝트와 전체 프로젝트 목록 즉시 갱신

즉 "분석 완료 / DB 저장 완료" 후에도 목록이 비어 있던 UI 동기화 문제를 보완했습니다.


## v5.52 전체 / 최근 프로젝트 DB 동기화

문제:
- DB 미등록 프로젝트 분석 후 "DB 저장 완료"까지 표시됨
- 하지만 좌측 전체/최근 목록은 비어 있음
- 브라우저 새로고침 후 projectList가 []로 초기화되지만 GET /api/projects 자동 호출이 없었음

수정:
1. IDE 시작 시 GET /api/projects 자동 호출
2. 전체/최근/즐겨찾기 탭 클릭 시 매번 GET /api/projects 재조회
3. 프로젝트 관리 전용 페이지에 "DB 새로고침" 버튼 추가
4. 목록 상태 표시:
   - DB 프로젝트 N건 로드됨
   - DB 목록 로드 실패
   - DB에 저장된 프로젝트가 없음
5. 외부 프로젝트 분석 완료 후 GET /api/projects 결과에 방금 생성된 Project ID가 실제 존재하는지 추가 확인
6. Project ID가 조회되지 않으면 화면에 진단 메시지 표시

이제 DB 저장 여부와 Frontend 목록 동기화 여부를 화면에서 바로 구분할 수 있습니다.


## v5.53 Frontend 중복 useState 선언 수정

발생 오류:
- `projectListLoading has already been declared`
- `setProjectListLoading has already been declared`

원인:
v5.52에서 기존에 존재하던 `projectListLoading` state를 다시 선언하여
Vite/esbuild가 같은 scope의 중복 변수 선언으로 빌드를 중단했습니다.

수정:
- App.jsx 전체 useState 선언 검사
- 중복 state/setter는 첫 선언만 유지
- projectFilter / projectListStatus / projectListLoading 등 v5.52 기능 state 유지
- Frontend Vite build 검증 수행


## v5.54 아이콘 클릭 검은 화면 / CORS / busy 오류 수정

브라우저 오류:
- `Uncaught ReferenceError: busy is not defined`
- `Access to fetch at http://127.0.0.1:8000/api/projects ... blocked by CORS policy`
- `Failed to load resource: net::ERR_FAILED`

원인 1:
v5.53에서 파일 전체 기준으로 중복 useState를 제거하면서,
서로 다른 React 컴포넌트(SystemPage / IDE)가 각각 가져야 할 `busy` state까지
중복으로 오판하여 IDE 쪽 선언이 삭제되었습니다.

수정:
- `busy/setBusy`는 컴포넌트별 독립 state로 복원
- SystemPage와 IDE의 scope를 분리해 확인

원인 2:
Vite Frontend(5173)와 FastAPI Backend(8000)가 서로 다른 Origin인데
FastAPI에 CORS 허용 설정이 없거나 누락되어 `/api/projects`가 브라우저에서 차단되었습니다.

수정:
- FastAPI CORSMiddleware 추가
- 허용 Origin:
  - http://127.0.0.1:5173
  - http://localhost:5173
  - http://127.0.0.1:5174
  - http://localhost:5174
- methods / headers 전체 허용

WebSocket `/api/ws` 경고는 별도 연결 문제이며,
이번 검은 화면의 직접 원인은 busy ReferenceError + REST API CORS 차단입니다.


## v5.55 FastAPI → PostgreSQL 연결 진단 / 로그 전체 경로

프로젝트 목록 연결 구조를 명확히 고정:
Frontend → FastAPI GET /api/projects → SQLAlchemy/Psycopg → PostgreSQL

Frontend는 PostgreSQL에 직접 연결하지 않습니다.

추가 API:
GET /api/projects/diagnostics

반환:
- FastAPI 응답 여부
- PostgreSQL 연결 여부
- projects 테이블 건수
- 최근 프로젝트 샘플
- Backend 로그 전체 경로
- 프로젝트 목록 진단 로그 전체 경로

실패 시 화면에:
- FastAPI 호출 실패
- FastAPI는 정상이나 PostgreSQL 조회 실패
를 구분해서 표시합니다.

로그:
- <AgentStudio>/logs/system_manager.log
- <AgentStudio>/logs/api_projects.log

CORS:
localhost / 127.0.0.1의 임의 개발 포트를 허용하는 allow_origin_regex 추가.


## v5.56 Backend Health / API 연결 진단

문제:
system_manager.log의 `Backend=8000, Frontend=5173`은 포트 결정 기록이며
실제 FastAPI가 정상 기동해 HTTP 응답을 했다는 확인이 아니었습니다.

추가:
- GET /api/health
- GET /api/health/database
- backend_startup.log
- database_health.log
- Frontend API 주소 화면 표시
- API Base를 현재 브라우저 hostname 기반으로 생성
- VITE_API_BASE_URL 환경변수로 덮어쓰기 가능
- SYSTEM_ADMIN.cmd에서 FastAPI health check 후에만 시작 완료 처리

정상 연결:
Frontend -> http://127.0.0.1:8000/api -> FastAPI -> PostgreSQL


## v5.56a Health 검증 보강
- /api/health 실제 존재 검증
- /api/health/database 실제 존재 검증
- SYSTEM_ADMIN.cmd에서 FastAPI와 PostgreSQL을 각각 확인
- API base는 VITE_API_BASE_URL 또는 현재 hostname + runtime backend port 사용


## v5.58b SYSTEM_ADMIN 강제 창 유지

v5.57의 정상 제어 흐름과 모든 라벨/서브루틴을 그대로 유지한 상태에서
SYSTEM_ADMIN.cmd 맨 앞에 영구 콘솔 런처만 추가했습니다.

더블클릭:
SYSTEM_ADMIN.cmd
→ 새 cmd /k 창 생성
→ SYSTEM_ADMIN.cmd __AGENTSTUDIO_INNER__ 재실행

장점:
- 본문에서 오류가 나도 cmd /k 창은 유지
- pause에 도달하기 전 오류가 발생해도 메시지를 확인 가능
- 기존 :FAIL / :END / Health Check 라벨 유지
- PC 경로 하드코딩 없음


## v5.59 SYSTEM_ADMIN CMD 파서 반복 오류 제거

증상:
- `'health'은(는) 내부 또는 외부 명령...`
- `'Method'은(는)...`
- `'G'은(는)...`
- `'cho'은(는)...`
- `'"tokens=5"'은(는)...`
같은 SYSTEM_ADMIN.cmd 내부 문자열 조각이 명령처럼 반복 실행됨.

원인:
복잡한 Batch 구조에서 `for /f`, 괄호 블록, `^` 줄연결,
PowerShell 인라인 명령, goto/call 라벨이 섞이며 CMD 파서가 깨짐.

v5.59 구조:
SYSTEM_ADMIN.cmd
  └─ SYSTEM_ADMIN.ps1 실행만 담당

SYSTEM_ADMIN.ps1
  ├─ 기존 Backend/Frontend 종료
  ├─ 동적 포트 찾기
  ├─ runtime-config.js 생성
  ├─ Backend 패키지 확인
  ├─ Frontend build
  ├─ Backend 실행
  ├─ /api/health 확인
  ├─ /api/health/database 확인
  ├─ Frontend 실행
  └─ 브라우저 실행

CMD에는 goto/call/for /f/복잡한 PowerShell 인라인 코드가 없습니다.
오류가 나면 PowerShell 상세 예외를 출력하고 CMD가 마지막에서 pause합니다.


## v5.60 Windows CMD 인코딩 깨짐 수정

증상:
- 한글 문자열 일부가 `'xxx'은(는) 내부 또는 외부 명령...` 형태로 실행됨
- SYSTEM_ADMIN.cmd가 정상 실행되지 않음

원인:
Windows CMD가 UTF-8 한글 Batch 파일을 파싱하는 과정에서 문자 바이트가 깨지며
echo 문자열 일부를 명령어로 해석함.

수정:
- SYSTEM_ADMIN.cmd를 100% ASCII 문자만 사용하도록 변경
- CMD에는 한글 문자열을 전혀 넣지 않음
- SYSTEM_ADMIN.ps1에서만 한글 메시지 출력
- SYSTEM_ADMIN.ps1을 UTF-8 BOM으로 저장
- PowerShell Console OutputEncoding을 UTF-8로 지정
- 당시 진단용 별도 CMD가 추가되었으나, v5.276에서 사용자 실행 진입점을 `SYSTEM_ADMIN.cmd` 하나로 통일하면서 제거했습니다.

현재 권장 실행:
1. `SYSTEM_ADMIN.cmd` 실행
2. 문제가 남으면 `SYSTEM_ADMIN.cmd`가 출력한 logs 경로 확인


## v5.61 PostgreSQL Health Check 비차단 방식

기존 문제:
FastAPI는 정상인데 PostgreSQL Health Check가 실패하면
SYSTEM_ADMIN.ps1이 예외를 throw하여 Frontend 실행까지 중단했습니다.

수정:
- FastAPI Health Check 실패: 치명적 오류 → 시작 중단
- Frontend Health Check 실패: 치명적 오류 → 시작 실패
- PostgreSQL Health Check 실패: 경고 → AgentStudio는 계속 실행
- 시스템 관리 화면에서 DB 설정/복구 가능
- database_health.log에 전체 오류/Traceback 저장
- 성공 화면에서 PostgreSQL 상태를 `정상` 또는 `연결 필요`로 명확히 표시

정상적인 시작 기준:
1. Backend FastAPI 응답 성공
2. Frontend 응답 성공
3. PostgreSQL은 별도 상태로 관리


## v5.62 Windows Psycopg SelectorEventLoop 고정

오류:
`Psycopg cannot use the 'ProactorEventLoop' to run in async mode`

원인:
Windows 기본 asyncio loop는 ProactorEventLoop이며,
Psycopg async는 Windows에서 ProactorEventLoop와 호환되지 않습니다.

수정:
- backend/run_server.py에서 WindowsSelectorEventLoopPolicy 강제 설정
- Uvicorn을 run_server.py를 통해서만 시작
- app/main.py에도 추가 안전장치 적용
- SYSTEM_ADMIN.ps1도 `python run_server.py` 방식으로 Backend 실행
- GET /api/health/runtime 추가
  - 현재 event loop 이름 확인 가능

정상 상태:
GET /api/health/runtime
→ event_loop: "_WindowsSelectorEventLoop"


## v5.63 Uvicorn Explicit SelectorEventLoop

v5.62에서 WindowsSelectorEventLoopPolicy를 설정했지만 실제 FastAPI 요청은
여전히 ProactorEventLoop에서 실행되는 PC가 확인되었습니다.

v5.63:
- uvicorn.run() 사용 중단
- uvicorn.Config + uvicorn.Server 직접 사용
- 서버 coroutine 전체를 아래 명시적 loop에서 실행
  `asyncio.SelectorEventLoop(selectors.SelectSelector())`
- Python이 loop_factory를 지원하면 asyncio.run(..., loop_factory=...)
- 지원하지 않으면 수동 loop.run_until_complete() fallback

이 방식은 해당 PC에서 psycopg.AsyncConnection 테스트가 실제 성공했던
SelectorEventLoop 실행 방식과 동일합니다.

진단:
GET /api/health/runtime

정상:
- is_selector = true
- is_proactor = false

System 관리 화면에도 `Event Loop 확인` 버튼을 추가했습니다.


## v5.63b Event Loop 진단 버튼 표시 보완
- PostgreSQL 테스트 옆에 Event Loop 확인 버튼 표시
- GET /api/health/runtime 호출
- Selector 정상 / Proactor 오류를 화면에 표시
- PostgreSQL/pgvector 테스트는 Frontend가 직접 DB 접속하지 않고 FastAPI test endpoint를 호출하는 구조 유지


## v5.64 프로젝트 목록 API 500 / diagnostics 422 수정

로그에서 확인된 실제 상태:
- PostgreSQL Health Check 성공
- PostgreSQL/pgvector 초기화 성공
- DB 설정 런타임 적용 성공

현재 프로젝트 목록 실패 원인:
`AttributeError: type object 'Project' has no attribute 'updated_at'`

수정:
- `/api/projects` 정렬에서 존재하지 않는 `Project.updated_at` 제거
- 최근 프로젝트 정렬:
  1. `last_opened_at DESC NULLS LAST`
  2. `created_at DESC`
  3. `id DESC`
- `/api/projects/diagnostics` 정적 라우트를 `/projects/{project_id}`보다 앞에 배치
- diagnostics 함수에 불필요한 path/query parameter가 생기지 않도록 무인자 endpoint로 고정
- local_control.py의 Windows 경로 SyntaxWarning 문자열도 escape 처리

이제:
GET /api/projects -> 200 예상
GET /api/projects/diagnostics -> 200 예상


## v5.64b diagnostics route order 보정
- `/api/projects/diagnostics`를 모든 `/api/projects/{...}` 동적 라우트보다 앞에 배치
- `diagnostics` 문자열이 project_id로 해석되어 422가 나는 문제 방지


## v5.65 프로젝트 파일 트리 클릭 / 이름 변경 분리

수정 동작:
- 파일 1회 클릭: 선택 + 중앙 코드 편집기에 파일 내용 로드
- 파일 더블클릭: 이름 변경하지 않음, 파일 열기 동작만 수행
- 폴더 클릭: 접기/펼치기
- 이름 변경: 각 파일/폴더 행 오른쪽 연필(✎) 아이콘 클릭시에만 활성화
- 연필 버튼은 `stopPropagation()`으로 파일 열기/폴더 토글 이벤트와 분리

기존 안내의 `더블클릭: 이름 변경` 문구도 `✎: 이름 변경`으로 변경.


## v5.66 프로젝트 트리 JSX 문법 오류 수정

발생 오류:
`App.jsx:1709:10 ERROR: Expected "}" but found "type"`

원인:
v5.65에서 조건부 렌더링:

`{fileTreeRename?.path===node.path ? ... : ... }`

뒤에 연필 버튼을 추가하면서 삼항식 종료 `}`가 누락되어 JSX 파서가
`<button type="button">`을 잘못된 위치로 해석했습니다.

수정:
- renderProjectTreeNode() 전체 JSX 재정리
- 삼항식에 명시적 `( ... ) : ( ... )` 그룹 사용
- 파일 1회 클릭 → openFile()
- 파일 더블클릭 → openFile()만 수행
- 폴더 클릭/더블클릭 → toggle
- 연필 버튼 클릭시에만 beginRenameTreeItem()
- 연필 더블클릭 이벤트도 stopPropagation()


## v5.67 파일 클릭 시 코드 편집기 로드 수정

확인된 구조:
- 프로젝트 트리 파일 클릭 → `openFile(node.path)`
- Frontend → FastAPI `POST /api/file/read`
- 요청은 `{"path": "<전체 파일 경로>"}`
- Backend `read_file(path)`가 파일 텍스트 반환

수정:
- 프로젝트 root + 상대경로로 Windows 전체경로를 명확히 구성
- `/api/file/read` 응답의 content를 확인한 뒤 `setCode(content)`
- 파일 클릭 즉시 CODE 탭 활성화
- 실패 시 코드창과 Terminal에 상대경로/전체경로/오류를 표시
- Backend 파일 읽기 실패도 404/403/400/500으로 구체적으로 반환

파일 1회 클릭은 이름변경과 완전히 분리되어 코드 로드만 수행합니다.


## v5.68 파일 읽기 / 최초 프로젝트 로딩 / Progress

- 프로젝트 파일 읽기를 `POST /api/files/read`로 표준화
  - root
  - relative_path
- Backend가 프로젝트 root 내부 파일인지 확인 후 UTF-8로 읽음
- 파일 읽기 500 오류는 `logs/file_read.log`에 상세 Traceback 기록
- `loadFiles(rootOverride)` 추가
- 프로젝트 최초 선택 시 `setRoot()` 직후 stale state를 사용하지 않고
  `await loadFiles(projectRoot)`로 즉시 파일/폴더 표시
- 프로젝트 로딩 Progress:
  - 5% 프로젝트 정보
  - 20% 경로 적용
  - 40% 파일/폴더 로드
  - 70% 상태 갱신
  - 90% 작업공간 준비
  - 100% 완료


## v5.69 좌측 프로젝트 Git 연결 정보
선택 프로젝트의 Git 정보를 FastAPI를 통해 조회하여 좌측 프로젝트 목록과 빠른 시작 사이에 표시합니다.

표시:
- Git 저장소 여부
- Clean / 변경 파일 수
- 현재 브랜치
- HEAD 짧은 해시
- origin URL
- 최신 / Ahead / Behind / Diverged
- 새로고침

프로젝트를 선택할 때 자동 조회합니다.


## v5.70 Git 작업 버튼
좌측 Git 카드에 다음 작업 추가:
- 상태
- Fetch
- Pull (`--ff-only`)
- Add
- Commit
- Push
- 수정파일 올리기 (`add -A → commit → push`)
- 로그 최근 20개
- Diff 요약

Git 작업은 모두 FastAPI를 통해 Backend에서 실행합니다.
커밋/수정파일 올리기는 커밋 메시지가 필수입니다.
오류 로그: `<프로젝트>/.agentstudio/logs/git_action.log`


## v5.71 커스텀 스크롤 디자인

기존 브라우저 기본 스크롤을 THEANOVA AgentStudio 다크 UI에 맞게 변경했습니다.

적용:
- 좌측 프로젝트 패널
- 우측 프로젝트 파일 트리
- 코드 편집기
- 터미널
- Git 결과 로그
- 분석/LLM 패널
- 세로/가로 스크롤

디자인:
- 6~8px 얇은 스크롤
- 둥근 thumb
- 투명 track
- 평상시 은은한 색
- hover/active 시 조금 더 밝게
- Firefox + Chromium/Edge 모두 대응


## v5.72 프로젝트 선택 시 기본 터미널 자동 활성화

프로젝트를 선택하면 해당 프로젝트 전용 PowerShell 터미널을 자동 활성화합니다.

예:
FamilyMind 선택
→ 프로젝트 경로:
  `C:\AI\Git\LGCNS_MCP\FamilyMind`
→ `.venv\Scripts\Activate.ps1` 존재 확인
→ 터미널 초기 표시:
  `PS C:\AI\Git\LGCNS_MCP\FamilyMind>`
  `(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& ...\.venv\Scripts\Activate.ps1)`
  `(.venv) PS C:\AI\Git\LGCNS_MCP\FamilyMind>`

구조:
Frontend
→ POST /api/terminal/project-bootstrap
→ FastAPI가 프로젝트 경로/.venv 확인
→ 선택 프로젝트별 터미널 세션 상태 저장
→ 하단 터미널에 프로젝트 이름/경로/.venv 활성 상태 표시

프로젝트를 변경하면 해당 프로젝트의 터미널이 기본 활성 세션이 됩니다.


## v5.72a
- 프로젝트 터미널 bootstrap API의 Python f-string 문법 오류 수정


## v5.73 실제 PowerShell 터미널 실행

원인:
기존 다중 터미널 UI의 `runTerminalSession()`은
`POST /api/command`를 호출했지만 Backend에 `/api/command`가 없어
`404 Not Found`가 발생했습니다.

수정:
- 기존 다중 터미널 UI 유지
- `POST /api/command` 구현
- 실제 `powershell.exe` 실행
- 프로젝트/터미널별 cwd 유지
- `cd`, `Set-Location` 후 다음 명령에도 경로 유지
- `.venv` 존재 시 실제 실행 환경에:
  - `VIRTUAL_ENV`
  - `.venv\\Scripts`를 PATH 앞쪽에 추가
- 명령 실행 결과 stdout/stderr를 터미널에 표시
- 프로젝트 선택 시 해당 프로젝트 전용 터미널을 기본 활성화

지원 예:
- dir
- ls
- Get-ChildItem
- cd app
- cd ..
- pwd
- python --version
- pip list
- git status
- git pull
- npm --version
- 일반 PowerShell 명령

오류 로그:
`<프로젝트>\\.agentstudio\\logs\\terminal.log`

## v5.74 지속형 PowerShell + WebSocket
- 프로젝트/터미널별 powershell.exe 프로세스 지속 유지
- Frontend ↔ FastAPI WebSocket ↔ PowerShell
- cd/.venv/장시간 실행 상태 유지
- stdout 실시간 출력
- Ctrl+C 버튼 추가


## v5.75 React useRef import 오류 수정

발생 오류:
`Uncaught ReferenceError: useRef is not defined`

원인:
v5.74 WebSocket 터미널에서 `terminalSocketsRef=useRef({})`를 추가했지만
App.jsx의 React import에 useRef가 포함되지 않아 IDE 컴포넌트 렌더링이 즉시 중단됨.

수정:
- 기존 React import 문을 찾아 useRef를 명시적으로 추가
- App.jsx에서 사용되는 표준 React Hook과 import 목록을 정적 비교
- 누락 Hook이 있으면 패키징 단계에서 실패하도록 검증


## v5.75a React import 줄바꿈 보정
- `useRef` import 추가 후 다음 import 문이 같은 줄에 붙는 문제 수정
- App.jsx 첫 두 import 문을 독립된 정상 문장으로 고정


## v5.76 터미널 오류 상세/로그 경로 표시

기존:
터미널 WebSocket 오류가 발생해도 UI에는 `[ERROR]`만 보여 원인 확인이 어려웠음.

수정:
터미널 오류 발생 시 화면에 즉시 표시:
- 오류 단계
- 오류 메시지
- 프로젝트 전체 경로
- 터미널 세션 ID
- WebSocket 주소
- 발생 시각
- 로그 전체 경로
- 상세 오류 / Python Traceback

Backend WebSocket 오류 로그:
`<프로젝트>\\.agentstudio\\logs\\terminal_ws.log`

다음 단계의 오류를 분리하여 기록:
- session_create
- output_sender
- websocket_loop
- websocket_error
- websocket_close
- message_parse


## v5.77 Windows SelectorEventLoop + 지속형 PowerShell 호환 수정

확인된 실제 오류:
`asyncio.create_subprocess_exec()`
→ `NotImplementedError`

원인:
AgentStudio Backend는 Psycopg async 때문에 Windows에서
SelectorEventLoop를 사용합니다.
Windows SelectorEventLoop는 asyncio subprocess를 지원하지 않습니다.

수정:
- `asyncio.create_subprocess_exec()` 제거
- `subprocess.Popen()`으로 지속 PowerShell 생성
- stdout 전용 Python Reader Thread 사용
- Reader Thread → `loop.call_soon_threadsafe()` →
  asyncio.Queue → WebSocket 순서로 실시간 출력
- stdin 쓰기는 `asyncio.to_thread()` 사용
- FastAPI/DB는 기존 SelectorEventLoop 유지
- PowerShell은 asyncio subprocess 기능에 의존하지 않음

결과 구조:
Frontend
↕ WebSocket
FastAPI (SelectorEventLoop / Psycopg)
↕ asyncio.Queue
Reader Thread
↕ pipes
subprocess.Popen(powershell.exe)

이 구조는 DB 이벤트 루프와 터미널 subprocess 요구사항을 분리합니다.

## v5.78 터미널 자동 스크롤 + 현재 위치
- 명령 입력/새 출력 시 자동으로 하단 이동
- 현재 작업 경로(CWD)를 터미널 상단에 표시
- cd / Set-Location 후 CWD 자동 갱신

## v5.78a 자동 스크롤 대상 보정
- 실제 `.terminal-output` DOM을 activeTerminalId별 ref에 연결
- 새 출력/명령 입력 후 scrollHeight까지 자동 이동


## v5.79 VS Code 형태의 인라인 PowerShell 터미널

사용자 요구에 맞게 터미널 UI를 변경했습니다.

기존:
- 터미널 위에 별도 `현재 위치` 표시
- 터미널 아래에 별도 명령 입력창

변경:
- 별도 `현재 위치` 표시 제거
- 별도 하단 입력창 제거
- 터미널 본문 안에 현재 PowerShell 프롬프트를 직접 표시
- 프롬프트 오른쪽에서 바로 명령 입력
- Enter → 지속형 PowerShell WebSocket 세션에 전달
- 실행 결과 출력 후 다음 프롬프트에서 계속 입력

예:
`(.venv) PS C:\AI\Git\LGCNS_MCP\FamilyMind> dir`

`cd app` 실행 후:
`(.venv) PS C:\AI\Git\LGCNS_MCP\FamilyMind\app>`

명령 실행/새 출력 시 자동으로 최신 위치로 스크롤합니다.

## v5.79a
- WebSocket ready 응답에 has_venv 포함
- 인라인 프롬프트의 `(.venv)` 표시를 실제 터미널 세션 상태와 동기화


## v5.80 실제 내장 터미널 컴포넌트(xterm.js)

이번 버전은 단순히 VS Code처럼 "보이게" 만든 것이 아닙니다.

Frontend에 xterm.js를 실제 내장하여:
- 화면 내부에 실제 터미널 입력 커서 표시
- 터미널 본문에서 직접 키 입력
- Enter / Backspace / 방향키 등 터미널 입력 이벤트 처리
- 입력 데이터는 WebSocket으로 지속형 PowerShell 세션에 전달
- PowerShell stdout을 xterm.js 화면에 실시간 표시
- ANSI 색상/제어문자 렌더링
- 스크롤백 5000줄
- 자동 하단 스크롤
- 프로젝트별/터미널별 독립 xterm + PowerShell 세션

구조:
xterm.js
↕ WebSocket
FastAPI
↕
지속형 powershell.exe

별도의 HTML input에서 명령을 흉내내는 구조가 아니라,
xterm.js가 키 입력을 직접 받아 PowerShell로 전달합니다.


## v5.81 xterm.js npm 의존성 자동 설치 수정

발생 오류:
`Rollup failed to resolve import "@xterm/xterm"`

원인:
SYSTEM_ADMIN이 node_modules 디렉터리 존재만 확인하고 npm install을 건너뜀.
v5.80에서 package.json에 새 패키지를 추가했지만 기존 node_modules에는 설치되지 않았음.

수정:
- node_modules 존재 여부만으로 설치 완료 판단하지 않음
- 다음 패키지 실제 존재 검사:
  - @xterm/xterm
  - @xterm/addon-fit
- 하나라도 누락되면 자동 `npm install`
- 설치 후 기존 Frontend build 검증 계속 수행
- 수동 복구용 `frontend/install_required_packages.cmd` 추가


## v5.82 Backend 시작 실패 수정

원인:
`TerminalSession` dataclass에서 기본값 필드 `has_venv=False`가
필수 필드 `queue`, `loop`보다 먼저 선언되어 Backend import가 실패할 수 있었습니다.

수정:
- dataclass 필드 순서 수정
- 실제 module import 검증 추가
- Backend Health Check 실패 시 SYSTEM_ADMIN 화면에 로그 마지막 60줄 표시
- Backend PowerShell 창에서도 종료 코드와 Backend 로그 전체 경로 표시
- Backend 정상 기동 후 Frontend 시작 및 웹페이지 열기 흐름 유지


## v5.83 터미널 글자 단위 실행 오류 수정

원인:
- xterm.js onData가 키 입력 한 글자마다 발생
- Backend가 매 입력마다 CWD 확인 명령을 붙여 실행
- 따라서 `dir`가 `d`, `i`, `r` 각각의 PowerShell 명령으로 처리됨
- bootstrap의 `Write-Output ((if ...`도 잘못된 PowerShell 문법

수정:
- xterm 명령줄 버퍼 도입
- 일반 글자는 화면에 즉시 표시만 함
- Enter를 눌렀을 때 완성된 한 줄만 WebSocket으로 전송
- Backspace / Ctrl+C / ↑ / ↓ 기본 처리
- WebSocket message type `command` 추가
- Backend `send_raw()` / `send_command()` 분리
- CWD 확인은 완성 명령 실행 후 1회만 수행
- PowerShell prompt 생성 문법 정상화


## v5.84 Backend 정상 INFO 로그 빨간색 표시 제거

현상:
Uvicorn은 일부 정상 로그를 stderr로 출력합니다.
PowerShell에서 native stderr를 `Tee-Object` 파이프로 받으면
정상 `INFO:` 문자열도 `NativeCommandError` 오류 레코드처럼 빨간색으로 표시될 수 있었습니다.

예:
`python.exe : INFO: Started server process [...]`
`FullyQualifiedErrorId : NativeCommandError`

이 로그는 서버 실패가 아니라 PowerShell 출력 처리 문제였습니다.

수정:
- Backend Python 프로세스를 PowerShell 파이프에서 직접 받지 않음
- `run_backend_console.cmd`를 런타임 생성
- cmd.exe에서 `stdout + stderr`를 Backend 로그 파일로 통합
- PowerShell은 로그 파일을 `Get-Content -Wait`로 읽기만 함
- 따라서 Uvicorn INFO가 PowerShell NativeCommandError로 변환되지 않음
- 실제 Backend 실패 시에만 ExitCode와 로그 전체 경로 표시

Backend 로그:
`C:\\AI\\AgentStudio\\logs\\backend_console.log`


## v5.85 파일/폴더 이름 변경 Enter 확정 방식

원인:
파일명 입력창의 `onBlur={saveTreeRename}` 때문에
연필 클릭 직후 autoFocus/blur 과정에서 저장 API가 즉시 호출됨.

수정:
- 연필 클릭: 이름 변경 입력창만 활성화
- 입력 중에는 API 호출 안 함
- Enter: 실제 이름 변경 저장
- Esc: 취소
- 입력창 포커스가 빠지면 저장하지 않고 취소
- 연필 버튼 MouseDown 기본 포커스 이동 방지


## v5.86 이름 변경 no-op + Backend Runner CMD 수정

### 이름 변경
문제:
같은 파일명으로 Enter를 눌러도 Backend가 대상 파일 존재를 검사해서
`FileExistsError: 같은 이름의 항목이 이미 존재합니다` 발생.

수정:
- Frontend: 현재 이름과 새 이름이 같으면 API 호출 없이 편집 종료
- Backend: source == target이면 오류가 아니라 `changed:false`로 정상 반환
- 실제 다른 파일/폴더와 이름이 충돌할 때만 FileExistsError

### run_backend_console.cmd
문제:
SYSTEM_ADMIN.ps1이 생성한 CMD가 UTF-8 BOM/한글/중첩 따옴표 때문에
cmd.exe에서 `echo`, 경로, python.exe 명령까지 깨져 실행됨.

수정:
- 생성 CMD를 UTF-8 BOM 없이 저장
- 생성 CMD 내부 메시지는 ASCII만 사용
- Python 실행 줄의 따옴표 구조 단순화
- stdout/stderr는 기존 backend_console.log로 통합


## v5.87 Backend 콘솔 UTF-8 깨짐 + 이름 변경 보강

### Backend 콘솔 문자 깨짐
발생 현상:
`INFO:` 같은 UTF-8 로그가
`义但›`, `䤊䙎...` 같은 문자로 깨짐.

원인:
Backend 로그 파일은 UTF-8인데 SYSTEM_ADMIN이 Windows PowerShell
`Get-Content -Wait`로 다시 읽으면서 바이트를 잘못 해석하는 경로가 생김.

수정:
- PowerShell 실시간 로그 tail 제거
- `backend/backend_console_runner.py` 추가
- Python runner가 Backend stdout/stderr를 UTF-8로 직접 디코딩
- 동일 텍스트를 콘솔과 `backend_console.log`에 동시에 출력
- `PYTHONUTF8=1`
- `PYTHONIOENCODING=utf-8`
- PowerShell 콘솔 OutputEncoding도 UTF-8로 지정

### 같은 이름으로 파일명 변경
- `clean_name.casefold() == source.name.casefold()`이면 즉시 no-op 성공
- 파일시스템 rename 호출 안 함
- `changed:false` 반환
- 다른 실제 파일과 충돌하는 경우만 FileExistsError


## v5.88 파일 편집기 유지 + 터미널 커서 편집

### 파일 편집기
문제:
파일을 클릭하면 잠깐 로드된 후 tree/project refresh의 상태 초기화와
비동기 응답 순서 때문에 selected/code가 다시 바뀌어 편집기가 닫히는 현상.

수정:
- fileLoadTokenRef로 가장 최근 파일 로드만 반영
- 파일 클릭 즉시 selected 상태 유지
- API 실패 시에도 선택한 파일과 편집 영역 유지
- loadFiles/tree refresh에서 selected/code 초기화 제거
- 폴더 클릭으로 현재 편집 파일을 닫지 않음

### 터미널 명령줄 편집
기존:
Backspace/Enter/↑/↓ 정도만 지원하고 커서 위치 개념이 없었음.

수정:
- 명령줄 cursor index 상태 추가
- ← / → 이동
- Home / End
- Backspace / Delete
- 커서 중간 위치에 문자 삽입
- ↑ / ↓ history
- Enter 시 현재 전체 명령 실행
- 현재 입력 줄 redraw 시 커서 위치 복원


## v5.89 PowerShell 프롬프트 지속 표시

원하는 동작:
`(.venv) PS C:\AI\LGCNS_MCP\my_llm_service> `

- 터미널 시작 시 프롬프트 표시
- 명령 입력은 프롬프트 바로 오른쪽에서 시작
- Enter 실행
- 명령 출력이 끝난 뒤 현재 위치 기준 프롬프트 다시 표시
- `cd`, `Set-Location`으로 경로 변경 시 다음 프롬프트 경로 자동 반영
- `.venv`가 활성화되어 있으면 `(.venv)` 유지
- 좌/우/Home/End/Backspace/Delete 편집 시에도 프롬프트는 지워지지 않음

구현:
Backend PowerShell이 명령 완료 후:
`__THEANOVA_PROMPT__=<실제 프롬프트>`
마커를 출력하고 Frontend xterm이 이를 실제 프롬프트로 렌더링합니다.


## v5.90 CMD/장시간 Python 실시간 출력 보정

증상:
Windows에서 `run_discord.cmd`를 더블클릭하면 모든 로그가 즉시 표시되지만,
AgentStudio 내장 터미널에서 실행하면 discord.py 로그까지만 보이고
프로그램의 후속 `print()` 출력이 늦게 나타나거나 보이지 않음.

원인:
AgentStudio 터미널은 powershell.exe의 stdin/stdout을 pipe로 연결합니다.
이 상태에서 CMD가 실행한 Python은 stdout이 콘솔(TTY)이 아닌 pipe라고 판단하여
stdout 버퍼링을 사용합니다. discord.py logging(stderr)은 바로 나오지만
일반 print(stdout)는 버퍼에 남을 수 있습니다.

수정:
터미널 세션 전체에 아래 환경변수를 강제:
- PYTHONUTF8=1
- PYTHONIOENCODING=utf-8
- PYTHONUNBUFFERED=1

PowerShell 내부에도 동일 환경변수를 다시 설정하고
Console InputEncoding/OutputEncoding을 UTF-8로 고정했습니다.

따라서 `run_discord.cmd`, `python app.py`, `uvicorn`, 기타 장시간 Python 프로세스의
stdout/stderr가 AgentStudio 내장 터미널에 즉시 표시됩니다.


## v5.91 실제 터미널 프로세스 상태

- `exit`가 PowerShell 자체를 종료하면 Reader Thread가 실제 process exit를 감지합니다.
- UI는 가짜 프롬프트를 만들지 않고 `종료됨 · ExitCode n` 상태로 바뀝니다.
- 종료된 탭에서는 키 입력을 막습니다.
- `다시 시작` 버튼을 누르면 같은 프로젝트 경로에서 새 PowerShell을 생성합니다.
- 장시간 실행 CMD/서버가 실행 중이면 PowerShell 프롬프트가 돌아오지 않는 것이 정상입니다.
- 장시간 프로세스가 정상 종료된 뒤에는 기존 PowerShell이 살아 있는 경우 실제 프롬프트가 다시 표시됩니다.


## v5.92 터미널 재시작 시 이전 WebSocket 오류 잔상 제거

증상:
- `exit` 후 `다시 시작`
- 새 PowerShell은 정상 실행되고 프롬프트도 표시됨
- 하지만 기존 WebSocket close가 `websocket_close` 오류로 기록되어
  좌측 `터미널 오류 상세` 패널이 계속 남음

원인:
재시작 로직이 기존 WebSocket을 의도적으로 close했는데,
onclose 처리기가 이를 비정상 종료와 동일하게 오류 처리함.

수정:
- 재시작 전에 해당 socket을 intentional close로 표시
- 의도적인 close는 오류 패널 생성하지 않음
- 재시작 시작 시 기존 terminalErrors 제거
- 새 WebSocket ready 수신 시 오류 상태 다시 초기화
- 현재 새 PowerShell 세션 상태와 과거 연결 오류 UI가 섞이지 않도록 분리


## v5.93 파일 생성 + 터미널 영구 유지 정책

### 프로젝트 파일
- 우측 프로젝트 파일 영역에 `＋ 파일` 버튼 추가
- 폴더 선택 상태: 해당 폴더에 파일 생성
- 파일 선택 상태: 해당 파일의 부모 폴더에 파일 생성
- 선택 없음: 프로젝트 루트에 파일 생성
- 생성 후 새 파일을 트리에 선택하고 코드 편집기에 자동으로 엶

### 터미널 정책
- 프로젝트를 이동해도 열린 터미널을 닫지 않음
- 프로젝트별 터미널/WebSocket/PowerShell 세션 계속 유지
- 같은 프로젝트로 돌아오면 기존 터미널을 재사용
- 프로젝트를 다시 선택했다고 새 터미널을 중복 생성하지 않음
- 장시간 실행 중인 Discord Bot/FastAPI 등의 프로세스도 프로젝트 이동과 관계없이 유지
- 사용자가 터미널 탭의 `×`를 클릭했을 때만 해당 WebSocket/xterm 세션을 정리

### 프로젝트 이동 시 빈 터미널 보정
기존에는 활성 터미널의 DOM만 렌더링하여 프로젝트 이동 후 xterm 인스턴스가
이미 제거된 DOM을 계속 참조하는 경우가 있었습니다.

이제 모든 열린 터미널의 xterm DOM을 계속 mounted 상태로 보존하고
비활성 터미널만 CSS로 숨깁니다. 따라서 프로젝트/터미널 탭 이동 후에도
기존 출력과 프롬프트가 그대로 남습니다.


## v5.94 파일 생성 후 Frontend 오류 수정

발생 오류:
`ReferenceError: setFileLoading is not defined`

원인:
Backend의 `/files/create`는 정상 완료되어 실제 파일이 생성됐지만,
생성 직후 `openFile()`에서 `setFileLoading()`을 호출했고
React state가 정의되어 있지 않아 Frontend 후처리에서 예외 발생.

수정:
- `fileLoading / setFileLoading` 상태 정상 추가
- 파일 생성 전용 `fileCreateLoading` 상태 추가
- `＋ 파일` 클릭 후 생성 중에는 버튼 잠금
- 헤더에 작은 spinner + `파일 생성 중` 표시
- 생성 성공과 자동 파일 열기 실패를 분리
- 자동 열기 실패가 발생해도 이미 생성된 파일을
  `파일 생성 실패`로 잘못 표시하지 않음

파일 생성은 짧은 작업이므로 0~100% 프로그래스바 대신
간단한 진행 spinner를 사용합니다.


## v5.95 파일 로드 404 Not Found 수정

발생 현상:
파일 트리에서 `.env`, `.py` 등을 클릭하면 코드 편집기에:

`Error: {"detail":"Not Found"}`

표시.

원인:
Frontend `openFile()`:
`GET /files/content?root=...&relative_path=...`

Backend 실제 구현:
`POST /files/read`

API 경로/HTTP method가 서로 달라 FastAPI가 404 반환.

수정:
- Frontend `openFile()`을 `POST /files/read`로 통일
- body:
  - root
  - relative_path
- 기존 Frontend/캐시 호환을 위해 Backend에
  `GET /files/content` 호환 API도 추가
- 파일 읽기는 UTF-8 + errors="replace" 유지
- 프로젝트 루트 밖 경로 접근 방지 유지


## v5.96 Backend 소유 Persistent Terminal

프로젝트 이동 후 터미널 텍스트가 일부 사라지거나 프롬프트가 잘리는 문제를
단순 UI가 아니라 Backend 세션 유지 구조로 보강했습니다.

### Backend
각 `TerminalSession`은 최대 약 600,000자의 raw terminal history를 보관합니다.

WebSocket 연결이 끊겨도:
- PowerShell 프로세스는 유지
- Session ID 유지
- 출력 history 유지

동일한 Session ID로 다시 연결하면 기존 PowerShell을 재사용하고
`history` WebSocket 이벤트로 이전 출력을 재전송합니다.

### Frontend
비활성 xterm을 더 이상 `display:none`으로 만들지 않습니다.

대신:
- visibility:hidden
- opacity:0
- pointer-events:none

으로 화면에서만 숨깁니다. DOM과 xterm 인스턴스는 계속 유지됩니다.

터미널/프로젝트 탭 활성화 시:
- FitAddon.fit()
- Terminal.refresh()
- scrollToBottom()
- focus()

를 레이아웃 안정 시점에 여러 번 실행합니다.

### 기대 동작
FamilyMind에서 Discord Bot 실행 →
YouTube MCP로 이동 →
다시 FamilyMind로 돌아와도

- Discord Bot 프로세스 계속 실행
- 기존 출력 그대로 복원
- 프롬프트 전체 표시
- 사용자가 ×로 닫기 전에는 터미널 유지


## v5.97 다중 파일 편집 탭

- 파일을 클릭하면 코드 편집기 상단에 탭 추가
- 다른 파일을 클릭해도 기존 탭 유지
- 이미 열린 파일을 다시 클릭하면 기존 탭 활성화
- 탭의 ×를 누를 때만 파일 닫기
- 파일별 코드 내용과 수정 여부 별도 유지
- 수정된 파일은 탭에 ● 표시
- 저장 성공 후 수정 표시 해제


## v5.98 코드 탭 레이아웃 + 프로젝트 파일 아이콘

### 코드 편집기
v5.97에서 다중 파일 탭이 flex 높이를 과도하게 차지하여
탭이 세로로 크게 늘어나고 Monaco 소스 영역이 보이지 않는 문제를 수정했습니다.

- 파일 탭 높이 30px 고정
- 탭은 상단 한 줄만 사용
- Monaco Editor는 남은 영역 100% 사용
- 코드 편집기 전체를 `code-editor-stack` flex column으로 정리

### 프로젝트 파일 버튼
기존:
`＋ 폴더  ＋ 파일  이름 변경`

좁은 우측 패널에서 글자가 줄바꿈되는 문제 때문에 아이콘으로 변경했습니다.

- 📁 : 새 폴더
- 📄 : 새 파일
- ✎ : 이름 변경

마우스를 올리면 title 툴팁으로 기능명이 표시됩니다.

- 프로젝트 파일 `이름 변경` 버튼도 ✎ 아이콘 버튼으로 통일.


## v5.99 이름 변경 아이콘 렌더링 오류 수정

발생 오류:
`ReferenceError: startRenameSelectedTreeItem is not defined`

원인:
v5.98에서 이름 변경 텍스트 버튼을 아이콘 버튼으로 교체하면서
실제로 존재하지 않는 함수명을 onClick에 연결함.

수정:
- 존재하지 않는 `startRenameSelectedTreeItem` 제거
- 기존에 정상 동작하던 `beginRenameTreeItem({...})` 인라인 로직 복원
- 아이콘 UI(✎)는 그대로 유지
- 폴더/파일 선택 여부에 따라 disabled 처리 유지


## v5.100 이름 변경 정규식 문법 오류 수정

발생 오류:
`App.jsx:3825:60 ERROR: Unexpected token`

잘못된 코드:
`fileTreeSelected.replace(/\/g,'/').split('/')`

정상 코드:
`fileTreeSelected.replace(/\\/g,'/').split('/')`

추가 확인:
- `startRenameSelectedTreeItem` 잔여 참조 없음
- `beginRenameTreeItem({...})` 사용 확인
- Vite production build 실제 검증


## v5.101 코드 입력 포커스 + 변경/저장 상태 관리

### 코드 입력 포커스
Monaco Editor에서 글자를 입력할 때 xterm 터미널의 자동 focus가
편집기 포커스를 빼앗는 문제를 막았습니다.

- Monaco focus 상태 추적
- 코드 편집 중에는 터미널 focus 금지
- 파일을 새로 열거나 탭 전환 시 Monaco focus 복귀
- onChange는 파일별 편집 상태 관리자에서 처리

### 변경됨
파일 내용을 수정하면 탭에:
`● 변경됨`

표시가 유지됩니다.

### 저장 상태
저장 버튼을 누르면:
1. `저장 중...`
2. 파일 API 저장
3. 성공 시 파일 snapshot 갱신
4. dirty=false
5. `저장 완료`

다시 코드를 수정하면 저장 완료 표시는 사라지고
다시 `● 변경됨`으로 표시됩니다.

저장 실패 시:
`저장 실패`
상태를 표시합니다.


## v5.102 명시적 포커스 소유권

기존 문제:
프로젝트/터미널 레이아웃 복구 코드의 자동 `focus()`가 Monaco 편집기의
포커스를 반복해서 빼앗아 한 글자를 입력한 뒤 터미널로 이동함.

새 정책:
- 기본 포커스 소유자: `editor`
- 코드 영역/파일 탭 클릭 → editor 소유
- 코드 입력 → editor 소유 유지
- Monaco가 일시적으로 blur 되어도 terminal로 자동 이전하지 않음
- 터미널 영역 또는 터미널 탭을 사용자가 직접 클릭 → terminal 소유
- 프로젝트 이동/WebSocket reconnect/xterm fit/refresh → 포커스 소유권 변경 금지
- 터미널 자동 focus는 `focusOwnerRef.current === 'terminal'`일 때만 허용

즉 사용자가 터미널을 직접 클릭하지 않는 한 코드 편집기 포커스가 유지됩니다.

- WebSocket ready 및 xterm mount 시 남아 있던 자동 focus 2곳도 terminal 명시 선택 상태에서만 실행되도록 추가 보정.


## v5.103 코드 편집기 Ctrl+S + 파일 탭 경로 기능

### Ctrl+S
코드 편집기가 포커스 소유자일 때:
`Ctrl+S`
→ 현재 활성 파일 저장

브라우저 기본 저장 기능은 막고 AgentStudio 파일 저장 API를 실행합니다.

### 변경 표시
기존 `● 변경됨` 텍스트를 제거하고
파일 탭에 주황색 `●` 하나만 표시합니다.

### 전체 경로
파일 탭에 마우스를 올리면 title 툴팁으로
프로젝트 루트 + 상대 경로의 전체 경로를 표시합니다.

예:
`C:\AI\LGCNS_MCP\my_llm_service\MyTest\hello.py`

### 오른쪽 클릭
파일 탭 우클릭:
- `전체 경로 복사`

클립보드 API 사용.
브라우저 권한 문제 시 prompt 방식으로 경로를 표시합니다.


## v5.104 파일 이름 변경과 열린 코드 탭 동기화

문제:
프로젝트 트리에서 `new_file2.py`를 `new_file3.py`로 변경해도
열려 있던 `new_file2.py` 탭은 그대로 남아서,
새 `new_file3.py`를 열면 두 파일이 동시에 존재하는 것처럼 보였습니다.

수정:
Backend 파일 이름 변경이 성공하면 반환되는
`result.new_relative_path`를 사용해 열린 편집기 상태도 즉시 변경합니다.

동기화 대상:
- openEditorFiles
- editorFileContents
- editorFileDirty
- selected
- fileTreeSelected
- editorTabMenu

결과:
`new_file2.py ×`
→ 이름 변경
`new_file3.py ×`

기존 탭이 같은 자리에서 새 이름으로 변경됩니다.
기존 편집 내용과 저장되지 않은 변경 상태도 그대로 유지합니다.

폴더 이름 변경 시에는 해당 폴더 아래에 열려 있는 파일 탭들도
새 폴더 경로로 함께 이동합니다.


## v5.105 자연어 코드 수정 실제 반영

### 원인
`/api/ai/edit`에서 잘못된 import를 사용하고 있었습니다.

잘못된 코드:
`from app.services.llm_provider import model_for_task, LLMTask`

실제 위치:
`app.services.model_router`

또한 존재하지 않는:
`LLMTask.CODING`

을 사용하고 있었습니다.

정상:
`LLMTask.CODE_GENERATION`

### 동작 변경
사용자:
`print hello 를 찍어줘`

현재 선택 파일이 Python이고 비어 있다면 코드 모델은:
`print("hello")`

형태의 전체 수정 코드를 반환합니다.

Frontend는 반환 결과를 별도 적용 버튼 없이 즉시:
- 현재 열린 파일 탭 내용
- Monaco Editor
- editorFileContents

에 반영합니다.

파일은 자동 저장하지 않습니다.
대신 `editorFileDirty=true`로 만들어 주황색 점을 표시하고,
사용자가 `Ctrl+S`로 저장하도록 합니다.

### 오류
모델 호출이 실패하면 Backend 500 detail에:
- 예외명
- 파일 경로
- 마지막 traceback

을 포함하도록 보강했습니다.


## v5.106 파일 단위 / 프로젝트 단위 코딩

### 프로젝트 파일 클릭
우측 프로젝트 파일 트리에서 파일을 클릭하면:
1. CODE 탭 자동 활성화
2. 해당 파일 편집 탭 열기/활성화
3. Monaco 편집기로 포커스 이동

### LLM 코드 작업 범위
수정 입력창 왼쪽에 선택 옵션 추가:

- 파일 단위
- 프로젝트 단위

#### 파일 단위
현재 활성 파일만 대상으로 합니다.

예:
`print hello 를 찍어줘`

→ 현재 파일 코드만 수정
→ 저장 전 주황색 점 표시
→ Ctrl+S로 파일 저장

#### 프로젝트 단위
전체 프로젝트를 분석해 기능을 구현합니다.

예:
`유튜브 등록 에이전트를 만들어줘`

Backend가:
1. 프로젝트 구조 분석
2. 사용자 요청과 관련된 기존 파일 선별
3. 기존 코드 Context 구성
4. 코드 생성 모델 호출
5. 필요한 신규 파일 생성
6. 필요한 기존 파일 수정
7. 실제 프로젝트 경로에 저장
8. 프로젝트 파일 트리 갱신
9. 대표 생성/수정 파일을 CODE 탭에서 자동 활성화

프로젝트 단위 응답 JSON은:
- summary
- primary_file
- files[]
  - path
  - action(create/update)
  - content

구조로 제한해 실제 파일 생성/수정을 수행합니다.

보호 경로:
- .git
- .venv
- node_modules
- __pycache__

는 프로젝트 AI가 생성/수정하지 못합니다.


## v5.107 Coding Style Registry

에이전트 프로그램 생성 시 적용되는 코딩 스타일을
대화 기록이 아니라 프로젝트 내부 Registry에 영구 저장하도록 추가했습니다.

구조:
- Coding Style Analyzer
- Coding Rule Registry
- Code Template Registry
- Rule Selector
- Coding Rule Validator

초기 자료:
- 모듈 1-6 LangChain 개요 / 첫 호출
- 모듈 1-7 Colab 로컬 이식 / 마이 서비스 조각

파일 단위 `/api/ai/edit`와 프로젝트 단위 `/api/ai/project-edit`가
현재 요청과 관련된 Coding Rule을 자동 선택해 LLM Prompt에 포함합니다.

상세:
`docs/CODING_STYLE_ARCHITECTURE.md`


## v5.109 Coding Rule Governance

추가:
- 신규 / 강화 / 병합 / 조건부 / 제외 판정
- Rule Priority Resolver
- 보안 > 정확성 > 아키텍처 > 유지보수 > 테스트 > 관찰성 > 성능 > 스타일 > 편의성 우선순위
- Analyzer 결과에 Governance 판정 포함
- Rule Selector가 우선순위에 따라 규칙 정렬

추가 파일:
- backend/app/data/coding_style/rule_policy.json
- backend/app/services/coding_rule_governance.py
- backend/app/services/coding_rule_priority.py
- docs/CODING_RULE_GOVERNANCE.md

추가 API:
- GET /api/coding-style/policy
- POST /api/coding-style/governance


## v5.110 LCEL / Pydantic / Structured Output Coding Rules

추가 규칙:
- CS-028 ~ CS-047

추가 템플릿:
- TPL-LCEL-TEXT
- TPL-PYDANTIC-STRUCTURED-OUTPUT
- TPL-RUNNABLE-PARALLEL
- TPL-RUNNABLE-BRANCH

원본 자료:
`backend/app/data/coding_style/sources/module_3_1_3_4_lcel_pydantic_structured_output.md`

Rule Selector와 Validator에도 LCEL/Pydantic/structured output 관련 판정 로직을 추가했습니다.


## v5.111 Tool Coding Style + DB Migration Fix

### Coding Style
CS-048 ~ CS-066 Function Calling / Tool Design 규칙을 추가했습니다.

### DB 오류 수정
과거 projects 테이블에 다음 컬럼이 없더라도 Backend 시작 시 자동 보정합니다.

- cache_path
- temp_path
- output_path
- venv_path
- models_path
- description
- created_at
- last_opened_at
- is_favorite

SQLAlchemy `create_all()`은 기존 테이블에 컬럼을 추가하지 않기 때문에
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration으로 보정합니다.

### Frontend 오류 수정
`diag?.ok===False` → `diag?.ok===false`

브라우저의:
`ReferenceError: False is not defined`
오류를 제거했습니다.


## v5.112 DB 미등록 기존 프로젝트 경로 찾기 수정

문제:
프로젝트 불러오기 → DB에 없는 기존 프로젝트 분석 →
`경로 찾기` 클릭 시 Windows 폴더 선택창이 전면에 뜨지 않거나
사용자에게 아무 반응이 없는 것처럼 보일 수 있었습니다.

수정:
- 경로 찾기 버튼을 명시적 `type="button"` 처리
- 버튼 선택 중 상태 표시
- 폴더 선택 결과/취소/오류를 프로젝트 불러오기 Modal 안에 바로 표시
- Windows FolderBrowserDialog에 TopMost owner Form 연결
- ShowDialog(owner) 방식으로 Browser 뒤에 숨는 현상 방지
- PowerShell 결과를 marker 기반으로 안전하게 파싱
- timeout/PowerShell 오류 상세 반환


## v5.114 Async Coding Rules

추가 규칙:
- CS-067 ~ CS-081

추가 템플릿:
- TPL-ASYNC-LLM-CALL
- TPL-ASYNC-GATHER-BATCH
- TPL-ASYNC-SEMAPHORE-RETRY

Coding Rule Validator는 Python AST를 이용해 다음 문제를 검사합니다.
- async def 내부 .invoke/.batch/.stream
- async def 내부 time.sleep()
- async def 내부 asyncio.run()


## v5.115 FastAPI Architecture Rules

추가 규칙:
- CS-082 ~ CS-113

추가 템플릿:
- TPL-FASTAPI-STANDARD-SKELETON
- TPL-FASTAPI-MAIN
- TPL-FASTAPI-ROUTER-SERVICE-SCHEMA
- TPL-FASTAPI-SETTINGS
- TPL-DEVCONTAINER-FASTAPI

추가 Agent Factory Profile:
- backend/app/data/agent_factory/fastapi_service_profile.json

Validator:
- main.py LLM/Prompt 로직 경고
- routers LLM 로직 경고
- services → routers/main 역방향 import 오류
- CORS wildcard 경고
- 운영 파일의 --reload 경고


## v5.116 Agent Factory Policy Layers

Day 6~8 전체 분석을 기반으로 Agent Factory 설계 정책 계층을 추가했습니다.

Policy:
- Async Strategy
- Dependency Lifecycle
- API Contract
- File Placement
- API Error/Security
- Agent API Test

추가 Coding Rule:
- CS-114 ~ CS-128

추가 Template:
- TPL-FASTAPI-DEPENDENCIES
- TPL-FASTAPI-YIELD-DEPENDENCY
- TPL-FASTAPI-SAFE-ERROR-HANDLER
- TPL-FASTAPI-DEPENDENCY-OVERRIDE-TEST

프로젝트 단위 FastAPI 코딩 요청에는 Agent Factory 설계 정책이 자동 주입됩니다.


## v5.117 Streaming Strategy

Day 9 전체 분석을 Agent Factory Streaming 계층에 반영했습니다.

Policy:
- STREAMING_STRATEGY_POLICY
- STREAMING_EVENT_CONTRACT
- STREAMING_ERROR_POLICY
- STREAMING_CLIENT_POLICY
- STREAMING_TEST_POLICY
- STREAMING_DEPLOYMENT_POLICY

Coding Rule:
- CS-129 ~ CS-146

Template:
- TPL-SSE-EVENT-ENCODER
- TPL-FASTAPI-SSE-STREAM
- TPL-HTTPX-SSE-CLIENT
- TPL-BROWSER-POST-STREAM


## v5.118 Full Agent Factory Workflow

기존 Patch 중심 LangGraph Workflow를 전체 Agent Factory 제작 Workflow로 확장했습니다.

추가 Node:
- requirement_analysis
- capability_design
- tool_mcp_decision
- agent_architecture
- target_workflow_design
- project_file_plan
- environment_configuration
- package_completion

AgentStudio 제작 Workflow와 생성 대상 Agent Workflow를 State에서 명확히 분리합니다.

Patch Service는 신규 파일 생성(create_file=true)도 지원합니다.

Workflow 확인 API:
- GET /api/workflow/definition


## v5.119 Workflow Visualizer

Workspace에 `워크플로우` 탭을 추가했습니다.

화면:
- AgentStudio 전체 Workflow
- 개발 대상 Agent Workflow

Backend:
- GET /api/workflow/definition
- POST /api/workflow/preview

신규 Agent 설계 인터뷰 화면에서도 `Workflow 보기` 버튼으로 대상 Agent Workflow 화면으로 이동할 수 있습니다.


## v5.120 Visual Workflow Designer

Workflow 화면을 단순 Node 나열 방식에서 설계도 형태로 변경했습니다.

AgentStudio:
- 요구 이해
- Agent 설계
- 제작
- 검증 & 완성

4개 Phase 기반 시각화와 자동 복구 Loop를 제공합니다.

대상 Agent:
- 단계별 자동 아이콘
- 시각 카드
- 연결 흐름
- Branch / Retry / Failure Policy 시각화

Backend workflow definition API도 `factory_phases` 메타데이터를 반환하도록 확장했습니다.


## v5.121 Sticky Interview Composer

Agent 설계 인터뷰의 대화가 길어져도 답변 입력창이 화면 아래로 밀려나지 않도록 수정했습니다.

- 헤더 고정
- 메시지 영역만 내부 스크롤
- 입력창 항상 하단 표시
- 새 메시지/AI 응답 시 최신 메시지 자동 스크롤
- 좌/우 패널 독립 스크롤


## v5.122 Blank Project Path

신규 Agent 설계 화면의 프로젝트 경로 실제 초기값을 제거했습니다.

- 실제 값: 빈 문자열
- placeholder: 예시 경로만 표시
- 사용자가 직접 입력하거나 `경로 찾기`로 선택해야 실제 값이 설정됩니다.


## v5.123 Workflow Requirement Memory

대상 Agent Workflow 설계 시 현재 한 문장만 보지 않고
Agent 설계 인터뷰 전체 대화와 확정 요구사항을 함께 사용하도록 개선했습니다.

주요 변경:
- interview_messages 전달
- confirmed_requirements 전달
- MCP/Transport/보안/Provider/UI/저장 분기 누락 방지
- Workflow quality 검사
- 단계 수/분기/Retry/Failure UI 표시


## v5.124 Agent Build Progress Actions

Agent 설계 인터뷰에 실제 제작 단계 버튼을 추가했습니다.

- Workflow 설계
- 프로젝트 생성
- 개발 시작

프로젝트 생성은 기존 `/projects/create-agent`,
개발 시작은 기존 `/workflow/start`와 연결됩니다.

`진행해줘` 같은 자연어도 요구사항 분석 완료 후 제작 진행 Intent로 처리됩니다.


## v5.125 Execution Result / Analysis Report Dashboard

`실행 결과`와 `분석 리포트`를 Agent Factory `workflow.state`에 실제 연결했습니다.

실행 결과:
- Status / Test / Created / Modified / Debug
- Test output
- File changes
- Debug history
- Terminal preview

분석 리포트:
- Requirements
- Architecture
- Target Workflow
- MCP / Tool
- Capabilities
- Generated files
- Coding Style Validation
- Final completion status

코딩 스타일은 프로젝트 코드 파일별로 `/coding-style/validate`를 호출해 PASS/WARNING/FAIL로 표시합니다.


## v5.126 Agent Settings Generator

Agent Factory에 정식 Settings Generator 계층을 추가했습니다.

Workflow:
- Settings Requirement Analysis
- Settings Schema Design
- Settings UI Design
- Settings Generator
- Settings Validation

생성 대상 Agent에 필요한 설정만 Backend API + React Settings UI로 자동 생성합니다.
Secret 평문 노출/Frontend 하드코딩/.env.example 실제 Secret 저장을 금지하는 Coding Rule도 추가했습니다.


## v5.127 Frontend Build Fix

v5.125 Dashboard 적용 과정에서 누락된 `workspace-bottom-grid` / `editor-pane`
구조를 복원했습니다. v5.126 Settings Generator 기능은 그대로 유지됩니다.

Vite 오류 위치:
- App.jsx 5445
- App.jsx 5629
- App.jsx 5630
- App.jsx 5632

원인은 단일 닫는 태그가 아니라 하단 Editor Section 시작 블록 누락이었습니다.


## v5.128 Persistent Agent Build Actions

Agent 제작 진행 버튼을 화면별 중복 UI가 아닌 `AgentBuildActionBar` 공통 컴포넌트로 통합했습니다.

Workspace에서 에이전트 설계 / Workflow / 코드 편집 / 실행 결과 / 분석 리포트로 이동해도
Workflow 설계, 프로젝트 생성, 개발 시작 버튼이 계속 표시되고 현재 제작 단계가 유지됩니다.


## v5.129 Compact RUN / REPORT Layout

실행 결과와 분석 리포트 탭의 불필요한 세로 빈 공간을 제거했습니다.

RUN / REPORT에서만 상단 Dashboard 영역을 콘텐츠 높이에 맞게 축소하고,
남는 화면은 LLM 코드 편집기와 터미널 영역이 사용합니다.


## v5.130 TRUE Compact Top Pane Fix

v5.129에서 남아 있던 상위 flex/height 강제를 제거했습니다.
RUN/REPORT 상단 영역은 이제 실제 콘텐츠 높이만 차지하고,
남는 공간은 하단 코드 편집/터미널이 사용합니다.


## v5.131 Grid Row Layout Fix

큰 세로 빈 공간의 실제 원인이었던 `workspace-main` Grid 행 수 불일치를 수정했습니다.
공통 진행 바 추가 후 4개 자식에 맞춰 Grid를 4행으로 재정의했습니다.


## v5.132 Requirement Completion Message

요구사항 분석 완료 시 응답 마지막을 다음 문장으로 고정했습니다.

`요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다.`

완료 후 추가 요구사항 입력을 유도하는 문장은 제거합니다.


## v5.133 Workflow Requirement Coverage

Target Agent Workflow가 인터뷰 요구사항을 지나치게 축약하지 않도록 강화했습니다.
Root/확장자 검증, MCP Client/Transport/Server/Tool, LLM Provider, UI 표시,
저장 분기/형식/Output 검증을 실행상 중요한 단계로 보존합니다.

Workflow 화면에 `요구사항 반영 확인` Traceability 패널도 추가했습니다.


## v5.134 Grouped Workflow Overview

Target Agent Workflow의 기본 표시를 그룹형으로 변경했습니다.

기본 화면:
- 입력 / 검증
- MCP 파일 처리
- LLM 요약
- 결과 표시
- 선택적 저장
- 완료

각 그룹을 클릭하면 해당 그룹의 상세 Workflow 카드 화면으로 들어갑니다.


## v5.135 Full Agent Build Engine

Code Generator가 Agent 설계 전체와 등록 Coding Style을 실제 생성 코드에 강제 적용하도록 개선했습니다.

- Architecture/MCP/Workflow/Settings/File Plan 전체 전달
- FastAPI/React/MCP 요구에 따른 최소 Project Artifact Manifest 자동 보강
- Coding Style Registry + Code Template을 Patch Generator System Prompt에 직접 적용
- planned required 파일 누락 검사
- TODO/placeholder/stub 검사
- Coding Style Error 검사
- 실패 시 Code Generation 재진입
- 산출물 검증 미완료 상태는 COMPLETED 금지


## v5.136 LangGraph Compile Fix

`build_artifact_validation` Edge는 있었지만 Node 등록이 누락되어 Backend 시작 시
LangGraph compile 오류가 발생하던 문제를 수정했습니다.

`backend/validate_agent_workflow.py`를 추가하여 실제 Graph compile 검증을 수행할 수 있습니다.


## v5.137 Project Recreate Flow

동일 프로젝트 경로가 DB에 이미 등록된 경우 확인창을 띄웁니다.

- 확인: 기존 DB Project Row를 재사용하고 재생성 진행
- 취소: 현재 상태 유지
- Workspace에 `← 신규 Agent 설계` 버튼을 추가하여 프로젝트 경로 변경 가능


## v5.138 Navigation / Right Panel Layout

- 홈 아이콘 아래에 신규 Agent 설계 전용 Global Nav 아이콘 추가
- Workspace 모든 탭의 `신규 Agent 설계` 버튼 제거
- DESIGN/WORKFLOW에서는 우측 프로젝트 파일 카드 숨김
- DESIGN/WORKFLOW에서는 MCP 도구 아래에 Workflow 설계/프로젝트 생성/개발 시작 액션 배치
- CODE/RUN/REPORT에서는 프로젝트 파일 트리 유지


## v5.139 Tab-specific Workspace Layout

- DESIGN/WORKFLOW: LLM 코드 편집 + 터미널을 하단 305px 고정
- CODE: Agent 제작 진행 제거, 하단 LLM/터미널 유지
- RUN/REPORT: Agent 제작 진행, LLM 코드 편집, 터미널, 프로젝트 파일 트리 제거


## v5.140 Design / Workflow Clean Layout

- DESIGN/WORKFLOW에서 LLM 대화형 코드 편집 및 터미널 제거
- 우측 Agent 제작 진행을 2단 구조로 재배치
- 좁은 우측 패널에서 버튼 잘림 방지
- 프로젝트 클릭/불러오기 완료 시 CODE 탭으로 자동 이동


## v5.142 Regression Fix

v5.141의 `askCodeEditorLLM is not defined` 오류를 수정했습니다.
v5.140에서 안전하게 다시 구성했으며 UI 통합 과정에서 Workspace 함수가 삭제되지 않도록 회귀 검사를 추가했습니다.


## v5.143 Vite HMR Stability Fix

- Vite host/port/HMR clientPort를 동일 Runtime Port로 통일
- package.json의 5173 하드코딩 제거
- Frontend Vite 자동 재시작 runner 추가
- SYSTEM_ADMIN에서 실제 선택된 Frontend Port를 환경변수/CLI에 동일 전달
- Frontend 시작 실패 시 frontend_console.log 상세 표시


## v5.144 Agent Design Left Panel Cleanup

- DESIGN 탭에서 기존 좌측 프로젝트 패널 대신 신규 Agent 설계 단계 표시
- 중앙 DESIGN 영역의 중복 신규 Agent 설계 단계 제거
- 글로벌 좌측 네비게이션의 중복 Workspace(▣) 아이콘 제거
- 신규 Agent 설계(✦) 아이콘 하나만 유지


## v5.145 Persistent Code Workspace

CODE 탭을 벗어나도 Monaco와 xterm DOM을 unmount하지 않습니다.
기존 1px 숨김 방식을 제거하여 Terminal 열/행 계산 깨짐을 방지했고,
CODE 복귀 시 xterm fit/refresh 및 Monaco layout을 수행합니다.


## v5.146 Windows Frontend Spawn Fix

Windows에서 `spawn npm.cmd`가 `EINVAL`로 실패하는 문제를 수정했습니다.
Frontend Runner는 이제 `cmd.exe /d /s /c npm run dev ...` 방식으로 Vite를 실행합니다.


## v5.147 Terminal + LLM Usage Cost
- xterm 숨김 상태 fit 금지 및 ResizeObserver 기반 복원
- 프로젝트별 유료 Input/Output/Total Token 및 추정 비용
- AgentStudio 일별 전체 Token 및 추정 비용
- 실행 결과/분석 리포트에 Usage Dashboard 추가


## v5.148 Workflow Design Progress

- Workflow 설계 중 진행률 Bar 표시
- 현재 단계 및 상세 진행 메시지
- 요구사항 → AI 설계 → 응답 대기 → 검증 → 완료
- Backend LLM 응답 대기 중에는 실제 상태를 왜곡하지 않고 `AI 설계 응답 대기`로 표시


## v5.149 Agent Development Progress

- 개발 시작 후 진행률 Bar 표시
- 경과 시간 표시
- 준비 → Factory → 코드/검증 → 테스트/복구 → 패키징 → 완료 단계 표시
- 현재 `/workflow/start`가 일괄 응답 방식이므로 응답 전에는 실제 Node 완료를 허위 표시하지 않음
- 최종 LangGraph State 응답 후 실제 상태로 100% 완료


## v5.150 Final Development Status Feedback

- Workflow 최종 상태를 성공/실패/디버그조치/사용자대기/기타로 분류
- 실행 결과 상단에 명확한 상태 Banner 표시
- 완료/실패/DEBUG_PATCH_READY 시 Browser Alert 표시
- `DEBUG_PATCH_READY`를 완료로 오인하지 않도록 "디버그 조치 필요" 명시


## v5.151 Failure Diagnostics
- 파일 0개 → FAILED_NO_ARTIFACTS
- failure_report/workflow_state/requirements_snapshot/generated_artifacts 자동 생성
- debug_patch/recovery_plan 자동 생성
- 실행 결과/분석 리포트에 실패 진단 카드 표시


## v5.152 File Apply + Requirement Coverage

- 개발 시작 클릭 즉시 실행 결과 탭 이동
- Workflow Preview design_bundle을 개발 단계에 그대로 전달
- React/FastAPI/MCP stdio File Plan Coverage Gate
- 상대 Patch 경로를 project_root 기준으로 정규화
- write → exists → size → read-back 검증 후에만 created=true
- 실제 쓰기 실패는 FILE_APPLY_FAILED
- 동일 Artifact 실패 반복 시 BUILD_ARTIFACT_STALLED
- stdio 프로젝트의 Flask/HTTP 구현 및 gpt-4 하드코딩 검출


## v5.153 Requirement Collection Memory

- 프로젝트별 인터뷰/요구사항 Draft 자동 저장
- Agent 설계 화면 재진입 시 이전 인터뷰 자동 복원
- 우측에 목적/파일/결과/LLM/UI/Backend/MCP/DB/권한/실행환경/처리제한 수집 현황 표시
- 이미 수집한 정보가 있으면 인터뷰를 다시 하지 않고 Workflow 바로 설계
- Workflow Preview까지 저장되어 있으면 WORKFLOW_READY 상태 복원


## v5.154 Requirement Keywords Visible

- 실제 DESIGN 탭 우측 `프로젝트 구성` 패널에 요구사항 수집 현황 표시
- 완료/미수집 키워드 11개 표시
- 저장/복원 상태와 저장 시각 표시
- 수집된 요구사항으로 바로 Workflow 설계 버튼 표시
- 현재 DESIGN 탭 `Workflow 보기`도 저장된 요구사항을 재사용


## v5.155 Code Plan Completeness + Targeted Repair

- File Plan required 파일 ↔ Code Plan changes[] 완전성 Gate
- 누락 Code Plan 자동 보강 후에도 실패하면 CODE_PLAN_INCOMPLETE
- Build 실패 시 원래 Code Plan 반복 금지, 실패 대상만 Targeted Repair
- Repair 대상 누락 시 REPAIR_PLAN_INCOMPLETE
- 전체 생성 소스에서 stdio 위반 / gpt-4 하드코딩 Architecture 검사
- 인터뷰 전체 요구사항/confirmed requirements를 개발 design bundle까지 보존
- `.env.example`, package.json 등 특수 설정 파일 Artifact 집계


## v5.156 Requirement Value Display

- 요구사항 수집 현황을 `키워드 : 실제 수집값` 형태로 표시
- LLM : gpt-4o-mini, Ollama
- UI : React + Vite
- Backend : FastAPI + Uvicorn
- MCP / DB / 파일 접근 / 실행 환경 / 처리 제한도 실제 값 표시
- confirmed_requirements에 processing/runtime/auth 구조 추가
- 우측 표시 데이터와 Workflow/개발 입력 데이터의 원천 통합


## v5.157 Requirement Panel Move

- 에이전트 설계 탭 우측에서 `요구사항 수집 현황`을 `Agent 제작 진행` 아래로 이동
- 기존 수집값/완료 상태/자동 저장/Workflow 설계 기능 유지


## v5.158 Requirement Coverage Gate Fix

- `stdio` 단어가 File Plan purpose에 없다는 이유만으로 즉시 실패하던 버그 수정
- confirmed requirements를 Coverage의 source of truth로 사용
- File Plan purpose 자동 보강
- Coverage는 필수 파일 구조만 검사
- 실제 stdio/HTTP 구현 위반은 Build Artifact Architecture Gate에서 검사
- Coverage 실패 시 정확한 누락 계약을 리포트에 표시


## v5.159 Status + Code Plan Path Fix

- `CODE_PLAN_INCOMPLETE`를 `COMPLETE` substring 때문에 성공으로 표시하던 치명적 UI 버그 수정
- 성공은 COMPLETED/SUCCESS 정확 일치 + 테스트 ReturnCode 0 + Artifact 검증 성공 + 실제 Patch 존재 시에만 표시
- Code Plan 절대/상대경로를 project_root 기준 상대경로로 통일
- Initial/Supplement/Repair Plan 중복 파일 제거
- CODE_PLAN_INCOMPLETE 실패 진단에 실제 누락 파일 목록 기록
- 성공 상태에서는 실패 진단 카드를 표시하지 않음


## v5.161 Failure Diagnostics + Dotfile Fix

- `.env.example` ↔ `env.example` Code Plan 비교 오류 수정
- stdio MCP 요구와 충돌하는 Flask/requests HTTP Code Plan을 File Apply 전에 차단
- Failed to fetch에 Backend URL/연결 오류 정보 포함
- Workflow fetch 실패 시 프로젝트 진단 자료 재조회
- 파일 적용/테스트/디버그 실행 여부 명시
- 실패 진단 및 로그 파일별 존재 여부 표시

## v5.162 Code Plan Batch Recovery + Failure Message Fix

- 많은 required 파일을 3개 단위 Code Plan 배치로 자동 보강
- 보강 무진전 시 1개 파일 단위로 축소 재시도
- 보강 응답을 요청 대상 파일로 제한하여 기존 Plan 덮어쓰기 방지
- `code_plan_validation`에 보강 횟수/대상/추가/잔여 파일 이력 기록
- 실패 진단 리포트와 UI에 Code Plan 누락 파일과 보강 상태 표시
- `/workflow/start` 응답 연결 오류와 실제 Agent 실패 원인을 분리하여 표시


## v5.173 SYSTEM_ADMIN UTF-8 BOM Parser Fix
- Windows PowerShell 5.1에서 한글 SYSTEM_ADMIN.ps1을 UTF-8 BOM 없이 읽어 발생하던 ParserError를 수정했습니다.
- AgentStudio 자체 및 생성 Agent의 SYSTEM_ADMIN.ps1을 UTF-8 BOM으로 보장합니다.

## v5.174 Generated FastAPI Import Contract Fix

- 생성 Agent의 표준 FastAPI 구조 `backend/app` 내부 import를 `app.*` 기준으로 자동 정규화합니다.
- `from routers ...`, `from backend.app ...` 혼용을 제거하고 필요한 `__init__.py`를 결정적으로 생성합니다.
- Generated `SYSTEM_ADMIN.ps1`은 Backend 시작 전에 `app.main:app` import preflight를 수행하여 ModuleNotFoundError를 포트 대기 전에 즉시 진단합니다.
- SYSTEM_ADMIN은 `backend` 폴더를 WorkingDirectory로 하고 `uvicorn app.main:app`을 실행하는 계약을 명시적으로 검증합니다.
- Settings Generator 이후 Build Artifact Validation에서도 import 정규화를 다시 수행하여 후속 생성 파일까지 동일 계약을 유지합니다.

Health: `5.174 / GeneratedFastApiImportContractFix`
