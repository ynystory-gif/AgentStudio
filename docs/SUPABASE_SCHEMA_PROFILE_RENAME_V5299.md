# v5.299 Supabase Schema Profile + Saved Connection Rename

## Supabase Schema
- SQL Workspace의 Supabase 연결 프로필에 `schema_name`을 저장합니다.
- UI 기본값은 `public`이며 `theanova_agentstudio` 등 사용자 스키마를 입력할 수 있습니다.
- 연결 시 psycopg 세션에서 `SET search_path TO <schema>, extensions, public`을 안전한 Identifier quoting으로 적용합니다.
- Connection URL/JSON의 `schema`, `schema_name`, `search_path`, `options=-csearch_path=...`를 가능한 범위에서 자동 감지합니다.

## 저장 DB 연결 이름 변경
- 모든 DB Provider의 저장 프로필 이름을 connection_id 기준으로 변경합니다.
- 비밀번호/DPAPI secret, DB 접속 정보, live runtime connection은 변경하지 않습니다.
- 같은 프로젝트 안에서 이름 중복 시 `이름 2`, `이름 3` 방식으로 자동 조정합니다.
- 기존 `연결 정보 저장`과 별개로 `연결 이름 변경` 전용 API/UI를 제공합니다.
