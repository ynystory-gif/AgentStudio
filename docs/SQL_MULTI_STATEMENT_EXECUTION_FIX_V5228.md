# v5.228 SqlMultiStatementExecutionFix

SQL Workspace의 선택/전체 실행에서 여러 SQL 문장을 안전하게 순차 실행하도록 개선했다.

- 세미콜론은 문자열/주석/PostgreSQL dollar quote 바깥에서만 문장 구분자로 해석한다.
- SQLite3에서 사용자가 여러 개의 한 줄 INSERT/UPDATE/DELETE/REPLACE 문장을 선택했지만 세미콜론을 생략한 경우, 각 줄이 독립적으로 완결된 DML이면 자동으로 개별 문장으로 인식한다.
- 모든 문장은 동일 트랜잭션에서 순차 실행하고 중간 실패 시 rollback 한다.
- 다중 DML은 총 영향 행 수를 표시한다.
- 여러 SELECT가 포함되면 Data Output에는 마지막 result set을 표시하고 statement별 결과 metadata를 응답한다.
- 오류 시 실패한 SQL 번호와 짧은 SQL preview를 Messages에 제공한다.
