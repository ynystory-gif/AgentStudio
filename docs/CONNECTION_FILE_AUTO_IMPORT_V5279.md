# v5.279 Supabase / Redis 연결 파일 자동 등록

DB 연결 패널에서 Supabase와 Redis의 연결 설정 파일을 선택하면 Backend가 파일을 분석하여 연결 입력란에 자동 등록합니다.

## Supabase
- `JSON 파일 찾기 / 로드` 버튼 제공
- PostgreSQL Connection URL 또는 Host/Port/Database/User/Password/SSL 필드를 분석
- Firebase/Google Service Account JSON은 Supabase 정보로 오인하지 않고 명확히 거부

## Redis
- `파일 찾기 / 로드` 버튼 제공
- `.py`, `.json`, `.env`, `.txt` 지원
- Python 파일은 실행하지 않고 `ast`로 `redis.Redis(...)` / `Redis.from_url(...)` 상수 인자만 분석
- Redis URL 및 REDIS_HOST/PORT/DB/USERNAME/PASSWORD 형태 지원

## 보안
- 가져온 비밀번호는 UI 입력란에만 자동 채워지며 로그에 원문을 표시하지 않습니다.
- 영구 저장은 기존 `연결 정보 저장` 버튼을 눌렀을 때만 수행하며 Windows DPAPI 정책을 그대로 사용합니다.
- 최대 2MB 파일만 분석합니다.
