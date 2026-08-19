# Multi Database Connection Profiles Fix v5.239

## 목적
SQL Workspace에서 프로젝트 하나에 DB 연결을 종류별 1개만 저장하던 구조를 다중 연결 프로필 구조로 변경합니다.

## 지원 연결
- PostgreSQL 여러 개
- MSSQL 여러 개
- Oracle 여러 개
- SQLite3 여러 개
- 서로 다른 DB 종류를 한 프로젝트에 혼합 등록

## 동작
- 각 연결은 고유 `connection_id`와 사용자가 지정하는 `name`을 가집니다.
- 여러 연결을 동시에 열린 상태로 유지할 수 있습니다.
- SQL 실행/Object Explorer는 현재 선택된 활성 연결을 사용합니다.
- 저장된 연결을 선택하면 이미 연결 중인 세션이면 즉시 해당 연결로 전환합니다.
- 저장 연결 삭제 시 해당 연결 세션만 닫고 다른 연결은 유지합니다.

## 영속 저장
연결 정보는 AgentStudio 영속 데이터 폴더의 `sql_workspace_profiles.json`에 프로젝트별로 저장합니다.
Windows 기본 위치는 `%LOCALAPPDATA%\THEANOVA\AgentStudio`입니다.

저장 정보 예:
- 연결 이름
- DB 종류
- Host / Port
- Database 또는 Oracle Service Name
- 사용자명
- MSSQL ODBC Driver / TrustServerCertificate
- SQLite 프로젝트 DB 파일 경로

## 비밀번호 보안
Windows에서는 비밀번호를 평문으로 JSON에 기록하지 않습니다.
`CryptProtectData`/`CryptUnprotectData` 기반 Windows DPAPI Current User 범위로 암호화한 값만 저장합니다.
따라서 같은 Windows 사용자 컨텍스트에서 AgentStudio를 실행할 때만 복호화할 수 있습니다.

## 이전 버전 호환
v5.238 이전의 `{active_db_type, profiles:{db_type:...}}` 구조는 읽을 때 자동으로 다중 `connections` 구조로 정규화합니다.
기존 PostgreSQL/MSSQL/Oracle/SQLite 연결 정보는 유지됩니다.
