# v5.309 PostgreSQL Schema Profile Support

일반 PostgreSQL(Local/Docker/원격) SQL Workspace 연결에도 Schema를 저장하고 실제 세션 search_path에 적용합니다.

- PostgreSQL 기본 Schema: `public`
- PostgreSQL search_path: `<schema>, public`
- Supabase는 기존 지원을 유지: `<schema>, extensions, public`
- 연결 시 `to_regnamespace()`로 존재 여부를 확인하고 `current_schema()`가 선택 Schema와 일치하는지 검증합니다.
- 저장 프로필의 `schema_name` 필드를 그대로 사용하므로 기존 Supabase 프로필과 저장 형식이 호환됩니다.
