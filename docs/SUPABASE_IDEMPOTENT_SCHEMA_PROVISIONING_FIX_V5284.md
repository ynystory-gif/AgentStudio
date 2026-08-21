# v5.284 SupabaseIdempotentSchemaProvisioningFix

## 목적

Supabase PostgreSQL을 신규 설치하거나 기존 AgentStudio 스키마를 업그레이드할 때 같은 작업을 반복 실행해도 기존 데이터를 삭제하지 않고 안전하게 스키마를 준비합니다.

## 처리 순서

1. Supabase `SELECT 1` 연결 확인
2. `vector` 확장 사용 가능 여부 및 설치 상태 확인
3. 하나의 PostgreSQL transaction 안에서 AgentStudio ORM 테이블 `create_all()` 실행
4. 기존 AgentStudio 호환 ALTER migration 실행
5. SQLAlchemy metadata 기반 누락 index 보정
6. 테이블 / 컬럼 / PK / UNIQUE / INDEX / FK 재검증
7. transaction commit
8. 설치된 `langgraph-checkpoint-postgres`의 `AsyncPostgresSaver.setup()` 실행
9. `checkpoint_migrations`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` 재검증
10. 모든 검증이 성공한 경우에만 Supabase Runtime DB로 전환

## 실패 정책

- AgentStudio transaction 단계 실패: 해당 transaction rollback
- LangGraph migration 실패: AgentStudio 테이블은 유지하되 Runtime DB는 로컬 PostgreSQL 유지
- Runtime 전환 중 실패: SQLAlchemy runtime, LangGraph runtime, 로컬 `app_settings` provider 상태를 `local`로 복구 시도
- `DROP TABLE`, `TRUNCATE`, 사용자 데이터 `DELETE`는 수행하지 않음

## SQL 파일

`backend/sql/supabase_agentstudio_full_schema.sql`

수동 SQL은 AgentStudio ORM/pgvector만 멱등 준비합니다. LangGraph Checkpointer 테이블은 라이브러리 버전과 수동 SQL의 충돌을 막기 위해 수동 정의하지 않으며 프로그램의 공식 `setup()` migration을 사용합니다.
