# v5.311 SQL Multi Result + Resizable Data Output

## 목적

한 SQL 편집기에서 `SELECT`를 두 개 이상 실행할 때 마지막 결과만 보이던 제약을 제거하고, Data Output 영역과 각 컬럼을 마우스로 넓혀 볼 수 있도록 개선합니다.

## 변경 사항

- `/sql/execute`는 기존 마지막 결과(`columns`, `rows`)를 유지하면서 모든 SELECT 결과를 `result_sets`로 추가 반환합니다.
- 각 result set에는 실행 순서, 원 SQL 순서, SQL 미리보기, columns, rows, row_count, truncated 상태가 포함됩니다.
- Frontend Data Output에 `Result 1`, `Result 2` ... 탭을 표시하며 각 SELECT 결과를 전환할 수 있습니다.
- 기존 동작과의 호환성을 위해 새 실행 직후에는 마지막 SELECT 결과를 기본 선택합니다.
- Data Output 패널의 왼쪽 경계를 좌우로 드래그해 결과 영역 폭을 조절할 수 있으며 폭은 localStorage에 저장됩니다.
- 각 컬럼 헤더 오른쪽 경계를 좌우로 드래그하여 해당 컬럼 폭을 72~720px 범위에서 조절할 수 있습니다.
- 기존 전체 하단 패널의 상하 높이 조절 기능은 그대로 유지합니다.
- SQL 결과 표시는 `src/components/database/SqlResultsPane.tsx`로 분리하여 TypeScript 경계를 추가했습니다.

## 호환성

- 기존 `/sql/execute`의 top-level `columns`, `rows`, `row_count`는 마지막 SELECT 결과를 계속 가리킵니다.
- `statement_results`는 기존과 동일하게 유지됩니다.
- PostgreSQL, Supabase PostgreSQL, MSSQL, Oracle, SQLite3 등 기존 SQL Workspace 실행 흐름을 변경하지 않습니다.
