# v5.232 DbObjectExplorerColumnSelectFix

## 변경 사항

- DB Object Explorer에서 테이블을 더블클릭할 때 임시 조회 SQL의 `SELECT *`를 사용하지 않습니다.
- Object Explorer가 이미 읽어 둔 실제 테이블 컬럼을 순서대로 모두 명시해 SELECT 문을 생성합니다.
- PostgreSQL/SQLite3/Oracle은 `"column"`, MSSQL은 `[column]` 형식으로 각 DB 식별자 quoting 규칙을 사용합니다.
- MSSQL은 `TOP (1000)`, PostgreSQL/SQLite3은 `LIMIT 1000`, Oracle은 `FETCH FIRST 1000 ROWS ONLY`를 유지합니다.
- DB 메타데이터 권한 문제로 컬럼 목록을 읽지 못한 예외 상황에서만 `*`를 호환 fallback으로 사용합니다.

## 예시

```sql
SELECT
    "id",
    "customer_id",
    "product_id",
    "qty",
    "order_date",
    "ship_date"
FROM "main"."orders"
LIMIT 1000;
```
