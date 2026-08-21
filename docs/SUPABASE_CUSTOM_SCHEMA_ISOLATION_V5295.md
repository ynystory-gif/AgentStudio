# v5.295 Supabase Custom Schema Isolation

## 목적
Supabase의 `public` 스키마에 AgentStudio 테이블이 섞이지 않도록 전용 사용자 스키마를 사용합니다.

## 기본 구조
- `theanova_agentstudio`: AgentStudio ORM 테이블 + LangGraph Checkpointer 테이블
- `extensions`: pgvector `vector` extension
- `public`: 다른 애플리케이션/일반 사용자 데이터

## 설정
`backend/.env`:

```env
SUPABASE_DB_SCHEMA=theanova_agentstudio
```

Supabase Runtime 설정 화면에서도 같은 값을 변경할 수 있습니다.

## Runtime 안전장치
1. 스키마명은 안전한 PostgreSQL identifier 형식만 허용합니다.
2. SQLAlchemy ORM은 `schema_translate_map`으로 테이블을 전용 스키마에 명시적으로 연결합니다.
3. PostgreSQL 연결에는 `theanova_agentstudio,extensions,public` search_path를 적용합니다.
4. pgvector가 `extensions` 이외의 스키마에 있으면 자동 이동하지 않고 명시적으로 실패합니다.
5. LangGraph Python Checkpointer는 upstream explicit-schema 옵션이 아직 없으므로 연결 search_path를 사용합니다.
6. Supabase transaction pooler보다 direct/session pooler 사용을 권장합니다.
7. 전환 실패 시 기존 로컬 PostgreSQL runtime으로 복귀합니다.

## 기존 기능
v5.294의 Terminal Stop, Redis Live TTL, Firestore compact field 기능과 v5.293 TypeScript Foundation을 그대로 유지합니다.
