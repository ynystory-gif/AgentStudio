# v5.277 Redis Database Provider Support

## 목적
AgentStudio SQL Workspace의 DB 연결 목록에 Redis를 추가합니다. Redis는 SQL 데이터베이스가 아니라 NoSQL Key-Value 데이터베이스로 취급합니다.

## 연결 설정
- Host: 기본 `127.0.0.1`
- Port: 기본 `6379`
- Redis DB index: 기본 `0`
- Username: Redis ACL을 사용할 때만 입력
- Password: 선택 입력, Windows에서는 기존 연결 프로필과 동일하게 DPAPI Current User 범위로 저장 가능
- Driver: `redis-py`

## 동작
- `redis.Redis(...).ping()`으로 실제 연결/인증을 확인합니다.
- 저장된 Redis 연결은 다른 DB 프로필과 동일하게 프로젝트별 다중 연결 목록에 유지됩니다.
- Redis는 SQL 실행 및 SQL Object Explorer 대상이 아닙니다.
- 연결 성공 시 Redis PING 정상 상태와 선택한 DB index를 표시합니다.

## 의존성
`backend/requirements.txt`에 `redis>=5.0`을 추가합니다.
