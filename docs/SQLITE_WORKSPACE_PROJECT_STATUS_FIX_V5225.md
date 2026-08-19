# v5.225 SQLite Workspace / Project Status Fix

- SQL Workspace DB 종류에 SQLite3를 추가했습니다.
- SQLite3는 Host/Port/User/Password 없이 현재 프로젝트 내부의 `.db`, `.sqlite`, `.sqlite3`, `.db3` 파일에 직접 연결합니다.
- DB 파일 경로는 프로젝트 상대 경로(`data/app.db`) 또는 프로젝트 내부 절대 경로를 사용할 수 있습니다. 파일이 없으면 연결 시 생성합니다.
- AgentStudio SQL Workspace는 Python 표준 라이브러리 `sqlite3`를 사용하므로 별도 pip 설치가 필요하지 않습니다.
- 프로젝트 SQLite3 상태 확인에서 다음을 표시합니다.
  - AgentStudio Backend Python의 sqlite3 사용 가능 여부/SQLite 버전
  - 프로젝트 `.venv`/`venv` Python의 sqlite3 사용 가능 여부/SQLite 버전
  - Node 프로젝트의 `sqlite3`, `better-sqlite3`, `@libsql/client` 패키지 선언 여부
  - PATH의 sqlite3 CLI 탐지
  - 프로젝트 내부 SQLite DB 파일 목록
- DB Object Explorer는 SQLite3의 테이블, 뷰, 인덱스, 트리거와 테이블/뷰 컬럼 정보를 표시합니다.
- SQL F5 전체 실행/F8 선택 실행 및 Data Output 테이블은 SQLite3 연결에도 동일하게 동작합니다.
