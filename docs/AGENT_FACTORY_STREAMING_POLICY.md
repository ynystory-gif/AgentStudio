# Agent Factory Streaming Policy — Day 9

## 목적

Streaming은 모든 Agent의 기본 기능이 아닙니다.
AgentStudio가 사용자 요구를 분석해 필요성을 판단하고,
필요할 때 적절한 프로토콜/실행/클라이언트/테스트 구조를 생성합니다.

## 판단 흐름

```text
실시간 출력 필요?
  ├─ 아니오 → 일반 HTTP
  └─ 예
      ↓
양방향 통신 필요?
  ├─ 예 → WebSocket 검토
  └─ 아니오
      ↓
서버→클라이언트 연속 이벤트?
  ├─ 예 → SSE
  └─ 아니오 → Polling/HTTP 검토
```

## SSE Agent 기본 구조

```text
LLM / chain.astream
        ↓
Async Generator
        ↓
SSE Encoder
        ↓
StreamingResponse
        ↓
Reverse Proxy
        ↓
Client Parser
        ↓
UI
```

## Event Contract

- message
- done
- error

Error event에는 내부 exception 원문을 노출하지 않습니다.

## Runtime

- async endpoint → astream
- client disconnect → CancelledError 분리
- proxy buffering → 배포 환경별 설정
- timeout → 환경별 설정
- TTFT/latency → 관찰 가능 구조 권장

## Test

- curl -N
- httpx AsyncClient
- message/done/error
- disconnect
- proxy buffering
- timeout
- TTFT
