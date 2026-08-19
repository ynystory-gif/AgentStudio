# THEANOVA AgentStudio DB 저장 정책

## 고정 원칙

모든 DB 저장은 FastAPI를 통과합니다.

```text
React / Agent / MCP Tool / Local UI
              ↓ HTTP
          FastAPI API
              ↓
        Application Service
              ↓
        DatabaseGateway
              ↓
      SQLAlchemy AsyncSession
              ↓
          PostgreSQL
```

## 금지

Frontend 또는 생성된 Agent 클라이언트 코드에서 다음을 직접 사용하지 않습니다.

- psycopg / asyncpg 직접 연결
- SQLAlchemy Engine 직접 생성
- PostgreSQL URL을 React 코드에서 사용
- DB 비밀번호를 Frontend에 전달
- 브라우저에서 PostgreSQL로 직접 접속

## Bootstrap 예외

`DATABASE_URL`, `LANGGRAPH_DATABASE_URL`, `POSTGRESQL18_ROOT`는
Backend가 PostgreSQL에 최초 접속하기 위해 필요한 bootstrap 정보입니다.

이 값도 Frontend가 DB에 직접 사용하는 것이 아니라 FastAPI Backend만 사용합니다.
