# v5.377 Execution Stop Lifecycle + ERD Obstacle Routing + Env Example Only Setup

## 1. Agent 개발 완료 후 전역 실행 정지 버튼

Agent Factory Background Job가 SUCCESS / FAILED / CANCELLED 상태로 끝나면 Frontend의
`activeWorkflowJobId`를 즉시 해제합니다. 완료된 Job ID 때문에 상단 `실행 정지` 버튼이
계속 활성화되는 문제를 방지합니다.

## 2. DB ERD 관계선 라우팅

- 인접 컬럼 관계는 테이블 사이 빈 공간에 관계별 전용 vertical lane을 배정합니다.
- 두 컬럼 이상 떨어진 관계는 테이블을 가로지르지 않고 상단/하단 routing corridor로 우회합니다.
- 동일 컬럼 관계는 테이블 좌/우 바깥 corridor를 사용합니다.
- 관계선은 서로 구분하기 쉽도록 lane offset과 흰색 halo를 사용합니다.
- 관계가 많은 전체 Schema에서는 FK 이름 라벨을 생략하고 hover title로 확인하여 화면 혼잡도를 줄입니다.
- 관계선은 테이블 렌더링 이후 표시하되, obstacle-free route를 사용하여 테이블 내부를 관통하지 않습니다.

## 3. 생성 Agent의 .env 보호

`SYSTEM_ADMIN.cmd` / `SYSTEM_ADMIN.ps1`은 사용자의 `.env` 파일을 생성하거나 수정하지 않습니다.
필수 설정이 없으면 `.env.example`에 필요한 Key, 용도, 형식, 예시를 보강하고 `.env.example`만 엽니다.
사용자는 기존 `.env`, `backend/.env` 또는 OS 환경변수에 실제 값을 직접 관리합니다.

대표 예시:

```dotenv
# PostgreSQL 연결 URL (DATABASE_URL)
# 형식: postgresql://사용자:비밀번호@호스트:포트/데이터베이스명
# 로컬 예시: postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE

# Redis 연결 URL (REDIS_URL)
# 형식: redis://호스트:포트/DB번호
# 로컬 예시: redis://127.0.0.1:6379/0
REDIS_URL=redis://127.0.0.1:6379/0
```
