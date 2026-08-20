# v5.278 Redis Key Browser / Value Inspector

## 목적
Redis 연결이 PING 성공 안내만 표시하고 아래 Object Explorer 영역이 비어 보이던 문제를 개선합니다.

## 변경 사항
- Backend에 `/api/sql/redis/keys`, `/api/sql/redis/key` 읽기 전용 API 추가
- Key 목록은 Redis `SCAN`을 사용하며 최대 조회 수를 제한
- STRING/HASH/LIST/SET/ZSET/STREAM 타입, TTL, 길이, MEMORY USAGE 조회
- `:` namespace를 폴더 형태로 그룹화한 Key Tree
- Key 이름/패턴 및 타입 필터
- 선택 Key 상세 Value Inspector
- 대용량 값은 일부만 표시하여 UI/Redis 부하 제한

## 안전 원칙
Redis Browser는 v5.278에서 읽기 전용입니다. SQL 실행 경로와 분리하며 Key 삭제/수정은 자동 수행하지 않습니다.
