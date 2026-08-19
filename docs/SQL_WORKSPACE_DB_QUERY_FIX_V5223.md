# v5.223 SQL Workspace DB Query Fix

`.sql` 파일을 코드 편집기에서 열었을 때 SQL 전용 Database Workspace를 제공합니다.

## 우측 DB 연결 탭
- PostgreSQL / MSSQL / Oracle 선택
- Host / Port / Database 또는 Oracle Service Name / 사용자 / 비밀번호 설정
- MSSQL ODBC Driver와 Trust Server Certificate 설정
- 프로젝트별 비밀정보 제외 연결 설정 저장
- Backend가 살아 있는 동안 실제 DB connection과 비밀번호는 메모리에서 유지
- SQL 파일을 바꾸거나 Frontend를 새로고침해도 Backend 연결이 유지되어 있으면 그대로 재사용
- 연결 / 테스트, 연결 해제, 상태 새로고침 제공

## SQL 실행
- F5 또는 `전체 실행`: 현재 Editor buffer 전체 SQL 실행
- F8 또는 `선택 실행`: Monaco에서 선택한 SQL만 실행
- 저장 전 Editor 내용도 실행 가능
- SELECT 결과는 하단 `Data Output`에 컬럼/행 테이블로 표시
- INSERT/UPDATE/DELETE/DDL 및 오류는 `Messages`에 표시
- 결과는 기본 최대 1,000행까지 표시

## Drivers
- PostgreSQL: psycopg
- MSSQL: pyodbc + Windows Microsoft ODBC Driver 18 for SQL Server
- Oracle: python-oracledb thin mode

DB 비밀번호는 `backend/data/sql_workspace_profiles.json`에 기록하지 않습니다.
