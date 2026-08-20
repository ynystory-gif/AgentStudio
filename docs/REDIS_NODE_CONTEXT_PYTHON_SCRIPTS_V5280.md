# v5.280 Redis 노드 우클릭 Python 코드 생성

- Redis Key Browser의 그룹 및 실제 Key 노드에 Context Menu를 추가합니다.
- Redis 연결코드, 리스트 조회, 조회, 등록, 수정, 삭제 Python 템플릿을 임시 파일로 생성합니다.
- 실제 Key는 STRING/HASH/LIST/SET/ZSET/STREAM 타입에 따라 redis-py 명령을 맞춰 생성합니다.
- 그룹 노드는 `prefix:*` 범위의 SCAN 기반 목록 코드와 그룹 하위 Key용 CRUD 템플릿을 생성합니다.
- 생성 위치: `.agentstudio/redis_scratch/*.py`
- 생성만 수행하며 자동 실행하지 않습니다.
- 삭제 템플릿은 `CONFIRM_DELETE = False`가 기본입니다.
- 저장된 비밀번호는 소스에 복사하지 않고 `REDIS_PASSWORD` 환경변수 또는 실행 시 입력을 사용합니다.
