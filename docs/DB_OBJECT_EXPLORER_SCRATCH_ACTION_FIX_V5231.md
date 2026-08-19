# v5.231 DbObjectExplorerScratchActionFix

## 변경 사항

- SQL Workspace 우측 `DB Object Explorer` 세로 영역을 기존 최소 220px에서 1100px로 약 5배 확대했습니다.
- DB Object Explorer 항목 더블클릭 동작을 추가했습니다.
  - 테이블: 현재 DB 종류에 맞는 `SELECT *` 임시 SQL을 `.agentstudio/sql_scratch`에 생성하고 즉시 실행합니다. 결과는 `Data Output`에 표시합니다.
  - 뷰/프로시저/함수/트리거/인덱스/시퀀스/패키지: 가능한 경우 DB의 실제 정의를 읽어 수정용 임시 SQL 파일을 생성하고 Editor에서 엽니다.
- PostgreSQL/MSSQL/Oracle/SQLite3별 식별자 quoting 및 객체 정의 조회 방식을 분리했습니다.
- `.agentstudio` 내부 scratch 파일은 프로젝트 파일 트리에 노출하지 않습니다.

## 임시 SQL

임시 파일은 프로젝트 내부 `.agentstudio/sql_scratch`에 저장되므로 일반 Editor처럼 수정/저장할 수 있지만 프로젝트 소스 트리에는 표시되지 않습니다.
