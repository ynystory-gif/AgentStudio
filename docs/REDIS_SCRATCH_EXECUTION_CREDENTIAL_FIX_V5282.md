# Redis Scratch Execution Credential Fix v5.282

## 문제
Redis 우클릭 메뉴로 생성된 Python 파일이 비밀번호가 환경변수에 없으면 `getpass.getpass()`를 호출했습니다. AgentStudio의 persistent Python worker는 사용자 stdin 프롬프트를 지원하지 않아 실행이 `실행 중...`에서 멈출 수 있었습니다.

## 수정
- 생성 코드에서 `getpass`를 제거했습니다.
- Redis scratch 파일에 연결 ID 메타데이터를 기록합니다.
- `/python/execute`가 Redis scratch 파일을 실행할 때 저장 프로필의 DPAPI 자격증명을 backend 내부에서만 복호화합니다.
- 자격증명은 worker 요청의 환경변수로만 전달하고 코드 실행 후 즉시 이전 환경으로 복원합니다.
- 비밀번호는 파일/Frontend/API 응답/로그에 포함하지 않습니다.
- v5.280 legacy scratch는 연결 이름 또는 현재 활성 Redis 연결을 fallback으로 사용합니다.
