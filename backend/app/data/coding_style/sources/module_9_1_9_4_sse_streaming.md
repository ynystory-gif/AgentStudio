# SSE 스트리밍

# 📋 오리엔테이션

---

## 핵심 메시지

### 토큰 하나가 생성될 때마다 클라이언트로 흘려 보냅니다

| 항목 내용        |                                                         |
| ------------ | ------------------------------------------------------- |
| **학습 목표**    | SSE 스트리밍 엔드포인트를 구현하고 curl과 Python 클라이언트로 토큰 단위 수신을 확인한다 |
| **내일 필수 요건** | `/chat/stream` 엔드포인트 (필수 요건 4번)                         |

---

## 모듈 구성

| # 모듈명  |                   |
| ------ | ----------------- |
| 9-1    | 스트리밍 개념 & 방식 비교   |
| 9-2    | SSE 스트리밍 구현       |
| 9-3    | 클라이언트 테스트 & 에러 처리 |
| 9-4    | 가이드 실습 (개인)       |

---

---

# 📦 모듈 9-1 · 스트리밍 개념 & 방식 비교

| 항목 내용     |                                                  |
| --------- | ------------------------------------------------ |
| **모듈 목표** | SSE가 왜 LLM 응답에 최적인지 설명하고, 세 가지 스트리밍 방식의 차이를 비교한다 |
| **선수 지식** | Day 6 async/await, Day 7\~8 FastAPI 기초           |
| **난이도**   | 🔰 기본                                            |

---

## 📚 강의 교안

### 핵심 개념

**LLM 스트리밍은 “사용자가 기다리는 방식”을 근본적으로 바꿉니다.**

ChatGPT가 처음 공개됐을 때 가장 인상적이었던 것은 정확도만이 아닙니다. 텍스트가 **타이핑되는 것처럼 한 글자씩 흘러나오는 경험** 자체가 이전 AI 서비스와 완전히 달랐습니다. 응답을 5초 기다렸다가 한 번에 받는 것과, 0.3초 만에 첫 글자가 등장해 3초에 걸쳐 완성되는 것 — 전체 소요 시간이 같더라도 사용자가 느끼는 속도감은 완전히 다릅니다. 이 경험을 만드는 기술이 바로 스트리밍이고, 오늘 우리는 그 구현 방법 중 하나인 **SSE(Server-Sent Events)** 를 선택한 이유와 동작 원리를 이해합니다.

---

### 상세 설명

#### 9-1 | **1. 왜 스트리밍인가 — 숫자로 보는 UX 차이**

동일한 5초짜리 LLM 응답이라도 전달 방식에 따라 사용자 경험이 극적으로 달라집니다.

| 일반 HTTP (배치) 스트리밍 (SSE)  |               |                         |
| ------------------------ | ------------- | ----------------------- |
| **첫 응답까지 대기**            | 5.0초          | **0.3\~0.8초** (첫 토큰 기준) |
| **사용자가 느끼는 속도**          | 느림            | **3\~5배 빠르게 체감**        |
| **5초 동안 화면 상태**          | 빈 화면 → 텍스트 전체 | 글자가 계속 타이핑됨             |
| **서버 자원 사용**             | 생성 후 전송       | 생성과 전송 동시 진행            |
| **구현 복잡도**               | 낮음            | 중간 (오늘 배울 내용)           |

첫 번째 토큰이 도달하는 데 걸리는 시간을 **TTFT(Time To First Token)** 라고 합니다. 오늘 실습 노트북에서 TTFT를 직접 측정할 수 있습니다 (9-4 실습 노트북 심화 ②). LLM API 벤더들이 스트리밍 엔드포인트를 기본으로 제공하는 이유가 여기에 있습니다 — 동일한 모델·동일한 비용으로 훨씬 나은 사용자 경험을 줄 수 있기 때문입니다.

> 💡 **핵심**: 같은 5초짜리 응답이라도 배치(일반 HTTP)는 5초 동안 빈 화면이고, SSE는 0.3초에 첫 글자가 나타나 계속 타이핑됩니다. 위 표의 “3\~5배 빠른 체감”은 실제 속도가 아니라 사용자 지각의 차이입니다 — 진행 중임을 시각적으로 확인할 수 있을 때 기다림이 훨씬 짧게 느껴집니다. 단 TTFT는 서버 부하·모델 크기에 따라 크게 달라지므로 항상 동일한 수치를 보장하지는 않습니다.

---

#### **9-1 | 2. 세 가지 방식 비교 — SSE를 선택하는 이유**

LLM 서비스에서 실시간 데이터를 전달하는 방법은 크게 세 가지입니다.

| 방식 방향성 연결 방식 LLM 적합성 구현 복잡도 기존 인프라 호환  |            |            |            |    |             |
| -------------------------------------- | ---------- | ---------- | ---------- | -- | ----------- |
| **SSE**                                | 서버 → 클라이언트 | HTTP 지속 연결 | ✅ **최적**   | 낮음 | ✅ 그대로 사용    |
| **WebSocket**                          | 양방향        | 프로토콜 업그레이드 | 가능 (과잉 설계) | 높음 | ⚠️ 추가 설정 필요 |
| **폴링**                                 | 주기적 재요청    | 반복 HTTP 요청 | ❌ 비효율      | 낮음 | ✅ 그대로 사용    |

LLM의 토큰 생성은 본질적으로 **단방향(서버 → 클라이언트)** 입니다. 사용자가 질문을 보내면 LLM이 답변 토큰을 생성해 보내줄 뿐, 스트리밍 도중 클라이언트가 서버에 추가 데이터를 보낼 이유가 없습니다. 이 흐름에 양방향 프로토콜인 WebSocket을 쓰는 것은 오버엔지니어링입니다.

폴링 방식의 문제는 더 심각합니다. 5초짜리 응답에 0.5초 간격 폴링을 적용하면 **약 10번의 불필요한 HTTP 요청**이 발생합니다.

> 💡 **핵심**: LLM 토큰 스트리밍은 단방향이므로 SSE가 최적입니다 — WebSocket은 양방향 협업 도구(Google Docs 방식)에, 폴링은 알림 뱃지처럼 빈도 낮은 상태 확인에 씁니다. 폴링을 스트리밍에 쓰면 5초 응답에 0.5초 간격 10번 요청이 발생하고, 완성 전까지 중간 결과를 보여줄 방법 자체가 없습니다. 단 SSE는 HTTP/1.1에서 도메인당 최대 6개 연결을 점유하므로, 동시 스트림이 많은 경우 HTTP/2 전환이 필요합니다.

---

#### **9-1 | 3. SSE 프로토콜 구조 — 단순함이 강점**

SSE는 놀라울 정도로 단순한 텍스트 기반 프로토콜입니다. HTTP 응답 헤더에 `Content-Type: text/event-stream`을 설정하고 아래 형식으로 데이터를 계속 전송하면 됩니다.

```
# SSE 전체 스트림 예시 — "파이썬" 3글자를 3번에 나눠 전송하는 경우
# ─────────────────────────────────────────────────────────────
# 규칙:
#  · "event: [타입]" — 이벤트 종류 (생략 시 기본값 "message")
#  · "data: [내용]"  — 전달할 데이터 (JSON 형식 권장)
#  · 빈 줄 하나      — 이벤트 하나의 끝을 나타내는 구분자
# ─────────────────────────────────────────────────────────────

event: message
data: {"content": "파"}

event: message
data: {"content": "이"}

event: message
data: {"content": "썬"}

event: done
data: {"content": "[DONE]"}

```

**SSE 이벤트 타입 3가지**

| 이벤트 타입 용도 `data` 필드 예시  |            |                                |
| ----------------------- | ---------- | ------------------------------ |
| `message`               | 토큰 하나 전달   | `{"content": "파이"}`            |
| `done`                  | 스트리밍 완료 알림 | `{"content": "[DONE]"}`        |
| `error`                 | 오류 발생 알림   | `{"content": "APIError: ..."}` |

> 💡 **핵심**: SSE 프로토콜은 `event: [타입]\ndata: [JSON]\n\n` 세 줄 반복입니다. 이 단순한 텍스트 형식 덕분에 nginx·CloudFlare 등 기존 HTTP 인프라에서 별도 프로토콜 업그레이드 없이 작동합니다. 오늘 구현에서 `message`로 토큰을 흘리고, `done`으로 완료를 알리고, `error`로 예외를 전달합니다 — 9-2에서 `sse_event()` 함수가 이 형식을 생성하고, 9-3에서 `line.startswith("data:")` 파싱으로 소비합니다. 단 버퍼링 방지 헤더(`X-Accel-Buffering: no`)는 nginx 뒤 배포 시 반드시 추가해야 합니다.

---

### 💡 핵심 요약

- 스트리밍은 LLM 응답을 토큰이 생성되는 즉시 전송하는 방식으로, 동일한 5초 응답이라도 첫 글자를 0.3초 만에 보여줘 체감 속도를 3\~5배 높입니다
- LLM 응답은 서버→클라이언트 **단방향**이므로 SSE가 최적 — WebSocket은 양방향 협업 도구에, 폴링은 빈도 낮은 상태 확인에 적합합니다
- SSE는 `event: [타입]\ndata: [JSON]\n\n` 세 줄짜리 텍스트 형식으로, 기존 HTTP 인프라에서 별도 설정 없이 대부분 작동합니다
- 9-2에서 구현할 서버는 `message`(토큰) / `done`(완료) / `error`(오류) 세 가지 이벤트 타입을 사용합니다
- 첫 토큰까지 걸리는 시간인 **TTFT(Time To First Token)** 가 스트리밍 서비스의 핵심 성능 지표입니다

---

### 🔥 더 알아보기

**HTTP/2와 SSE의 조합**: HTTP/1.1에서는 SSE 연결 하나당 TCP 연결 하나를 점유합니다. 브라우저의 도메인당 최대 6개 HTTP/1.1 연결 제한으로 인해 SSE 연결이 많아지면 다른 리소스 요청이 밀릴 수 있습니다. HTTP/2에서는 단일 TCP 연결에서 멀티플렉싱으로 여러 스트림을 처리하므로 이 제한이 사라집니다. FastAPI + Uvicorn에서 HTTP/2를 활성화하려면 `pip install httptools h2` 추가 설치가 필요합니다.

**`Last-Event-ID`****로 끊긴 스트림 재연결**: SSE 스펙(W3C EventSource)에는 클라이언트가 연결이 끊겼을 때 `Last-Event-ID` 헤더를 포함해 자동 재연결하는 메커니즘이 내장되어 있습니다. 각 이벤트에 `id: [번호]` 필드를 추가하면, 재연결 시 클라이언트는 “마지막으로 받은 이벤트 ID”부터 이어서 수신할 수 있습니다. 대화 품질을 유지해야 하는 프로덕션 서비스에서 필수적인 패턴입니다.

---

### ⭐ 심화

> **폴링 방식으로 구현하면 실제로 얼마나 비효율적인가**
>
> 폴링의 비효율을 수치로 확인해 봅시다. 5초 응답에 0.5초 간격 폴링을 적용하면:
>
> - HTTP 요청 횟수: 10회
> - 각 요청의 응답 상태: 8회는 “아직 없음(204)” + 마지막 2회에 데이터
> - SSE 대비 서버 처리 부담: 약 **10배**
>
> 더 심각한 문제는 **응답 완성 전까지 부분 결과를 보여줄 수 없다**는 점입니다. SSE는 토큰 하나가 생성될 때마다 즉시 전달하지만, 폴링은 “완성된 결과”만 전달할 수 있어 스트리밍 경험을 근본적으로 제공할 수 없습니다.

---

---

# 📦 모듈 9-2 · SSE 스트리밍 구현

| 항목 내용     |                                                                |
| --------- | -------------------------------------------------------------- |
| **모듈 목표** | async generator로 토큰을 SSE 형식으로 yield하는 엔드포인트를 v1→v2→v3 단계로 구현한다 |
| **선수 지식** | 9-1 SSE 프로토콜 형식, Day 6 async/await, Day 7\~8 FastAPI Depends   |
| **난이도**   | 🔰⭐ 기본+심화                                                      |

---

## 📚 강의 교안

### 핵심 개념

**async generator는 LLM 토큰 스트리밍을 위한 가장 자연스러운 파이썬 구조입니다.**

LangChain의 `chain.astream()`은 LLM이 토큰을 하나 생성할 때마다 즉시 반환합니다. 이 토큰들을 받아서 HTTP 채널로 흘려보내는 중간 역할이 필요한데, 이 역할에 정확히 맞는 파이썬 구조가 **async generator**입니다. “비동기로 여러 값을 하나씩 내보내는 함수”라는 개념이 처음에는 낯설게 느껴질 수 있지만, 원리를 이해하면 “이것 말고 다른 방법이 있을까?”라는 생각이 들 정도로 딱 맞는 추상화입니다.

이 모듈에서는 async generator의 개념을 이해한 뒤, SSE 유틸리티 함수를 작성하고 v1→v2→v3 단계로 스트리밍 엔드포인트를 완성합니다.

---

### 상세 설명

#### **9-2 | 1. 네 가지 함수 유형 비교 — async generator의 위치**

파이썬에는 “동기/비동기” × “단일 반환/다중 반환” 조합으로 네 가지 함수 유형이 있습니다.

| 유형 선언 방식 반환 방식 소비 방법 LLM 스트리밍 적합성  |                        |              |                       |          |
| ---------------------------------- | ---------------------- | ------------ | --------------------- | -------- |
| **일반 함수**                          | `def f():`             | `return` 1회  | `result = f()`        | ❌ 단일 반환  |
| **Generator 함수**                   | `def f(): yield`       | `yield` 여러 번 | `for x in f():`       | ❌ 동기만    |
| **async 함수**                       | `async def f():`       | `return` 1회  | `result = await f()`  | ❌ 단일 반환  |
| **async generator**                | `async def f(): yield` | `yield` 여러 번 | `async for x in f():` | ✅ **최적** |

LLM 토큰 스트리밍에는 두 가지 조건이 동시에 필요합니다. ① LLM API 호출을 기다려야 하므로 **비동기** 필수, ② 토큰이 여러 개이므로 **다중 반환** 필수. 이 두 조건을 동시에 충족하는 것은 async generator 뿐입니다.

📓 **노트북 참조**: Step 1 “기본 스트리밍 소비”

```
# 네 유형 비교 — 동일한 "숫자 1, 2, 3을 비동기로 생성" 시나리오
import asyncio

# ① 일반 함수: 완성 후 리스트로 한 번에 → 스트리밍 불가
def f1():
    return [1, 2, 3]                         # 한 번에 전달

# ② Generator 함수: 하나씩이지만 동기 → await 불가
def f2():
    yield 1                                   # 일시 정지 → 1 전달
    yield 2                                   # 재개 → 2 전달
    yield 3                                   # 재개 → 3 전달

# ③ async 함수: 비동기지만 단일 반환 → 스트리밍 불가
async def f3():
    await asyncio.sleep(0)                    # 비동기 대기 가능
    return [1, 2, 3]                         # 하지만 한 번에 전달

# ④ async generator: 비동기 + 다중 반환 ← LLM 토큰 스트리밍에 정확히 대응
async def f4():
    for i in [1, 2, 3]:
        await asyncio.sleep(0)               # 각 토큰 생성 후 비동기 대기
        yield i                              # 하나씩 즉시 전달

# 소비 방법
result1 = f1()                               # [1, 2, 3]
for x in f2(): print(x)                     # 1, 2, 3 (동기)
result3 = await f3()                         # [1, 2, 3] ← Jupyter top-level await 전용
                                             #   .py에서는: asyncio.run(f3())
async for x in f4(): print(x)               # 1, 2, 3 (비동기) ← 오늘 패턴
                                             #   Jupyter top-level await 전용
                                             #   .py에서는: async def main(): async for x in f4(): ...
# 예상 출력: 1  2  3  (각 줄에 하나씩)

```

> 💡 **핵심**: async generator는 컨베이어 벨트처럼 제품(토큰)이 완성될 때마다 즉시 내보내는 구조입니다. `yield`는 “일시 정지 버튼이 달린 return” — 값 하나를 내보내되 함수를 종료하지 않고 다음 토큰이 생성될 때까지 기다립니다. 위 표에서 ④만이 “비동기 + 다중 반환” 두 조건을 동시에 충족하기 때문에, `chain.astream()`이 yield하는 토큰을 받아 SSE로 변환하는 `token_generator()`는 반드시 async generator여야 합니다. 단 일반 `.py` 파일에서는 `async for`를 `asyncio.run()` 안에서만 실행할 수 있습니다.

---

#### **9-2 | 2. LangChain** **`astream()`****과** **`token_generator`****의 관계**

`chain.astream()`은 LangChain이 제공하는 async generator입니다. 우리가 작성하는 `token_generator()`는 그 위에서 **SSE 형식 변환을 담당하는 중간 레이어**입니다.

```
# 전체 데이터 흐름
# ─────────────────────────────────────────────────────────────────
#
#  1. 사용자 요청 (POST /chat/stream)
#       │  ChatRequest {"message": "질문"}
#       ▼
#  2. chain.astream({"message": "질문"})        ← LangChain async generator
#       │  LLM이 토큰 하나 생성 → 즉시 AIMessageChunk 반환
#       ▼
#  3. token_generator() [우리가 작성]           ← SSE 변환 담당
#       │  AIMessageChunk → sse_event(token) 호출
#       │  "event: message\ndata: {...}\n\n" 문자열 yield
#       ▼
#  4. StreamingResponse(token_generator(), ...)  ← FastAPI HTTP 레이어
#       │  HTTP chunked transfer encoding으로 청크 단위 전송
#       ▼
#  5. 클라이언트 (curl -N / httpx / Streamlit)
#
# ─────────────────────────────────────────────────────────────────

```

> 💡 **핵심**: 위 흐름에서 **3번 단계만 우리가 작성**합니다. LangChain(2번)은 토큰 생성을, FastAPI(4번)는 HTTP 전송을 각자 처리합니다. `token_generator()`의 유일한 책임은 “LangChain AIMessageChunk → SSE 형식 문자열”로 변환하는 것입니다. 단 이 역할 분리 때문에 `chain.astream()`의 에러가 `token_generator()` 안에서 잡혀야 합니다 — 바깥에서 잡으면 이미 `StreamingResponse`가 시작된 후라 HTTP 상태 코드를 바꿀 수 없습니다.

---

#### **9-2 | 3. SSE 유틸리티 함수 — 왜 분리하는가**

스트리밍 엔드포인트마다 SSE 형식 문자열을 만드는 코드가 반복됩니다. 이 로직을 `app/utils/sse.py`로 분리하면 세 가지 이점이 있습니다.

| 이유 설명        |                                                                 |
| ------------ | --------------------------------------------------------------- |
| **재사용성**     | `/chat/stream`, `/docs/summary/stream` 등 여러 엔드포인트에서 동일하게 임포트    |
| **테스트 가능성**  | `sse_event()` 함수만 단위 테스트하면 모든 엔드포인트의 SSE 형식 검증 완료               |
| **구조 설계 중심** | Vibe Coding 원칙 — 로직을 역할별로 분리하는 습관이 Day 10 루브릭의 구조·설계 25점에 반영됩니다 |

```
# 터미널에서 먼저 실행 — 폴더와 파일 생성
mkdir -p app/utils
touch app/utils/__init__.py   # Python이 utils를 패키지로 인식 (Day 7 참조)
touch app/utils/sse.py        # 아래 코드를 이 파일에 작성

```

> ⚠️ `__init__.py` 없이 `from app.utils.sse import sse_event`를 실행하면 `ModuleNotFoundError: No module named 'app.utils'`가 발생합니다.

📓 **노트북 참조**: Step 2 “이벤트 타입 분기 처리”

```
# app/utils/sse.py
import json   # SSE data 필드에 JSON 직렬화를 위해 필요

def sse_event(data: str, event: str = "message") -> str:
    """
    SSE(Server-Sent Events) 형식 문자열을 생성합니다.

    SSE 프로토콜 규칙 (9-1에서 학습한 내용):
      · "event: [타입]\n"  — 이벤트 종류 지정 (기본값 "message")
      · "data: [JSON]\n"   — 전달할 데이터 (JSON 형식 권장)
      · "\n"               — 이벤트 끝 구분자 (빈 줄 하나)
      ※\n = 실제 줄바꿈 문자. 함수 반환값에서는 f-string의\n이 실제 newline으로 치환됩니다.
    """
    return (
        f"event:{event}\n"
        f"data:{json.dumps({'content': data}, ensure_ascii=False)}\n\n"
        # ensure_ascii=False: 한국어 등 비ASCII 문자를 유니코드 이스케이프 없이 전달
    )

# 동작 확인 (터미널에서 python app/utils/sse.py 로 실행)
if __name__ == "__main__":
    print(repr(sse_event("안녕")))
    # 예상 출력: 'event: message\ndata: {"content": "안녕"}\n\n'

    print(repr(sse_event("[DONE]", event="done")))
    # 예상 출력: 'event: done\ndata: {"content": "[DONE]"}\n\n'

```

> 💡 **핵심**: `sse_event()`는 9-1에서 배운 SSE 프로토콜 형식을 그대로 Python 문자열로 만들어 줍니다. `sse_event("파이")` 한 줄 호출이 `"event: message\ndata: {\"content\": \"파이\"}\n\n"` 문자열이 되고, `StreamingResponse`가 이를 HTTP 청크로 전달합니다. `app/utils/sse.py`로 분리한 이유는 `/chat/stream` 외에 다른 엔드포인트가 생길 때 이 함수를 그대로 임포트하기 위함입니다. 단 `__init__.py` 생성을 빠뜨리면 `ModuleNotFoundError`가 발생합니다.

---

#### **9-2 | 4. async 절대 규칙 재확인 — SSE에서도 동일하게 적용**

Day 6에서 선언한 “async def 안에서 동기 함수 호출 금지” 규칙이 스트리밍에서도 동일하게 적용됩니다.

```
# ❌ 절대 금지 — 동기 stream()을 async def 안에서 호출
@router.post("/stream")
async def chat_stream_wrong(request: ChatRequest):
    async def generate():
        # chain.stream()은 동기(sync) 메서드 — 이벤트 루프 전체가 블록됩니다
        for chunk in chain.stream({"message": request.message}):   # ❌ 동기!
            yield sse_event(chunk)
    return StreamingResponse(generate(), media_type="text/event-stream")

# ✅ 올바른 방법 — astream()으로 비동기 스트리밍
@router.post("/stream")
async def chat_stream_correct(request: ChatRequest):
    async def generate():
        # chain.astream()은 비동기(async) — 토큰 대기 중 다른 요청도 처리 가능
        async for chunk in chain.astream({"message": request.message}):   # ✅ 비동기!
            yield sse_event(chunk)
    return StreamingResponse(generate(), media_type="text/event-stream")

```

> ⚠️ **스트리밍에서 더 위험한 이유**: 일반 엔드포인트에서 `invoke()` 실수는 해당 요청만 블록합니다. 스트리밍에서 `stream()` 실수는 응답 완료까지 **수초\~수십 초** 동안 이벤트 루프를 독점합니다.

> 💡 **핵심**: `chain.stream()`(동기)을 `async def` 안에서 부르는 순간 이벤트 루프 전체가 그 요청에 묶입니다. 5초짜리 LLM 응답이면 5초 동안 서버 전체가 응답 불능입니다. `chain.astream()`(비동기)은 각 `await` 사이에 이벤트 루프를 반환해 동시에 다른 요청을 처리합니다. 단 `asyncio.sleep(0)` 한 줄로 이벤트 루프 공정성을 보장해야 긴 응답(1,000토큰+) 중에도 다른 접속자가 응답을 받을 수 있습니다.

---

#### **9-2 | 5. v1 → v2 → v3 빌드업 — 단계별 엔드포인트 완성**

세 버전을 만드는 이유는 각 단계에서 “무엇이 문제이고 왜 추가하는가”를 직접 확인하기 위해서입니다.

| 버전 핵심 추가 사항 남아 있는 문제  |                     |                                 |
| --------------------- | ------------------- | ------------------------------- |
| **v1**                | LLM 직접 스트리밍 (최소 동작) | SSE 형식 없음, 완료 신호 없음, 에러 처리 없음   |
| **v2**                | SSE 형식 + 완료 신호      | 에러 시 클라이언트에 알릴 방법 없음, nginx 버퍼링 |
| **v3**                | 에러 처리 + 프록시 헤더      | (프로덕션 수준 완성)                    |

**v1 · 가장 단순한 스트리밍**

📓 **노트북 참조**: Step 1-① “그대로 실행”

```
# app/routers/chat.py 에 추가 (v1 — 최소 동작 확인용)
# 주의: 이 코드는 라우터 파일 스니펫으로, load_dotenv()는 app/main.py에서 처리됩니다
# 상단 임포트에 추가: from fastapi.responses import StreamingResponse

@router.post("/stream-v1")
async def chat_stream_v1(
    request: ChatRequest,
    llm: ChatOpenAI = Depends(get_llm),
):
    """v1: 가장 단순한 스트리밍 — SSE 형식 없음, 에러 처리 없음"""
    async def generate():
        # llm.astream()으로 LLM을 직접 스트리밍
        # AIMessageChunk.content = 토큰 텍스트 (문자열)
        async for chunk in llm.astream(request.message):
            yield chunk.content         # ← 토큰 텍스트만 전달, SSE 형식 없음
            # 한계 ①: 토큰이 붙어서 나옴 — 이벤트 타입 구분 불가
            # 한계 ②: 스트림 종료 시점을 클라이언트가 알 수 없음

    return StreamingResponse(generate(), media_type="text/event-stream")

# curl 테스트:
# curl -N -X POST <http://localhost:8000/chat/stream-v1>
#      -H "Content-Type: application/json" -d '{"message": "파이썬 장점은?"}'
# 예상 출력: 파이썬의장점은...  (SSE event:/data: 구조 없이 텍스트만 나옴)

```

**v2 · SSE 형식 + 종료 신호 추가**

> ⚠️ **v2 실행 전 주의**: v2 코드는 `prompt_template`을 사용하는데, 이 변수는 v3 단계에서 처음 정의됩니다. v2를 단독으로 실행하려면 아래 v3의 `prompt_template` 선언을 먼저 파일에 추가하세요. v2는 “SSE 형식이 추가되는 단계”를 보여주는 교육용 중간 버전이며, 최종 팀 프로젝트 구현은 v3를 사용합니다.

```
# v2: v1 + SSE 형식 + 완료 신호
# 상단 임포트 추가: from app.utils.sse import sse_event
#
# v1 대비 구조 변화 두 가지:
#  ① llm.astream() → chain.astream(): StrOutputParser가 .content 추출을 자동화
#    (v1에서 chunk.content 로 직접 꺼내던 작업 불필요)
#  ② 문자열 입력 → dict 입력: prompt_template이 {message} 자리에 값을 채워넣음

@router.post("/stream-v2")
async def chat_stream_v2(
    request: ChatRequest,
    llm: ChatOpenAI = Depends(get_llm),
):
    """v2: SSE 형식 + [DONE] 신호 — 클라이언트가 종료를 감지할 수 있음"""
    chain = prompt_template | llm | StrOutputParser()

    async def generate():
        async for token in chain.astream({"message": request.message}):
            yield sse_event(token)                    # v1과 차이: SSE 형식으로 래핑
        yield sse_event("[DONE]", event="done")       # 종료 신호 추가

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},        # 중간 프록시의 캐싱 방지
    )

# v2 아직 없는 것:
#   · 에러 발생 시 클라이언트에 알릴 수 없음 (9-3 트러블슈팅 없는 버전)
#   · nginx 버퍼링 방지 헤더 없음 (9-3 트러블슈팅 표 1번 증상)

```

**v3 · 에러 처리 + 프록시 설정 (최종 버전)**

📓 **노트북 참조**: Step 1-③ “내 것에 적용”

```
# app/routers/chat.py 에 추가
# 주의: 이 코드는 라우터 파일 스니펫입니다. load_dotenv()는 app/main.py 또는
#       app/dependencies.py에서 처리됩니다.
# ↓ 상단 임포트에 반드시 추가하세요 ↓
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate      # ← 추가 필요
from langchain_core.output_parsers import StrOutputParser  # ← 추가 필요
from app.utils.sse import sse_event
import asyncio
import json   # 심화: done 이벤트에 token_count 포함 시 json.dumps() 사용

# 프롬프트 템플릿은 모듈 수준에서 한 번만 생성 (요청마다 재생성은 낭비)
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "유용한 AI 어시스턴트입니다."),
    ("human", "{message}"),
])

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    llm: ChatOpenAI = Depends(get_llm),
):
    """v3: v2 + 에러 처리 + 프록시 버퍼링 방지 (프로덕션 수준)"""
    chain = prompt_template | llm | StrOutputParser()

    async def token_generator():
        """토큰을 하나씩 SSE 형식으로 yield하는 async generator"""
        try:
            async for token in chain.astream({"message": request.message}):
                yield sse_event(token)
                await asyncio.sleep(0)
                # asyncio.sleep(0): "이벤트 루프에 잠깐 제어권을 돌려줘"
                # 0초 대기가 아니라 다른 코루틴이 실행될 기회를 줍니다

            yield sse_event("[DONE]", event="done")   # 정상 완료 신호

        except Exception as e:
            # v2와 차이: 에러를 event: error 로 클라이언트에 전달
            yield sse_event(str(e), event="error")

    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # nginx에게 "버퍼에 모으지 말고 즉시 전달해" 지시
            # 이 헤더 없이 nginx 뒤에 배포하면 9-3 트러블슈팅 표 1번 증상 발생
        },
    )

```

> 💡 **핵심**: v1→v2→v3의 핵심 발전은 “에러와 완료를 이벤트 타입으로 알리기”입니다. v1은 텍스트만, v2는 `event: message`/`event: done`으로 SSE 형식을 갖추고, v3는 `except Exception`을 `event: error`로 전달해 클라이언트가 재시도 UI를 표시할 수 있게 합니다. `X-Accel-Buffering: no` 헤더는 nginx 프록시 뒤에서 “이 응답은 버퍼링하지 말고 청크 단위로 즉시 전달하라”는 지시입니다. 단 이 헤더를 추가해도 CloudFlare 같은 CDN은 별도 설정이 필요할 수 있습니다.

---

### 💡 핵심 요약

- async generator(`async def` + `yield`)는 “비동기로 값을 여러 번 반환”하는 구조로, LLM 토큰 스트리밍(다중 반환 + 비동기 대기)에 정확히 대응하는 파이썬의 유일한 추상화입니다
- `yield`는 “일시 정지 버튼이 달린 return” — 값 하나를 반환하되 함수를 종료하지 않고 다음 호출을 기다립니다
- 데이터 흐름: `chain.astream()` (LangChain) → `token_generator()` (SSE 변환, 우리 코드) → `StreamingResponse` (FastAPI HTTP 레이어)
- SSE 유틸리티 함수는 `app/utils/sse.py`로 분리해 재사용·테스트 가능하게 관리합니다 — `__init__.py` 생성이 필수
- `await asyncio.sleep(0)`은 0초 대기가 아니라 “이벤트 루프에 제어권을 잠깐 반환”하는 관용구입니다

---

### 🔥 더 알아보기

**`asyncio.sleep(0)`****의 실제 동작 원리**: Python 이벤트 루프는 협력적 멀티태스킹(cooperative multitasking)을 기반으로 합니다. 코루틴이 `await`를 만나야만 이벤트 루프가 다른 코루틴을 실행할 기회를 얻습니다. `asyncio.sleep(0)`은 “즉시 완료되는 await” — 실질적인 대기 없이 다른 코루틴에게 실행 기회를 줍니다.

**generator 프로토콜과 disconnect 감지**: FastAPI의 `StreamingResponse`는 클라이언트가 연결을 끊으면 내부적으로 generator의 `aclose()`를 호출합니다. 9-4 심화 미션의 “disconnect 감지”가 이 메커니즘을 통해 `asyncio.CancelledError`로 나타납니다.

---

### ⭐ 심화

> **종료 이벤트에 토큰 사용량 포함하기**

LLM API는 응답 완료 후 사용된 토큰 수를 반환합니다. 스트리밍에서는 마지막 `done` 이벤트에 이 정보를 포함해 클라이언트가 비용을 추적할 수 있게 할 수 있습니다.

```
# 심화 버전 — token_generator 내부를 수정해 사용량 이벤트 추가
# 주의: 이 코드는 라우터 스니펫입니다. load_dotenv()는 app/main.py에서 처리됩니다.
import json   # done 이벤트에 token_count 포함 시 json.dumps() 사용

async def token_generator():
    token_count = 0   # 단어 단위 근사 카운트 (실제 토큰 수와 약간 차이 있음)

    try:
        async for token in chain.astream({"message": request.message}):
            token_count += len(token.split())   # 공백 기준으로 단어 수 누적
            yield sse_event(token)
            await asyncio.sleep(0)

        # done 이벤트에 token_count 포함
        yield (
            f"event: done\n"
            f"data:{json.dumps({'content': '[DONE]', 'token_count': token_count}, ensure_ascii=False)}\n\n"
        )

    except Exception as e:
        yield sse_event(str(e), event="error")

# 클라이언트 수신 예시:
# event: done
# data: {"content": "[DONE]", "token_count": 42}
#
# 9-4 심화 미션 ①에서 클라이언트 측 파싱 코드를 작성합니다.

```

> ⚠️ `len(token.split())`은 공백 기준 단어 수이므로 실제 LLM 토큰 수(tiktoken 기준)와 차이가 있습니다. 정확한 토큰 수가 필요하면 `tiktoken` 라이브러리의 `encoding.encode(token)`으로 측정합니다.

---

---

# 📦 모듈 9-3 · 클라이언트 테스트 & 에러 처리

| 항목 내용     |                                                         |
| --------- | ------------------------------------------------------- |
| **모듈 목표** | curl과 Python httpx로 SSE 스트리밍을 소비하고, 흔한 문제 4가지를 스스로 해결한다 |
| **선수 지식** | 9-2 스트리밍 엔드포인트 구현 완료                                    |
| **난이도**   | 🔰⭐ 기본+심화                                               |

---

## 📚 강의 교안

### 핵심 개념

**서버가 완벽해도 클라이언트까지 도달하는 경로 전체가 올바른지 검증해야 합니다.**

9-2에서 스트리밍 서버를 만들었습니다. 그런데 실제로 토큰이 단위별로 도달하는지는 직접 받아봐야 압니다. 서버 코드만으로는 nginx 버퍼링, 사내 프록시, 방화벽 같은 **네트워크 레이어 문제**를 발견할 수 없습니다. 오늘 사용하는 두 도구는 각자 다른 역할을 담당합니다. **curl**은 터미널에서 “서버가 SSE를 제대로 보내는가”를 빠르게 확인하고, **Python httpx 클라이언트**는 “우리 Python 코드가 SSE를 올바르게 받는가”를 확인합니다. 둘을 함께 사용하면 문제가 서버·네트워크·클라이언트 중 어느 단계에서 발생했는지 쉽게 격리할 수 있습니다.

---

### 상세 설명

#### **9-3 | 1. curl 명령어 해부 — 옵션별 역할과 없을 때 증상**

스트리밍 테스트에 쓰는 curl 명령어는 다섯 부분으로 구성됩니다. 각 옵션의 역할을 알면 오류 발생 시 어느 부분이 문제인지 빠르게 판단할 수 있습니다.

```
curl          \  # ① HTTP 클라이언트 CLI 도구
  -N          \  # ② --no-buffer: 출력 버퍼링 해제 — 스트리밍에 필수
  -X POST     \  # ③ HTTP 메서드 지정
  <http://localhost:8000/chat/stream>   \  # ④ 요청 URL
  -H "Content-Type: application/json" \ # ⑤ 요청 헤더 — JSON 바디 전송 알림
  -d '{"message": "파이썬의 장점 5가지를 설명해줘"}'  # ⑥ 요청 바디 (JSON)

```

| 옵션 역할 빠뜨리면 발생하는 증상           |                   |                                         |
| ---------------------------- | ----------------- | --------------------------------------- |
| **`-N`**                     | curl 로컬 버퍼링 해제    | 응답 완료 후 전체가 한 번에 출력 — 스트리밍처럼 안 보임       |
| **`-X POST`**                | HTTP 메서드 POST 지정  | 기본값 GET으로 전송 → 405 Method Not Allowed   |
| **`-H "Content-Type: ..."`** | 바디가 JSON임을 서버에 알림 | 서버가 바디 파싱 실패 → 422 Unprocessable Entity |
| **`-d '...'`**               | 요청 바디(JSON) 지정    | message 필드 없음 → 422 (Pydantic 검증 실패)    |

```
# ✅ 올바른 스트리밍 테스트 — 토큰이 하나씩 흘러나옵니다
curl -N -X POST <http://localhost:8000/chat/stream> \
  -H "Content-Type: application/json" \
  -d '{"message": "파이썬의 장점 5가지를 설명해줘"}'

# 출력 예시 — 각 이벤트가 도착할 때마다 즉시 출력됩니다:
# event: message
# data: {"content": "파이"}
#
# event: done
# data: {"content": "[DONE]"}

# ❌ 가장 흔한 실수 — -N 없으면 응답이 완료될 때까지 기다렸다가 한 번에 출력
curl -X POST <http://localhost:8000/chat/stream> \ # ← -N 없음!
  -H "Content-Type: application/json" \
  -d '{"message": "파이썬의 장점 5가지를 설명해줘"}'
# 결과: 5초 후 전체 응답이 한 번에 출력 — "스트리밍이 안 된다"고 오해하기 쉬움

```

> 💡 **핵심**: curl의 `-N`은 창문을 열어 바람(토큰)이 들어오는 즉시 느끼게 해주는 옵션입니다. `-N` 없으면 curl이 버퍼에 모아 두었다가 연결이 닫힐 때 한 번에 출력하므로, “스트리밍이 동작하지 않는다”고 오해하기 쉽습니다. `-X POST`, `-H`, `-d` 세 옵션은 FastAPI의 Pydantic 검증(422)을 통과하기 위한 최소 요건입니다. 단 `-N`은 로컬 curl의 버퍼링만 해제하고, nginx 같은 중간 프록시의 버퍼링은 서버 헤더(`X-Accel-Buffering: no`)로 별도 해제해야 합니다.

---

#### **9-3 | 2. Python httpx 클라이언트 — 왜 httpx인가, 어떻게 동작하는가**

Python에는 HTTP 요청 라이브러리가 여러 개 있습니다. 스트리밍 클라이언트에 `requests` 대신 `httpx`를 쓰는 이유가 있습니다.

| `requests` `httpx`  |                |                     |
| ------------------- | -------------- | ------------------- |
| 동기(sync) 지원         | ✅              | ✅                   |
| 비동기(async) 지원       | ❌              | ✅                   |
| 스트리밍 소비             | 가능 (sync only) | ✅ (`aiter_lines()`) |
| FastAPI async와 통합   | 어색함            | 자연스럽게 통합            |

우리 서버는 `async def`로 작성되어 있고, 클라이언트도 Jupyter 노트북에서 `await`로 실행합니다. `requests`는 동기만 지원해 `async for`와 자연스럽게 연결되지 않습니다.

📓 **노트북 참조**: Step 1-① “그대로 실행”

```
# stream_client.py — 전체 코드 + 상세 주석
# 실행 방법: python stream_client.py  (uvicorn 서버 실행 후)
# 주의: 이 클라이언트는 FastAPI 서버를 호출하므로 LLM API 키가 서버 측에 있습니다
import httpx    # 비동기 HTTP 클라이언트 라이브러리 (pip install httpx)
import asyncio
import json

async def consume_stream():
    # AsyncClient: 비동기 HTTP 세션 — with 블록 종료 시 자동으로 연결 정리
    async with httpx.AsyncClient() as client:

        # client.stream(): 스트리밍 모드로 연결을 열고 유지
        # 일반 client.post()는 응답 전체를 한 번에 받지만,
        # client.stream()은 데이터가 오는 대로 처리할 수 있게 연결을 유지합니다
        async with client.stream(
            "POST",
            "<http://localhost:8000/chat/stream>",
            json={"message": "파이썬 장점 5가지를 알려줘"},
            timeout=60,    # 기본 타임아웃(5초)으로는 LLM 응답 완료 전에 끊길 수 있음
        ) as response:

            print("스트리밍 시작...")
            # response.aiter_lines(): 줄 단위로 비동기 반복
            # 새 줄(\n)이 도착할 때마다 yield — 전체를 기다리지 않음
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    # "data:" = 정확히 5글자 — line[5:]로 접두어 제거
                    data = json.loads(line[5:].strip())
                    content = data.get("content", "")
                    if content != "[DONE]":
                        print(content, end="", flush=True)
                        # end="": 줄바꿈 없이 토큰을 이어서 출력
                        # flush=True: 버퍼 없이 즉시 화면에 표시

            print("\n\n스트리밍 종료!")

asyncio.run(consume_stream())
# Jupyter에서는 await consume_stream() 으로 직접 실행 (asyncio.run 불필요)
# 예상 출력: "파이썬은 여러 가지..." 텍스트가 이어지며 출력됨

```

> 💡 **핵심**: `httpx.AsyncClient`는 서버와의 연결을 세션으로 관리하고, `client.stream()`은 그 연결에서 데이터가 오는 대로 처리합니다. `aiter_lines()`는 9-2의 `token_generator()`가 yield하는 SSE 줄들을 `async for`로 수신하는 클라이언트 쪽 대응입니다 — 서버에서 `yield sse_event(token)`, 클라이언트에서 `async for line in response.aiter_lines()`. `requests` 대신 `httpx`를 쓰는 이유는 `async for`와의 자연스러운 통합 때문입니다. 단 `timeout=60` 없이는 기본 5초 후 `httpx.ReadTimeout`이 발생합니다.

---

#### **9-3 | 3. SSE 파싱 로직 상세 —** **`line[5:]`****의 의미**

클라이언트가 SSE 스트림을 받으면 한 줄씩 처리합니다.

```
# 클라이언트가 aiter_lines()로 수신하는 줄들 (이벤트 하나 기준)
# ─────────────────────────────────────────────────────────────
event: message        ← line.startswith("event:") → 이벤트 타입 확인에 사용
                        (이 기본 클라이언트에서는 스킵 — 실습 노트북 Step 2의
                         이벤트 타입 분기에서 처리)

data: {"content": "파이"}   ← line.startswith("data:") → 실제 데이터
                              line[5:] → '{"content": "파이"}'
                              json.loads(...)["content"] → "파이"

(빈 줄)               ← 이벤트 구분자 → if 조건에 걸리지 않아 자동 스킵
# ─────────────────────────────────────────────────────────────

```

**`line[5:]`****가 정확히 5인 이유**

```
data: {"content": "파이"}
0123 4  ← 인덱스 (0-based)
d a t a :   ← "data:" = 5글자
      ↑
    line[5:] 시작 지점

```

이 파싱 패턴은 **모든 SSE 클라이언트에 공통**으로 적용됩니다.

> 💡 **핵심**: SSE 파싱은 세 줄 패턴의 역방향입니다. 서버는 `sse_event("파이")` 한 줄 호출로 `event: message\ndata: {"content": "파이"}\n\n`을 만들고, 클라이언트는 `line.startswith("data:")` → `line[5:]` → `json.loads()` 세 단계로 역분해합니다. `line[5:]`가 5인 이유는 `"data:"` 자체가 d·a·t·a·콜론 = 5글자이기 때문입니다. 단 `event:` 줄을 스킵하면 `message`/`done`/`error` 구분이 불가하므로, 팀 서비스에서 이벤트 타입별 처리가 필요하면 실습 노트북 Step 2 패턴을 적용하세요.

---

#### **9-3 | 4. 흔한 스트리밍 문제 해결 — 증상별 원인 분석**

> ⚠️ **아래 표의 1·2번이 현장 문의의 80%를 차지합니다. 순회 시 이 두 가지를 먼저 확인하세요.**

| # 증상 근본 원인 진단 방법 해결책  |                                        |                                           |                                                       |                                                      |
| --------------------- | -------------------------------------- | ----------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------- |
| **1**                 | 한 번에 전체 응답                             | 중간 프록시(nginx) 버퍼링                         | curl -N에서도 같은 증상? → nginx 문제                          | 서버 응답 헤더에 `"X-Accel-Buffering": "no"` 추가 (v3에 이미 포함) |
| **2**                 | curl에서 바로 안 보임                         | curl 로컬 버퍼링                               | `-N` 옵션 있는가?                                          | `curl -N ...` — `-N` 추가                              |
| **3**                 | 중간에 연결 끊김                              | httpx 타임아웃 초과                             | 에러: `httpx.ReadTimeout`                               | `timeout=60` 이상 (기본 5초는 LLM에 너무 짧음)                  |
| **4**                 | `<async_generator object at 0x...>` 출력 | `async for` 없이 `astream()` 결과를 변수에만 받아 출력 | `result = chain.astream(...)` 후 `print(result)` 패턴 확인 | `for` → `async for chunk in chain.astream()`         |

**증상 1 추가 설명 — nginx 버퍼링과 서버 헤더의 관계**

```
# 서버 코드 (9-2 v3에 이미 포함)에서 헤더 확인
return StreamingResponse(
    token_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",   # ← 이 헤더가 없으면 nginx 뒤에서 증상 1 발생
    },
)

```

> 💡 **핵심**: 증상 1(전체 응답 한 번에)의 진단 순서는 curl -N 테스트 → 문제 없으면 nginx 헤더, 여전히 문제면 프록시 정책 확인입니다. 증상 2(curl에서 안 보임)는 `-N` 한 글자가 원인의 80%입니다. 두 증상 모두 “스트리밍이 동작하지 않는다”고 오해하기 쉽지만, 실제로는 서버가 올바르게 토큰을 보내고 있고 **버퍼가 문제**입니다 — 로컬 curl 버퍼는 `-N`, nginx 버퍼는 `X-Accel-Buffering: no`로 각각 해제합니다. 단 기업 내부 보안 프록시는 이 헤더로도 해결되지 않을 수 있어 IT 정책 확인이 필요합니다.

---

#### **9-3 | 5. 오늘의 한계와 다음 연결**

```
오늘 확인한 것:
  터미널 curl    → 서버가 SSE를 올바르게 보내는가? ✅
  Python httpx   → Python 코드가 SSE를 올바르게 받는가? ✅

아직 없는 것:
  실제 사용자가 보는 채팅 UI

8/22(토) Streamlit 강의에서:
  st.write_stream()  ← httpx 클라이언트와 동일한 SSE를 소비
  → 토큰이 흘러오며 화면에 표시되는 채팅 UI 완성

```

> ℹ️ `st.write_stream()`은 내부적으로 오늘 작성한 `aiter_lines()` 패턴과 동일하게 동작합니다. 오늘 파싱 코드를 이해하면 8/22 Streamlit 연동이 훨씬 쉬워집니다.

---

### 💡 핵심 요약

- 클라이언트 테스트의 목적은 서버뿐 아니라 \*\*네트워크 경로 전체(서버 → 프록시 → 클라이언트 파싱)\*\*를 검증하는 것입니다
- curl의 **`N`****(–no-buffer) 옵션**은 스트리밍 테스트의 필수 옵션 — 없으면 응답이 한 번에 나와 스트리밍이 동작하지 않는다고 오해하기 쉽습니다
- SSE 파싱은 `data:` 줄을 감지 → `line[5:]`로 접두어 제거 → `json.loads()`로 파싱하는 3단계 패턴입니다 (“data:"는 정확히 5글자)
- `requests`는 동기만 지원해 `async for`와 어색하고, **`httpx`****는 비동기 스트리밍을 자연스럽게 지원**합니다
- 가장 흔한 두 가지 문제: curl `N` 옵션 누락(#2) / nginx 버퍼링(`X-Accel-Buffering: no` 누락)(#1)

---

### 🔥 더 알아보기

**`aiter_lines()`** **vs** **`aiter_bytes()`** **— 언제 무엇을 쓰는가**: `aiter_lines()`는 줄 단위로 텍스트를 반환해 SSE 파싱에 편리합니다. `aiter_bytes()`는 바이트 단위로 반환해 이미지·파일 다운로드 등 바이너리 스트리밍에 적합합니다.

**사내망(LG CNS 환경) 프록시와 SSE**: 기업 네트워크에는 보안 프록시가 있어 SSE 연결을 자동으로 끊거나 버퍼링할 수 있습니다. 증상: curl 로컬 테스트는 정상 → 사내망에서 테스트하면 한 번에 전체 응답. 해결 힌트: `X-Accel-Buffering: no` 외에 `Transfer-Encoding: chunked` 헤더가 명시적으로 설정되어 있는지 확인합니다.

---

### ⭐ 심화

> **JavaScript Fetch API로 브라우저에서 직접 소비**

브라우저에는 `EventSource`라는 SSE 전용 API가 있지만 **GET 요청만 지원**합니다. 우리 서버는 POST를 사용하므로 `fetch` API로 스트림을 직접 읽어야 합니다.

```
<!-- static_test.html — 브라우저에서 열어 테스트 -->
<!DOCTYPE html>
<html>
<head><title>SSE 스트리밍 테스트</title></head>
<body>
  <div id="output" style="font-family: monospace; white-space: pre-wrap;"></div>
  <script>
    fetch("<http://localhost:8000/chat/stream>", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: "파이썬 장점 5가지"})
    })
    .then(response => {
      const reader = response.body.getReader();   // ReadableStream 리더
      const decoder = new TextDecoder();           // 바이트 → 문자열 변환기

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) { console.log("스트리밍 완료"); return; }
          const text = decoder.decode(value);
          text.split("\n").forEach(line => {
            if (line.startsWith("data:")) {
              try {
                const data = JSON.parse(line.slice(5).trim());
                if (data.content && data.content !== "[DONE]")
                  document.getElementById("output").textContent += data.content;
              } catch (e) { /* 빈 줄 무시 */ }
            }
          });
          read();   // 재귀 호출로 다음 청크 읽기
        });
      }
      read();
    });
  </script>
</body>
</html>

```

> ⚠️ **CORS 주의**: 브라우저에서 `localhost:8000`을 직접 호출하면 CORS 오류가 발생할 수 있습니다. 오늘 실습에서는 curl/httpx로 테스트하고, 브라우저 연동은 8/22 Streamlit에서 다룹니다.

---

---

# 📦 모듈 9-4 · 가이드 실습 (개인·기본 미션)

| 항목 내용     |                                                    |
| --------- | -------------------------------------------------- |
| **모듈 목표** | `/chat/stream` 엔드포인트를 독립적으로 구현하고 curl로 토큰 흐름을 확인한다 |
| **선수 지식** | 9-2 v3 코드, 9-3 curl 테스트 방법                         |
| **난이도**   | 🔰 기본 / ⭐ 심화 병행                                    |

---

### 🏋️ 실습 자료

#### 🔰 기본 미션 — 단계별 가이드

> AI 코파일럿(Claude Code / Cursor) 사용 권장. 코드 암기가 아니라 “토큰이 흘러오는 것”을 확인하는 것이 목표입니다.

**Step 1: 임포트 추가**

`app/routers/chat.py` 파일 상단에 아래를 추가합니다.

```
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.utils.sse import sse_event   # 9-2에서 만든 유틸
import asyncio

```

**Step 2: 프롬프트 템플릿 선언**

라우터 파일 상단(엔드포인트 함수 바깥)에 추가합니다.

```
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "유용한 AI 어시스턴트입니다."),
    ("human", "{message}"),
])

```

**Step 3:** **`/stream`** **엔드포인트 추가**

9-2 v3 코드를 그대로 `chat.py` router에 붙여넣습니다.

(9-2 강의 교안의 `@router.post("/stream")` 전체 코드)

**Step 4: 서버 실행**

```
uvicorn app.main:app --reload

```

서버가 뜨면 `/docs`에서 `/chat/stream`이 보이는지 확인합니다.

**Step 5: curl로 토큰 흐름 확인**

```
# -N 필수!
curl -N -X POST <http://localhost:8000/chat/stream> \
  -H "Content-Type: application/json" \
  -d '{"message": "파이썬의 장점을 알려줘"}'

# 예상 출력: 토큰이 하나씩 흘러나오는 것을 확인
# event: message
# data: {"content": "파"}
# ...

```

---

#### ⭐ 심화 미션

기본 미션 완료 후 아래 중 1개 이상 도전하세요. 완료 시 팀 프로젝트 블록에 조기 합류 가능합니다.

**심화 ①: 종료 이벤트에 토큰 사용량 포함**

`[DONE]` 이벤트에 `token_count` 필드를 추가해 클라이언트가 사용량을 알 수 있게 하세요.

```
# 힌트: token_count 변수를 누적하고 done 이벤트에 포함
yield f"event: done\ndata:{json.dumps({'content': '[DONE]', 'token_count': token_count})}\n\n"

```

**심화 ②: 클라이언트 disconnect 감지**

클라이언트가 연결을 끊으면 generator가 계속 실행되는 문제를 해결하세요.

```
# 힌트: asyncio.CancelledError를 except로 잡아서 처리
try:
    async for token in chain.astream(...):
        yield sse_event(token)
except asyncio.CancelledError:
    print("클라이언트 연결 끊김 — generator 종료")
    return

```

---

#### 예상 결과물 & 제출 기준

| 구분 결과물 확인 방법  |                                             |          |
| ------------- | ------------------------------------------- | -------- |
| 🔰 기본         | `/chat/stream` 엔드포인트 동작, curl -N으로 토큰 흐름 확인 | 터미널 스크린샷 |
| ⭐ 심화          | 토큰 사용량 이벤트 또는 disconnect 처리 구현              | 동작 확인 영상 |

---

---

## ⚠️ 스프린트 전날 절대 규칙 재확인

> **스프린트에서 가장 많이 발생하는 서버 멈춤 원인 Top 1**

```
# ❌ 서버 전체가 멈추는 패턴 — 스프린트 중 가장 흔한 실수
@router.post("/stream")
async def chat_stream(request: ChatRequest):
    for token in chain.stream({"message": request.message}):  # ❌ 동기 stream
        yield sse_event(token)

# ✅ 반드시 이렇게
@router.post("/stream")
async def chat_stream(request: ChatRequest):
    async for token in chain.astream({"message": request.message}):  # ✅ astream
        yield sse_event(token)

```

> 오늘 팀 서비스에 `/chat/stream`을 통합할 때, 기존 코드에 동기 `invoke()` 또는 `stream()`이 섞여 있으면 반드시 `ainvoke()` / `astream()`으로 교체하세요.

---

## ✅ Day 9 최종 체크포인트

- [ ]  토큰이 단위별로 흘러오는 것을 터미널에서 확인했다
- [ ]  필수 요건 6종 점검표가 작성되었고 내일 계획이 섰다
- [ ]  팀원 전원이 데이터 흐름을 설명할 수 있다 (상호 확인 완료)