# v5.310 Database Table Diagram + PNG Export

## 범위

- PostgreSQL 및 Supabase PostgreSQL 테이블 우클릭 메뉴에 `다이어그램 보기` 추가
- 선택 테이블과 직접 연결된 FK 이웃 테이블 메타데이터 조회
- `.agentstudio/sql_scratch/*.agentdiag.json` 임시 문서 생성
- AgentStudio 코드 탭에서 전용 ERD Viewer로 렌더링
- PK / FK / 컬럼 타입 / NULL 여부 / FK 관계선 표시
- `PNG 내보내기`로 전체 다이어그램을 2배 해상도 PNG로 브라우저 저장

## 안전성

다이어그램 조회는 PostgreSQL catalog/information schema 메타데이터만 읽습니다. CREATE/ALTER/DROP/DML은 수행하지 않습니다. 생성되는 파일은 프로젝트의 `.agentstudio/sql_scratch` 임시 영역에만 저장됩니다.
