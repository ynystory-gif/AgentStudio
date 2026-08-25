# v5.312 Schema Full Diagram View

## 목적

DB Object Explorer에서 PostgreSQL / Supabase PostgreSQL의 **스키마 노드 우클릭 → 전체 다이어그램 보기**를 지원합니다.

## 동작

- 선택한 스키마의 모든 BASE TABLE을 ERD에 포함합니다.
- 선택 스키마 내부에서 서로 연결된 Foreign Key 관계를 모두 표시합니다.
- 다른 스키마로 나가는 FK는 전체 스키마 뷰의 범위를 벗어나므로 표시하지 않습니다.
- `.agentstudio/sql_scratch/diagram_schema_<schema>_*.agentdiag.json` 임시 파일을 생성하고 코드 탭에서 전용 Diagram Viewer로 엽니다.
- DB 변경 SQL은 실행하지 않습니다.

## Viewer

- 테이블 수에 따라 2~8개 열로 자동 배치합니다.
- 같은 열에 배치된 테이블끼리의 FK도 우회 경로로 표시합니다.
- 빈 영역 드래그 이동, 50~200% 확대/축소를 지원합니다.
- 기존 `PNG 내보내기`를 그대로 사용하며 전체 스키마 다이어그램을 흰 배경 2배 해상도 PNG로 저장합니다.

## 호환성

- 기존 테이블 우클릭 `다이어그램 보기`는 그대로 유지합니다.
- PostgreSQL / Supabase PostgreSQL에만 제공하며, 다른 DB Provider에서는 안내 메시지를 표시합니다.
- v5.311의 Multi SELECT 결과 탭 및 리사이즈 기능을 유지합니다.
