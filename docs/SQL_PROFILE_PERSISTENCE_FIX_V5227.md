# v5.227 SqlProfilePersistenceFix

## 문제
SQL Workspace에서 저장한 DB 연결 정보가 AgentStudio 버전 ZIP 교체 또는 DB 종류 전환 후 기본값으로 돌아갈 수 있었습니다. 기존 구현은 설치 폴더의 `backend/data/sql_workspace_profiles.json`에 프로젝트당 DB 프로필 1개만 저장했습니다.

## 수정
- 연결 프로필 저장 위치를 `%LOCALAPPDATA%\THEANOVA\AgentStudio\sql_workspace_profiles.json`으로 이동하여 앱 버전 교체와 분리했습니다.
- 프로젝트마다 PostgreSQL/MSSQL/Oracle/SQLite3 프로필을 각각 보존합니다.
- DB 종류를 전환하면 해당 종류의 마지막 저장값을 다시 불러옵니다.
- v5.223~v5.226 형식의 단일 프로필 파일은 자동 마이그레이션합니다.
- 비밀번호는 기존 보안 정책대로 디스크에 저장하지 않으며 Backend 실행 메모리에서만 유지합니다.
- 우측 DB 연결 패널에 저장된 DB 종류와 실제 프로필 저장 경로를 표시합니다.
