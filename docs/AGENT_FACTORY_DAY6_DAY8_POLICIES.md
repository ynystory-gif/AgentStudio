# Agent Factory Design Policies — Day 6~8 Consolidation

THEANOVA AgentStudio에서 Day 6~8 자료를 단순 Coding Rule 목록이 아닌
Agent 생성 설계 계층으로 통합합니다.

## Policy Layers

1. ASYNC_STRATEGY_POLICY
2. DEPENDENCY_LIFECYCLE_POLICY
3. API_CONTRACT_POLICY
4. FILE_PLACEMENT_POLICY
5. API_ERROR_SECURITY_POLICY
6. AGENT_API_TEST_POLICY

## FastAPI Agent 생성 흐름

```text
사용자 요구
  ↓
FastAPI/API 후보 판단
  ↓
File Placement
  ↓
Request/Response Contract
  ↓
Dependency Lifecycle
  ↓
Async Strategy
  ↓
Error/Security Strategy
  ↓
Code Generation
  ↓
Static Validator
  ↓
Runtime Test
  ↓
Repair / Re-test
```

## 핵심 원칙

- 교육 예시 숫자를 글로벌 규칙으로 고정하지 않는다.
- 코드 생성 전에 파일 배치와 dependency lifecycle을 결정한다.
- 외부 입력은 trust boundary에서 검증한다.
- Request/Response DTO와 내부 모델을 분리한다.
- 공유 가능한 client만 singleton/cache 후보로 본다.
- 요청별 사용자 상태를 singleton으로 공유하지 않는다.
- 정리 필요한 자원은 yield lifecycle을 사용한다.
- 오류는 서버 로그와 client response를 분리한다.
- 코드 생성 성공이 아니라 실행/검증/재수정 완료를 목표로 한다.
