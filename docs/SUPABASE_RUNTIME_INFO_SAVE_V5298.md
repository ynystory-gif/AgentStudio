# v5.298 Supabase Runtime Info Save

## 목적
Supabase DATABASE URL을 시스템 관리 화면에 매번 다시 입력해야 하는 불편을 제거합니다.

## 저장 정책
- 저장 위치: `backend/.env`
- 저장 키: `SUPABASE_DATABASE_URL`, `SUPABASE_LANGGRAPH_DATABASE_URL`, `SUPABASE_DB_SCHEMA`
- PostgreSQL `app_settings`에는 비밀번호/URL 원문을 저장하지 않습니다.
- 브라우저 `localStorage`에도 저장하지 않습니다.
- API 응답은 URL 원문을 반환하지 않습니다.

## 동작
1. Supabase 연결 정보를 입력합니다.
2. `Supabase 정보 저장`을 누릅니다.
3. Backend가 URL 형식과 6543 Transaction Pooler 사용 여부를 검증한 뒤 `.env`에 원자적으로 저장합니다. LangGraph URL 입력이 비어 있고 기존 별도 저장값이 있으면 그 값을 유지하며, 별도 값이 없으면 DATABASE URL 자동 파생 모드를 사용합니다.
4. 저장 성공 후 Frontend의 URL 입력 상태를 비웁니다.
5. 이후 `Supabase 스키마 준비/검증` 또는 `Supabase PostgreSQL 사용 적용`에서 입력칸이 비어 있으면 저장값을 자동 사용합니다.
6. 정보 저장 자체는 현재 Runtime Provider를 전환하지 않습니다.
