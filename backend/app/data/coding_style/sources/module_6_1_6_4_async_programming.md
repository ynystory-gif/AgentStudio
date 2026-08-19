# 비동기 프로그래밍

# 📋 오리엔테이션

---

## 핵심 메시지

### LLM은 기다리는 작업입니다. 기다리는 동안 다른 일을 합니다.

| 항목 내용       |                                                               |
| ----------- | ------------------------------------------------------------- |
| **학습 목표**   | async/await의 3가지 핵심 패턴을 익히고, gather로 동시 요청을 처리하며 팀 프로젝트를 시작한다 |
| **이 주의 척추** | async가 없으면 FastAPI(Day 7-8)와 SSE(Day 9)가 동작하지 않는다             |

---

## 모듈 구성

| # 모듈명  |                            |
| ------ | -------------------------- |
| 6-1    | 동기 vs 비동기 & 벤치마크           |
| 6-2    | async/await 핵심 패턴 3개       |
| 6-3    | asyncio.gather & Semaphore |
| 6-4    | 가이드 실습 (개인·기본 미션)          |

---

---

# 📦 모듈 6-1 · 동기 vs 비동기 & 벤치마크

이 모듈에서는 비동기의 **필요성과 원리**를 배웁니다. 숫자로 직접 체감하는 벤치마크가 이번 주 내내 `ainvoke`를 고수하는 동기 부여가 됩니다.

| 항목 내용     |                                                                    |
| --------- | ------------------------------------------------------------------ |
| **모듈 목표** | 동기·비동기 처리 방식의 차이를 벤치마크 숫자로 이해하고, LLM 서비스에 비동기가 필요한 이유를 설명할 수 있다    |
| **선수 지식** | 파이썬 함수 정의, `ChatOpenAI.invoke()` 사용 경험 (Day 1 완료), `load_dotenv()` |
| **난이도**   | 🔰⭐ 기본+심화                                                          |

---

### 📚 강의 교안

## 6-1 | 왜 비동기가 필요한가?

### LLM 호출의 현실

```
LLM 응답 시간: 평균 1~3초 (긴 응답은 5~10초)

동기 방식으로 5건 처리:
  요청 1 대기 (2초) → 요청 2 대기 (2초) → ... → 총 10초

비동기 방식으로 5건 처리:
  5개 동시 시작 → 가장 느린 것 기다림 → 총 2~3초

5배 차이!

```

---

## 6-1 | 1. 비동기 프로그래밍이란?

### 핵심 개념

비동기 프로그래밍은 **"기다리는 동안 다른 일을 한다"** 는 철학입니다. 일반적인(동기) 프로그래밍은 한 작업이 완전히 끝나야 다음 작업을 시작하지만, 비동기 프로그래밍은 완료를 기다리는 동안 다른 작업을 처리할 수 있습니다. LLM API 호출처럼 응답이 오기까지 1\~15초가 걸리는 작업에서 비동기의 효과가 극적으로 나타납니다.

### 상세 설명

**왜 LLM 서비스에서 비동기가 필수인가**

일반 REST API(날씨 조회, DB 검색)는 수십\~수백 ms면 응답이 옵니다. 그러나 LLM은 응답 *생성 자체* 에 시간이 걸립니다.

| 작업 유형 평균 응답 시간 비동기 효과  |           |          |
| ---------------------- | --------- | -------- |
| 일반 REST API            | 50\~200ms | 미미함      |
| DB 쿼리                  | 10\~100ms | 미미함      |
| LLM 짧은 응답              | 1\~2초     | **매우 큼** |
| LLM 긴 응답 (보고서·코드)      | 5\~15초    | **극적**   |

10개의 LLM 요청을 동기로 처리하면 평균 2초 × 10 = **20초**, 비동기로 처리하면 가장 느린 요청 하나를 기다리는 **2\~3초**에 완료됩니다.

**이벤트 루프(Event Loop): 비동기의 핵심 엔진**

파이썬 비동기의 중심에는 **이벤트 루프**가 있습니다. "현재 실행 가능한 작업이 뭐가 있나?"를 계속 확인하면서, `await`를 만나 기다리는 코루틴은 잠시 멈추고 준비된 다른 코루틴을 실행하는 스케줄러입니다.

```
이벤트 루프의 동작 원리:

  ┌──────────────────────────────────────────────────────┐
  │  이벤트 루프                                          │
  │                                                      │
  │  1. 코루틴 A 실행 ──→ await 만남 (LLM 대기 중)         │
  │  2. "A는 잠깐 멈춤" ──→ 코루틴 B 실행 시작              │
  │  3. 코루틴 B 실행 ──→ await 만남 (LLM 대기 중)         │
  │  4. "B도 잠깐 멈춤" ──→ 코루틴 C 실행 시작             │
  │  5. A의 LLM 응답 도착 ──→ A 재개, 마저 실행            │
  │  6. B의 LLM 응답 도착 ──→ B 재개, 마저 실행            │
  └──────────────────────────────────────────────────────┘

```

> 💡 **핵심** : 비동기는 "마법"이 아닙니다. CPU가 여러 연산을 동시에 하는 것이 아니라, "이 작업은 외부 응답을 기다리는 중이니 그동안 다른 작업을 처리한다"는 스케줄링 전략입니다. `await`는 이벤트 루프에 "나 지금 기다리는 중이니 다른 것 먼저 해도 돼"라는 신호입니다.

**파이썬 비동기의 간략한 역사**

파이썬은 2015년(Python 3.5)에 `async`/`await` 키워드를 정식 도입했습니다. 이전에는 콜백 함수, `concurrent.futures`, `Twisted` 등 방법이 혼재해 코드가 복잡했지만, `async`/`await` 도입으로 작성 방식이 통일됐습니다. FastAPI, LangChain의 `ainvoke`·`astream`은 이 문법을 직접 활용합니다.

### 💡 핵심 요약

LLM 서비스의 병목 95%는 "API 응답 대기"입니다. 이 대기 시간을 겹쳐서 활용하는 것이 비동기의 핵심이며, FastAPI 엔드포인트와 SSE 스트리밍은 모두 이 원리 위에서 동작합니다. `async`/`await`는 이번 주의 기본 문법입니다.

### 🔥 더 알아보기

파이썬의 비동기는 **협력적 멀티태스킹(Cooperative Multitasking)** 방식입니다. 각 코루틴이 자발적으로 `await`를 통해 제어권을 이벤트 루프에 넘겨야 합니다. `await` 없이 긴 계산을 수행하면 다른 코루틴이 실행될 수 없어 이벤트 루프 전체가 멈춥니다. 이것이 `async def` 안에서 `time.sleep(1)` 대신 반드시 `await asyncio.sleep(1)`을 써야 하는 이유이며, 이번 주 내내 반복 점검되는 절대 규칙입니다.

---

## 6-1 | 2. 동기 vs 비동기: 처리 흐름 비교

### 핵심 개념

같은 5개의 LLM 요청을 처리할 때, **동기 방식**은 요청을 하나씩 완료하고 나서 다음을 시작합니다. **비동기 방식**은 기다리는 동안 다음 요청을 이미 시작합니다. 이 차이가 처리 시간을 3\~5배 단축시킵니다.

### 상세 설명

**처리 흐름 시각화**

```
────────────────────────────────────────────────────────────────
 동기 방식: 앞 요청이 완료돼야 다음 시작
────────────────────────────────────────────────────────────────
 [시작]
 요청 1: ████████ (2초) → 완료
 요청 2:          ████████ (2초) → 완료
 요청 3:                   ████████ (2초) → 완료
 요청 4: ...
 총 소요: 건수 × 평균 응답 시간  (5건이면 약 10초)

────────────────────────────────────────────────────────────────
 비동기 방식: 기다리는 시간을 겹쳐서 활용
────────────────────────────────────────────────────────────────
 [시작]
 요청 1: ████████ (2초) → 완료
 요청 2: ████████ (2초) → 완료  ← 요청 1과 거의 동시에 시작
 요청 3: ████████ (2초) → 완료
 요청 4: ████████ (2초) → 완료
 요청 5: ████████ (2초) → 완료

 총 소요: 가장 느린 단일 요청의 시간  (5건이라도 약 2~3초)
────────────────────────────────────────────────────────────────

```

**파이썬 코드 수준에서의 차이**

| 구분 동기 코드 비동기 코드  |                   |                          |
| ---------------- | ----------------- | ------------------------ |
| 함수 선언            | `def f():`        | `async def f():`         |
| LLM 호출           | `llm.invoke(...)` | `await llm.ainvoke(...)` |
| 여러 건 동시          | 불가 (for문 순차 실행)   | `asyncio.gather(...)`    |
| 스크립트 진입점         | 함수 직접 호출          | `asyncio.run(...)`       |

> ⚠️ **이번 주 절대 규칙:** **`async def`** **안에서 동기 함수 호출 금지**
>
> ```
> # ❌ 절대 금지 — 이벤트 루프 전체가 멈춤!
> async def bad_handler():
>     result = llm.invoke("...")    # 동기 invoke → 이 요청 처리 중 다른 모든 요청 대기
>     time.sleep(1)                 # 동기 sleep → 이벤트 루프 완전 정지
>     return result.content
>
> # ✅ 올바른 방법
> async def good_handler():
>     result = await llm.ainvoke("...")   # 비동기 ainvoke
>     await asyncio.sleep(1)             # 비동기 sleep
>     return result.content
>
> ```
>
> 이 규칙은 FastAPI 순회 클리닉, 루브릭 구조·설계(25점) 점검 항목입니다

> 💡 **핵심**: 동기는 은행 창구에 줄 서기입니다 — 앞 사람이 완전히 끝나야 내 차례가 옵니다. 비동기는 진동벨 번호표입니다 — `await`를 만나는 순간 번호표를 받고 자리를 비켜주고, 응답이 도착하면 이벤트 루프가 다시 깨웁니다. `async def` 안에서 `invoke()`를 쓰는 것은 번호표 시스템에서 혼자 창구 앞에 서는 것과 같아, 그 요청이 처리되는 동안 다른 모든 고객이 대기합니다.

### 💡 핵심 요약

- `async def`: "이 함수는 비동기로 기다릴 수 있습니다" 선언
- `await`: "여기서 기다리되, 다른 코루틴이 실행될 수 있게" 신호
- `await`를 빠뜨리면 **코루틴 객체**만 만들어지고 실제 실행이 안 됩니다 — 셀 출력에 `<coroutine object ...>`가 뜨면 `await` 누락이 원인입니다

### 🔥 더 알아보기

FastAPI가 비동기를 기본으로 채택한 이유가 바로 여기에 있습니다. 웹 서버에 수백 개의 요청이 동시에 들어올 때, 각 요청이 LLM 응답을 기다리는 동안 이벤트 루프가 다른 요청을 처리합니다. 동기 Flask 기반 서버와 비교하면 LLM 서비스 기준 처리량(Throughput)이 5\~20배 차이날 수 있습니다. uvicorn이 FastAPI의 공식 서버인 이유도 Cython 기반 이벤트 루프(uvloop)로 최적화됐기 때문입니다.

---

## 6-1 | 3. I/O Bound vs CPU Bound — 비동기가 효과적인 작업

### 핵심 개념

비동기가 **모든** 상황에서 빠른 것은 아닙니다. 병목이 "기다림(I/O)"에 있을 때는 효과가 크지만, 병목이 "계산(CPU)"에 있을 때는 비동기가 도움이 되지 않습니다. LLM API 호출은 전형적인 **I/O Bound** 작업이므로 비동기(asyncio)가 최적의 선택입니다.

### 상세 설명

| 구분 I/O Bound CPU Bound  |                                 |                              |
| ----------------------- | ------------------------------- | ---------------------------- |
| **병목 원인**               | 외부 응답 대기 (네트워크·디스크·DB)          | CPU 연산 자체                    |
| **대표 사례**               | **LLM API 호출**, REST API, 파일 읽기 | 이미지 처리, 암호화, ML 모델 추론        |
| **async 효과**            | ✅ 매우 큼 — 대기 시간을 겹쳐 활용           | ❌ 없음 — CPU는 이미 100% 사용 중     |
| **해결 도구**               | `asyncio` (이번 주)                | `multiprocessing`, GPU 병렬 처리 |

**비유로 이해하기**

배달 앱으로 음식을 주문하는 상황(I/O Bound)을 생각해보세요. 배달원이 음식을 가져오는 동안 내가 청소나 독서를 해도 됩니다. 주문 5개를 동시에 넣으면 배달원 5명이 동시에 출발합니다. 나는 기다리기만 하면 됩니다. → **asyncio 효과 극적**

반면 직접 라면을 끓이는 상황(CPU Bound)에서는 내가 냄비를 저어야 합니다. 다른 일을 동시에 하면 라면이 타거나 더 느려집니다. → **asyncio 효과 없음**

> 💡 **핵심 통찰**: 우리가 만드는 LLM 서비스는 "사용자 입력 → OpenAI 서버에서 토큰 생성 대기 → 응답 수신" 흐름입니다. 파이썬 코드가 OpenAI 서버의 응답을 기다리는 이 구간이 전형적인 I/O Bound입니다. asyncio는 이 대기 시간 동안 다른 사용자의 요청을 처리합니다.

**asyncio vs multiprocessing: 어떤 경우에 무엇을?**

```
asyncio (I/O Bound에 적합):
  프로세스 1개 → 이벤트 루프 1개 → 여러 코루틴이 번갈아 실행
  메모리 효율 높음 | 오버헤드 낮음 | GIL 영향 없음

multiprocessing (CPU Bound에 적합):
  프로세스 N개 → 각 프로세스가 독립 CPU 코어 사용
  진짜 병렬 실행 | GIL 우회 가능 | 메모리 N배 사용

```

### 💡 핵심 요약

**"LLM 호출 = I/O Bound = asyncio"** 이 공식을 기억하세요. 이미지 전처리나 수치 계산이 병목이라면 multiprocessing을 고려해야 하지만, 이 과정에서 만드는 LLM API 서비스는 asyncio로 충분합니다.

### 🔥 더 알아보기

Python 3.12부터 실험적 `no-GIL` 모드가 도입됐습니다. 기존 파이썬은 GIL(Global Interpreter Lock) 때문에 한 번에 하나의 스레드만 파이썬 코드를 실행할 수 있어 멀티스레딩이 CPU Bound에서 비효율적이었습니다. no-GIL 모드가 안정화되면 asyncio와 multiprocessing의 경계가 흐려질 수 있지만, 2025년 현재 실무에서는 여전히 **I/O Bound → asyncio, CPU Bound → multiprocessing** 구분이 표준입니다.

---

## 6-1 | 4. 벤치마크: 숫자로 체감하기

### 핵심 개념

개념을 이해했다면 직접 측정해볼 차례입니다. 동일한 5개의 LLM 요청을 동기·비동기로 각각 처리해 소요 시간을 비교합니다. 이 숫자가 이번 주 내내 `ainvoke`와 `async def`를 고수하는 동기 부여가 됩니다.

### 상세 설명

**코드 구조 이해**

벤치마크 코드는 두 개의 함수로 구성됩니다.

- `sequential()`: 일반 함수(`def`), 동기 호출(`invoke`), for문으로 순차 처리
- `concurrent()`: 비동기 함수(`async def`), 비동기 호출(`ainvoke`), `gather`로 동시 처리

두 함수를 순서대로 실행해 소요 시간을 비교하면 비동기의 효과를 숫자로 확인할 수 있습니다.

### 코드 예시 — 동기 vs 비동기 벤치마크

> 📓 **노트북 참조**: — Step 1 "그대로 실행" + Step 2 "건수를 10개로 바꿔 관찰"

```
# async_benchmark.py — 로컬 .venv 환경에서 실행 (python async_benchmark.py)
import asyncio, time
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# .env 파일에서 OPENAI_API_KEY 환경변수 로드
# 이 호출 없으면 ChatOpenAI 생성 시 AuthenticationError 발생
load_dotenv()

# LLM 객체 생성
# temperature=0: 매번 동일한 짧은 답변 유도 → 벤치마크 결과의 일관성 확보
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 과정 관련 질문 5개 (명확한 질문 → LLM이 짧고 일관된 답 반환)
QUESTIONS = [
    "파이썬 async/await의 장점을 한 문장으로.",
    "LangChain이란 무엇인지 한 문장으로.",
    "FastAPI의 특징을 한 문장으로.",
    "비동기 프로그래밍이 필요한 이유를 한 문장으로.",
    "Pydantic의 역할을 한 문장으로.",
]

# ─── ① 동기 방식 ──────────────────────────────────────────────────────────
def sequential():
    """5개 질문을 하나씩 순서대로 처리하는 동기 함수"""
    start = time.time()
    for q in QUESTIONS:
        # invoke(): 이 줄에서 LLM 응답이 올 때까지 완전히 멈춤
        # 응답이 와야 다음 반복(다음 질문)으로 넘어갈 수 있음
        llm.invoke(q)
    elapsed = time.time() - start
    print(f"순차: {elapsed:.2f}초")
    return elapsed

# ─── ② 비동기 방식 ────────────────────────────────────────────────────────
async def concurrent():
    """5개 질문을 동시에 시작해 가장 늦는 응답까지 기다리는 비동기 함수"""
    start = time.time()
    await asyncio.gather(
        # 리스트 컴프리헨션으로 5개의 코루틴(ainvoke 호출) 생성
        # * 연산자로 리스트를 펼쳐 gather에 전달 (gather는 *args 형식을 받음)
        # ainvoke(): invoke()의 비동기 버전 — await 지점에서 이벤트 루프에 제어권 반환
        *[llm.ainvoke(q) for q in QUESTIONS]
        # asyncio.gather: 전달받은 코루틴들을 "동시에 시작"하고
        #                 "모두 완료될 때까지" 기다린 후 결과를 리스트로 반환
    )
    elapsed = time.time() - start
    print(f"동시: {elapsed:.2f}초")
    return elapsed

# ─── ③ 실행 ───────────────────────────────────────────────────────────────
seq_time  = sequential()

# asyncio.run(): .py 스크립트의 최상위에서 async 함수를 실행하는 표준 진입점
# 내부에서 새 이벤트 루프 생성 → concurrent() 실행 → 완료 후 루프 종료
# FastAPI 서버 안의 async def 엔드포인트에서는 이 호출 불필요 (FastAPI가 루프 관리)
conc_time = asyncio.run(concurrent())

print(f"\n속도 향상: {seq_time / conc_time:.1f}배")

# 예상 출력:
# 순차:  10.83초
# 동시:   2.41초
#
# 속도 향상: 4.5배

```

> ⚠️ **Jupyter Notebook에서 실행 시**: Jupyter는 이미 이벤트 루프가 실행 중이므로 `asyncio.run()`을 호출하면 `RuntimeError: This event loop is already running`이 발생합니다. 노트북 셀에서는 `asyncio.run(concurrent())`를 **`await concurrent()`** 로 교체하세요. `.py` 스크립트에서는 `asyncio.run()`이 맞습니다.

**실습 결과 기록 표**

아래 표를 완성해보세요.

| 방식 건수 소요 시간 LangSmith 트레이스  |   |           |                |
| --------------------------- | - | --------- | -------------- |
| 순차                          | 5 | \_\_\_\_초 | 5개 (순차 생성됨)    |
| 동시                          | 5 | \_\_\_\_초 | 5개 (거의 동시 생성됨) |
| 속도 향상                       | — | \_\_\_\_배 | —              |

### 💡 핵심 요약

숫자로 확인하셨나요? 보통 3\~5배 차이가 납니다. 이것이 이번 주 내내 `ainvoke`, `astream`, `async def`를 고수하는 이유입니다. FastAPI 서버에서 동기 `invoke`를 단 한 군데만 써도, 그 요청이 처리되는 동안 다른 모든 사용자의 요청이 대기합니다.

### 🔥 더 알아보기

LangChain의 핵심 컴포넌트는 모두 `a` 접두사가 붙은 비동기 버전을 제공합니다. 패턴만 기억하면 처음 보는 메서드도 비동기 버전이 있다는 것을 바로 알 수 있습니다.

| 동기 메서드 비동기 메서드 사용 상황       |                             |                |
| -------------------------- | --------------------------- | -------------- |
| `invoke()`                 | `ainvoke()`                 | 단건 LLM 호출      |
| `batch()`                  | `abatch()`                  | 리스트 일괄 처리      |
| `stream()`                 | `astream()`                 | 토큰 단위 스트리밍     |
| `get_relevant_documents()` | `aget_relevant_documents()` | RAG 문서 검색 (9월) |

이 패턴을 기억하면 Day 9 SSE 스트리밍에서 `chain.astream()`을 처음 봐도 자연스럽게 이해됩니다.

---

## 🏋️ 실습 자료

### 🔰 기본 실습 — 벤치마크 실행 확인

위 `async_benchmark.py`를 그대로 실행해 순차·동시 실행 시간 차이를 확인합니다.
 LangSmith에 5개의 트레이스가 생성되었는지도 확인하세요.

### ⭐ 심화 실습 — 두 모델 병렬 벤치마크

```
# two_model_benchmark.py
# 심화 실습 사전 준비:
# 1. pip install langchain-anthropic
# 2. .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 추가
# (Anthropic Console: <https://console.anthropic.com> 에서 발급)
import asyncio, time
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()
openai_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
# ANTHROPIC_API_KEY가 .env에 있어야 함
anthropic_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

QUESTION = "파이썬과 자바스크립트의 차이를 2문장으로 설명해."

async def compare_models():
    start = time.time()
    openai_result, anthropic_result = await asyncio.gather(
        openai_llm.ainvoke(QUESTION),    # 두 모델 동시 호출
        anthropic_llm.ainvoke(QUESTION),
    )
    print(f"총 소요:{time.time()-start:.2f}초 (두 모델 동시 호출)")
    print(f"\n[GPT-4o-mini]\n{openai_result.content}")
    print(f"\n[Claude Haiku]\n{anthropic_result.content}")
    # 출력 예시:
    # 총 소요: 1.87초 (두 모델 동시 호출)
    # [GPT-4o-mini] 파이썬은 ...
    # [Claude Haiku] 파이썬은 ...

asyncio.run(compare_models())

```

---

---

# 📦 모듈 6-2 · async/await 핵심 패턴 3개

| 항목 내용     |                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------- |
| **모듈 목표** | `async def` / `await` / `asyncio.gather` 3가지 패턴을 직접 작성하고, `async def` 안에서 동기 함수를 호출하면 안 되는 이유를 설명할 수 있다 |
| **선수 지식** | 6-1 완료 (동기·비동기 차이 이해), 파이썬 함수 정의, `llm.invoke()` 사용 경험                                                  |
| **난이도**   | 🔰⭐ 기본+심화                                                                                               |

---

### 📚 강의 교안

## 6-2 | 왜 배우는가

6-1에서 비동기가 빠르다는 것을 숫자로 확인했습니다. 그렇다면 “어떻게 코드로 표현하는가”가 다음 질문입니다. 파이썬에서 비동기를 표현하는 방법은 딱 3가지 패턴으로 완결됩니다. 이 패턴을 모르면 FastAPI 엔드포인트를 작성할 수 없고,  SSE 스트리밍도 불가능합니다. 오늘 3가지를 손으로 한 번씩 쓰면, 나머지는 AI 코파일럿이 대신 써줍니다.

---

## 6-2 | 1. async def와 await — 비동기 함수의 선언과 실행

### 핵심 개념

비동기 코드는 딱 두 개의 키워드로 시작됩니다. `async def`는 "이 함수는 기다릴 수 있습니다"라는 **선언**이고, `await`는 "여기서 기다리되, 다른 코루틴이 실행될 수 있게"라는 **신호**입니다. 이 두 키워드가 이번 주 모든 비동기 코드의 뼈대를 이룹니다.

### 상세 설명

### **`async def`****: 코루틴 함수 선언**

`async def`로 선언된 함수를 **코루틴 함수(coroutine function)** 라고 합니다. 일반 함수와 생긴 것은 비슷하지만, 호출했을 때 동작이 완전히 다릅니다.

| 구분 일반 함수 (`def`) 코루틴 함수 (`async def`)  |                |                                       |
| -------------------------------------- | -------------- | ------------------------------------- |
| 호출 결과                                  | 즉시 실행되고 결과 반환  | **코루틴 객체** 생성 (아직 실행 안 됨)             |
| 실행 방법                                  | 함수 이름()        | **`await`** 함수이름() 또는 `asyncio.run()` |
| 내부에서 사용                                | 일반 코드          | `await` 가능                            |
| LLM 호출                                 | `llm.invoke()` | `await llm.ainvoke()`                 |

> 💡 **핵심** : `async def`로 정의된 함수를 호출하면 **"실행 예약서(코루틴 객체)"** 가 만들어집니다. 실제 요리가 아니라 레시피 카드를 받는 것입니다. `await`를 붙여야 비로소 요리가 시작됩니다. 이 점이 처음 비동기를 배울 때 가장 헷갈리는 부분입니다.

#### 코드 예시 — 패턴 1: async def 선언

> 📓 **노트북 참조**: — Step 2 "sync vs async 함수 나란히 실행"

```
# pattern1_async_def.py — 독립 실행 가능
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import asyncio

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ─── ❌ 일반 함수 (동기) ─────────────────────────────────────────────
def get_summary_sync(text: str) -> str:
    """동기 함수: LLM 응답이 올 때까지 이 함수 전체가 멈춤"""
    result = llm.invoke(f"한 문장으로 요약: {text}")   # 완료될 때까지 블로킹
    return result.content

# ─── ✅ 코루틴 함수 (비동기) ─────────────────────────────────────────
async def get_summary_async(text: str) -> str:
    """코루틴 함수: await 지점에서 이벤트 루프에 제어권을 잠시 넘김"""
    # ainvoke(): invoke()의 비동기 버전
    # await: "여기서 LLM 응답 기다리는 동안 다른 코루틴 실행해도 됨" 신호
    result = await llm.ainvoke(f"한 문장으로 요약: {text}")
    return result.content
    # 예상 반환값: "이 텍스트는 ..." (LLM이 생성한 요약)

# ─── 실행 비교 ──────────────────────────────────────────────────────
# 동기 함수: 그냥 호출
sync_result = get_summary_sync("파이썬은 배우기 쉬운 프로그래밍 언어입니다.")
print(f"동기 결과: {sync_result}")

# 비동기 함수: asyncio.run()으로 감싸서 실행
# asyncio.run(): 이벤트 루프를 생성하고 코루틴 함수를 실행하는 진입점
async_result = asyncio.run(get_summary_async("파이썬은 배우기 쉬운 프로그래밍 언어입니다."))
print(f"비동기 결과: {async_result}")

# 두 결과는 동일함 — 차이는 "기다리는 방식"

```

### **`await`****: 코루틴을 실제로 실행하는 신호**

`await`는 두 가지 역할을 동시에 합니다. 첫째, 코루틴을 실제로 실행합니다. 둘째, 완료될 때까지 기다리되 이벤트 루프가 다른 코루틴을 실행할 수 있게 합니다.

#### 코드 예시 — 패턴 2: await 유무 차이

> 📓 **노트북 참조**: — Step 3 "await 지우고 출력 타입 비교"

```
# pattern2_await.py — await 유무의 차이를 직접 확인
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import asyncio

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

async def demonstrate_await():

    # ─── ❌ await 없음: 코루틴 객체만 생성, 실행 안 됨 ─────────────────
    result_bad = llm.ainvoke("랭체인이 뭐야?")   # await 빠짐!
    print(type(result_bad))     # <class 'coroutine'>
    print(result_bad)
    # 출력: <coroutine object ChatOpenAI.ainvoke at 0x10f3a2...>
    # ⚠️ RuntimeWarning: coroutine '...' was never awaited 경고도 발생!
    # 이것은 실제 LLM 호출이 아닌, "나중에 실행될 예약서"만 만든 것

    # 코루틴이 실행되지 않았으므로 가비지 컬렉션 전에 닫아야 함
    result_bad.close()   # RuntimeWarning 방지

    # ─── ✅ await 있음: 실제 실행, 결과 반환 ────────────────────────────
    result_good = await llm.ainvoke("랭체인이 뭐야?")   # await!
    print(type(result_good))    # <class 'langchain_core.messages.ai.AIMessage'>
    print(result_good.content)
    # 출력 예시: "LangChain은 LLM 기반 애플리케이션을 만들기 위한 프레임워크입니다."

asyncio.run(demonstrate_await())

```

> ⚠️ **가장 흔한 실수 — await 누락**
>
> 셀 출력에 `<coroutine object ...>`가 나타나면 `await`를 빠뜨린 것입니다.
>  이것은 **레시피 카드를 들고만 있는 것**이지 요리를 한 것이 아닙니다.
>
> ```
> # ❌ 잘못된 코드 — 자주 하는 실수
> result = llm.ainvoke("질문")       # coroutine 객체만 생성
> print(result.content)              # AttributeError: 'coroutine' object has no attribute 'content'
>
> # ✅ 올바른 코드
> result = await llm.ainvoke("질문") # 실제 실행 후 AIMessage 반환
> print(result.content)              # "답변 내용"
>
> ```

### 💡 핵심 요약

- `async def f()`: "이 함수는 코루틴입니다" 선언. 호출하면 **코루틴 객체(예약서)** 가 생성됩니다.
- `await f()`: 코루틴을 실제로 실행하고 결과를 받습니다. `async def` 함수 **안에서만** 사용할 수 있습니다.
- `<coroutine object ...>` 출력 = `await` 누락. 바로 `await`를 붙이세요.
- `asyncio.run(f())`: `.py` 스크립트에서 코루틴 함수를 실행하는 시작점. 이벤트 루프를 새로 만들고 종료합니다.

### 🔥 더 알아보기

`async def` 함수를 일반 함수처럼 호출하면 코루틴 객체가 반환되지만, 실제로 실행하려면 `await`가 필요합니다. 이 **지연 실행(lazy evaluation)** 특성 덕분에 코루틴을 변수에 저장했다가 나중에 `gather`에 넘기는 것이 가능합니다. `[get_summary_async(t) for t in texts]` 처럼 리스트 컴프리헨션으로 코루틴을 "준비"해뒀다가 `asyncio.gather(*코루틴_리스트)`로 한 번에 동시 실행하는 패턴이 Day 9 SSE와 팀 프로젝트에서 반복 등장합니다.

---

## 6-2 | 2. asyncio.gather — 동시 실행과 흔한 실수 모음

### 핵심 개념

`asyncio.gather`는 **여러 코루틴을 동시에 시작**하고 **모두 완료될 때까지 기다린 후** 결과를 리스트로 반환합니다. 결과의 순서는 입력 순서와 동일하게 보장됩니다. 5개 요청의 응답이 뒤죽박죽으로 도착해도 gather가 순서를 맞춰 줍니다.

### 상세 설명

**gather의 동작 원리**

```
asyncio.gather(코루틴A, 코루틴B, 코루틴C) 호출 시:

  1. A, B, C 동시에 시작 (이벤트 루프에 등록)
  2. 이벤트 루프가 세 코루틴을 번갈아 실행
     - A가 await를 만나면 → B 실행
     - B가 await를 만나면 → C 실행
     - C가 await를 만나면 → A 재개 (응답이 도착한 것부터)
  3. A, B, C 모두 완료되면 → [A결과, B결과, C결과] 리스트 반환
     (도착 순서와 무관하게 입력 순서로 정렬)

```

### 코드 예시 — 패턴 3: asyncio.gather

> 📓 **노트북 참조**: — Step 4 "gather로 5개 동시 처리"

```
# pattern3_gather.py — 독립 실행 가능
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import asyncio, time

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 코루틴 함수 정의 — 섹션 5에서 배운 패턴 1 활용
async def get_summary(text: str, label: str) -> str:
    result = await llm.ainvoke(f"한 문장으로 요약: {text}")
    print(f"  [{label}] 완료")   # 완료 순서 확인 (도착 순서가 입력과 다를 수 있음)
    return result.content

async def process_all(texts: list) -> list:
    start = time.time()

    # ─── ❌ for문 순차 처리 (gather 없이) ──────────────────────────────
    # results_sequential = []
    # for i, text in enumerate(texts):
    #     result = await get_summary(text, f"순차-{i}")
    #     results_sequential.append(result)
    # → 위처럼 하면 하나씩 순서대로 → 비동기의 이점 없음!

    # ─── ✅ gather로 동시 처리 ──────────────────────────────────────────
    results = await asyncio.gather(
        # 리스트 컴프리헨션으로 코루틴 객체 5개 생성
        *[get_summary(text, f"동시-{i}") for i, text in enumerate(texts)]
        # * 연산자: 리스트를 펼쳐 gather의 인수로 전달
        # gather는 코루틴들을 동시에 이벤트 루프에 등록
    )
    # results: 입력 순서대로 정렬된 결과 리스트 (도착 순서 무관)
    # 예: [텍스트0 요약, 텍스트1 요약, 텍스트2 요약, ...]

    elapsed = time.time() - start
    print(f"\n총 소요: {elapsed:.2f}초 | 결과 수: {len(results)}개")
    return results

texts = [
    "파이썬은 배우기 쉬운 범용 언어입니다.",
    "LangChain은 LLM 앱 개발 프레임워크입니다.",
    "FastAPI는 빠른 API 서버 프레임워크입니다.",
    "Pydantic은 데이터 검증 라이브러리입니다.",
    "asyncio는 비동기 프로그래밍 라이브러리입니다.",
]

results = asyncio.run(process_all(texts))

print("\n─── 결과 ───")
for i, r in enumerate(results):
    print(f"[{i}] {r[:40]}...")
# 예상 출력:
#   [동시-2] 완료
#   [동시-0] 완료   ← 도착 순서는 랜덤
#   [동시-4] 완료
#   [동시-1] 완료
#   [동시-3] 완료
#
# 총 소요: 2.31초 | 결과 수: 5개
#
# ─── 결과 ───
# [0] 파이썬은 문법이 간결하고 ...   ← 결과는 입력 순서대로!
# [1] LangChain은 LLM 기반 ...
# [2] FastAPI는 Python으로 ...
# [3] Pydantic은 타입 힌트를 ...
# [4] asyncio는 비동기 I/O를 ...

```

**return\_exceptions 옵션 — 일부 실패해도 나머지 결과 받기**

```
results = await asyncio.gather(
    *[get_summary(text, f"{i}") for i, text in enumerate(texts)],
    return_exceptions=True   # 기본값: False (하나라도 오류면 전체 예외 발생)
    # True로 설정하면: 오류 발생 항목은 Exception 객체로 채워지고 나머지 결과 반환
)

for i, r in enumerate(results):
    if isinstance(r, Exception):
        print(f"[{i}] 오류: {r}")   # 실패한 항목만 처리
    else:
        print(f"[{i}] 성공: {r[:30]}")

```

**흔한 실수 모음 — 이것만 피하면 async 코드가 동작합니다**

비동기 코드에서 발생하는 오류의 90%는 아래 4가지 실수에서 비롯됩니다.

**실수 ①: await 누락 → 코루틴 객체 출력** (➡️ 섹션 5에서 코드로 상세 확인)

```
# ❌ await 없음
async def bad():
    result = llm.ainvoke("질문")   # 코루틴 객체만 생성
    print(result)                  # <coroutine object ...>
    print(result.content)          # AttributeError!

# ✅ await 있음
async def good():
    result = await llm.ainvoke("질문")
    print(result.content)          # "답변 텍스트"

```

**실수 ②:** **`async def`** **안에서 동기 함수 사용 → 이벤트 루프 정지**

```
# ❌ async 함수 안에서 동기 함수 호출
async def bad_handler():
    result = llm.invoke("...")     # 동기 invoke → 이 동안 전체 서버 멈춤
    time.sleep(2)                  # 동기 sleep → 이벤트 루프 완전 정지

# ✅ 비동기 버전 사용
async def good_handler():
    result = await llm.ainvoke("...")   # 비동기 ainvoke
    await asyncio.sleep(2)             # 비동기 sleep

```

> ⚠️ 이 실수는 개발 중에는 발견하기 어렵습니다. 혼자 테스트할 때는 정상 동작하지만, 실제 서비스에서 요청이 몰릴 때 서버 응답이 느려지는 원인이 됩니다. FastAPI 엔드포인트의 `async def` 안에서 동기 `invoke()`를 쓰면 그 요청을 처리하는 동안 다른 모든 사용자의 요청이 대기합니다.

**실수 ③:** **`asyncio.run()`** **중첩 → ValueError**

```
# ❌ async 함수 안에서 asyncio.run() 호출
async def outer():
    # asyncio.run()은 새 이벤트 루프를 만들려 하지만
    # 이미 실행 중인 루프 안에서는 불가능
    result = asyncio.run(inner())
    # ValueError: cannot be called from a running event loop

# ✅ await로 대체
async def outer():
    result = await inner()   # 같은 이벤트 루프 안에서 실행

```

**실수 ④: Jupyter에서** **`asyncio.run()`** **사용 → RuntimeError**

```
# ❌ Jupyter 셀에서
asyncio.run(my_async_func())
# RuntimeError: This event loop is already running
# (Jupyter는 이미 자체 이벤트 루프를 실행 중)

# ✅ Jupyter 셀에서 (top-level await)
await my_async_func()
# Jupyter는 셀 안에서 await를 직접 지원함 (IPython 7.0+)

# ✅ .py 스크립트에서 (이것은 OK)
asyncio.run(my_async_func())
# 스크립트 최상위는 이벤트 루프가 없으므로 run()으로 새로 생성

```

> 💡 **핵심**: gather는 심부름 여러 건을 가족에게 동시에 맡기는 것입니다 — 각자 다른 시간에 돌아와도 결과는 맡긴 순서 그대로 정렬됩니다. `await`를 빠뜨리면 쪽지만 건네고 실제로 심부름을 보내지 않은 상태(`<coroutine object>`), `async def` 안에서 동기 `invoke()`를 쓰면 가족 한 명이 직접 돌아올 때까지 나머지가 전혀 출발하지 못하는 상태입니다. Jupyter에서 `asyncio.run()`을 쓰는 것은 이미 번호표 시스템이 돌아가는 식당에서 전원을 다시 켜려는 것과 같아 충돌합니다.

### 💡 핵심 요약

- `asyncio.gather(*코루틴_리스트)`: 여러 코루틴을 동시에 시작하고 모두 완료될 때까지 기다림. **결과 순서는 입력 순서와 동일**
- `return_exceptions=True`: 일부 실패해도 나머지 결과를 받을 수 있음. 배치 처리에 필수
- **흔한 실수 4가지**: ① await 누락 ② async 안에서 동기 함수 ③ asyncio.run() 중첩 ④ Jupyter에서 asyncio.run()
- 셀 출력에 `<coroutine object>`가 나오면 `await`, `RuntimeError: event loop`가 나오면 Jupyter에서 `await`로 교체

### 🔥 더 알아보기

`asyncio.create_task()`는 `gather`와 비슷하지만 **즉시 이벤트 루프에 등록**해 백그라운드에서 실행을 시작한다는 점이 다릅니다. `gather`는 `await gather(A, B, C)` 한 줄에서 A, B, C를 동시에 시작하지만, `create_task`는 태스크를 만든 직후부터 이미 실행이 시작됩니다. 그 사이에 다른 코드를 끼워 넣을 수 있습니다. 대부분의 LLM 배치 처리 상황에서는 `gather`로 충분하며, `create_task`는 "태스크를 만들어두고 나중에 결과를 확인"하는 고급 패턴에 활용됩니다.

---

### 🏋️ 실습 자료

#### 🔰 기본 실습 — 패턴 3개 직접 작성

각 패턴 파일을 순서대로 작성하고 실행해보세요.

**Step 1**: `패턴1_async_def.py` 작성 — sync와 async 함수를 나란히 작성
 **Step 2**: `패턴2_await.py` 작성 — await 유무 차이를 직접 출력으로 확인
 **Step 3**: `패턴3_gather.py` 작성 — texts 3개를 gather로 동시 처리, 결과 리스트 확인

#### ⭐ 심화 실습 — asyncio.create\_task() 패턴

```
# 심화_create_task.py
# gather와 create_task의 차이: create_task는 "즉시 시작 예약"
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

async def summarize(text: str, label: str) -> str:
    result = await llm.ainvoke(f"한 문장으로 요약:{text}")
    print(f"[{label}] 완료")   # 완료 순서가 입력 순서와 다를 수 있음
    return result.content

async def main():
    texts = ["긴 텍스트 A...", "텍스트 B...", "텍스트 C..."]

    # gather 방식 — 모든 결과가 준비될 때까지 기다렸다가 일괄 반환
    results_gather = await asyncio.gather(*[summarize(t, f"gather-{i}") for i, t in enumerate(texts)])

    # create_task 방식 — 즉시 시작, 원하는 시점에 await
    tasks = [asyncio.create_task(summarize(t, f"task-{i}")) for i, t in enumerate(texts)]
    # 다른 작업을 여기에 넣을 수 있음
    results_task = await asyncio.gather(*tasks)

    print(f"gather 결과:{len(results_gather)}개")
    print(f"task 결과:{len(results_task)}개")

asyncio.run(main())

```

---

## 6-2 | 압축 설명

### 딱 3가지 패턴만 기억하세요

| # 패턴 문법 의미  |           |                       |                        |
| ----------- | --------- | --------------------- | ---------------------- |
| 1           | 비동기 함수 선언 | `async def f():`      | “이 함수는 기다릴 수 있습니다”     |
| 2           | 기다리기      | `await 비동기함수()`       | “기다리되, 다른 것도 실행 가능하게”  |
| 3           | 동시 시작     | `asyncio.gather(...)` | “모두 동시에 시작해서 다 끝나면 결과” |

---

# 📦 모듈 6-3 · asyncio.gather & Semaphore

이 모듈에서는 gather를 대량 처리에 적용할 때의 **Rate Limit 문제와 해결책**을 배웁니다. Semaphore와 지수 백오프를 조합하면 프로덕션 수준의 배치 처리 함수를 완성할 수 있습니다.

| 항목 내용     |                                                                       |
| --------- | --------------------------------------------------------------------- |
| **모듈 목표** | `asyncio.gather`로 동시 요청을 처리하고, `Semaphore`로 Rate Limit(429)을 방지할 수 있다 |
| **선수 지식** | 6-2 완료 (`async def` / `await` 이해), `asyncio.run()` 사용 경험              |
| **난이도**   | 🔰⭐ 기본+심화                                                             |

---

### 📚 강의 교안

## 6-3 | 1. asyncio.gather 심화 — Rate Limit과 대량 처리의 현실

### 핵심 개념

`asyncio.gather`로 5\~10개 요청을 동시에 보내는 것은 문제없습니다. 그러나 20\~100개를 한 번에 보내면 OpenAI가 **429 Too Many Requests** 오류를 반환하기 시작합니다. 이것이 API의 **Rate Limit**입니다. 이 섹션에서는 대량 처리 시 gather 단독 사용의 한계를 이해하고, 다음 섹션의 Semaphore가 왜 필요한지 이해니다.

### 상세 설명

**Rate Limit이란?**

OpenAI를 포함한 모든 LLM API 제공사는 서비스 안정성을 위해 요청 속도를 제한합니다.

| 제한 종류 의미 초과 시                 |               |           |
| ----------------------------- | ------------- | --------- |
| **RPM** (Requests Per Minute) | 분당 요청 횟수 제한   | 429 오류 반환 |
| **TPM** (Tokens Per Minute)   | 분당 처리 토큰 수 제한 | 429 오류 반환 |
| **TPD** (Tokens Per Day)      | 일일 총 토큰 제한    | 429 오류 반환 |

> gpt-4o-mini Tier 1 기준으로 RPM은 약 500, TPM은 약 200,000입니다. (플랜별 정확한 한도는 OpenAI 공식 문서에서 확인하세요.) 100개 요청을 0.1초 안에 동시에 쏘면 단 한 번의 burst로 RPM 한도를 초과할 수 있습니다.

> 💡 **핵심**: gather는 편의점·약국·세탁소 심부름을 가족 3명에게 동시에 맡기는 것입니다. 혼자 순서대로 돌면 30분이지만 동시에 보내면 가장 오래 걸리는 15분에 끝납니다. 그러나 심부름꾼 100명을 한꺼번에 보내면 편의점이 감당 못하듯, 요청 100개를 한 번에 쏘면 OpenAI도 429로 거부합니다. 가족이 다른 순서로 돌아와도 gather는 항상 입력 순서대로 `results[0]`, `[1]`...에 정렬합니다.

**gather 단독 사용의 한계 — 숫자로 확인**

> 💡 **비유 : gather는 "엑셀에서 여러 셀을 한 번에 자동 채우기"입니다**
>
> 셀 하나씩 순서대로 수식을 넣는 대신, 전체 범위를 선택해 한 번에 적용하듯 `gather(*[함수(x) for x in 목록])`은 목록 전체에 함수를 한 번에 적용합니다. 리스트 컴프리헨션으로 코루틴을 "준비"해두고 `*`로 펼쳐 넘기는 패턴과 같습니다.
>
> **이 비유의 한계**: 엑셀 계산은 CPU에서 즉각 처리되지만, `gather`는 I/O 대기가 있는 비동기 작업에서만 의미 있는 속도 향상을 제공합니다. CPU Bound 작업(이미지 처리·암호화)에는 효과가 없습니다.

아래 코드에서 \*\*`[*get_summary(text, i) for i, text in enumerate(texts)]`\*\*이 바로 이 패턴입니다.

```
# gather_limit_demo.py — Rate Limit 문제 재현 (실제 실행 시 주의)
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

async def get_summary(text: str, idx: int) -> str:
    result = await llm.ainvoke(f"한 문장으로 요약: {text}")
    return result.content

async def process_bulk(texts: list) -> list:
    """gather로 대량 요청을 한 번에 전송"""
    results = await asyncio.gather(
        *[get_summary(text, i) for i, text in enumerate(texts)],
        return_exceptions=True   # 일부 실패해도 나머지 결과 받기
    )

    # 결과 분석
    successes = [r for r in results if not isinstance(r, Exception)]
    failures  = [r for r in results if isinstance(r, Exception)]
    print(f"성공: {len(successes)}개 / 실패: {len(failures)}개")

    # 실패 원인 확인
    for failure in failures[:3]:   # 처음 3개만 출력
        print(f"  오류: {type(failure).__name__}: {str(failure)[:80]}")
    return results

# ❌ 100개를 한 번에 → Rate Limit 위험
# texts_100 = [f"텍스트 {i}입니다." for i in range(100)]
# asyncio.run(process_bulk(texts_100))
# 예상 결과:
#   성공: 47개 / 실패: 53개
#   오류: RateLimitError: Error code: 429 - Rate limit reached...

# ✅ 10개는 보통 안전
texts_10 = [f"텍스트 {i}입니다." for i in range(10)]
asyncio.run(process_bulk(texts_10))
# 예상 결과:
#   성공: 10개 / 실패: 0개

```

> ⚠️ **Rate Limit 오류가 위험한 이유**: `return_exceptions=True` 없이 gather를 쓰다가 429가 발생하면 **전체 gather가 취소**됩니다. 처리 완료된 결과도 모두 버려집니다. 대량 배치 처리에서 `return_exceptions=True`는 기본값으로 설정해야 합니다.

**부분적 해결책: 청크(Chunk) 단위 처리**

100개를 한 번에 보내는 대신, 10개씩 나눠서 청크 사이에 잠시 대기하는 방법입니다.

```
# chunk_processing.py — 청크 단위 처리
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

async def get_summary(text: str) -> str:
    result = await llm.ainvoke(f"한 문장으로 요약: {text}")
    return result.content

async def process_in_chunks(texts: list, chunk_size: int = 10) -> list:
    """텍스트를 chunk_size개씩 나눠 처리, 청크 사이 1초 대기"""
    all_results = []

    for i in range(0, len(texts), chunk_size):
        chunk = texts[i : i + chunk_size]    # 현재 청크 (최대 chunk_size개)
        print(f"청크 {i//chunk_size + 1} 처리 중... ({len(chunk)}개)")

        chunk_results = await asyncio.gather(
            *[get_summary(text) for text in chunk],
            return_exceptions=True
        )
        all_results.extend(chunk_results)    # 전체 결과에 추가

        # 마지막 청크가 아니면 1초 대기 (Rate Limit 방지)
        if i + chunk_size < len(texts):
            print("  1초 대기 중...")
            await asyncio.sleep(1)           # ← 반드시 await! time.sleep 금지

    print(f"\n전체 완료: {len(all_results)}개")
    return all_results

texts = [f"텍스트 {i}입니다." for i in range(25)]
results = asyncio.run(process_in_chunks(texts, chunk_size=10))
# 예상 출력:
#   청크 1 처리 중... (10개)
#   1초 대기 중...
#   청크 2 처리 중... (10개)
#   1초 대기 중...
#   청크 3 처리 중... (5개)
#
#   전체 완료: 25개

```

**청크 처리의 한계**

청크 방식은 구현이 간단하지만 두 가지 문제가 있습니다. 첫째, 청크 사이 1초 대기가 고정값이라 낭비입니다. 실제로 요청이 얼마나 빠르게 처리됐는지와 무관합니다. 둘째, 각 청크 안에서 요청이 동시에 쏟아지므로 청크 크기를 잘못 설정하면 여전히 429가 발생합니다. 이 문제를 근본적으로 해결하는 것이 `Semaphore`입니다.

### 💡 핵심 요약

- gather 단독으로 10개 이하: 보통 안전
- 20개 이상을 한 번에: Rate Limit(429) 위험
- `return_exceptions=True`: 대량 처리 시 반드시 사용, 실패한 항목을 Exception 객체로 수집
- 청크 처리: 간단하지만 고정 대기와 정밀도 문제 → 다음 섹션의 Semaphore가 근본 해결책

### 🔥 더 알아보기

LangChain의 `llm.abatch()` 메서드는 내부적으로 청크 처리와 Rate Limit 대응 로직을 포함합니다. `llm.abatch(texts, config={"max_concurrency": 5})`처럼 `max_concurrency`를 지정하면 동시 처리 수를 제한할 수 있어 Semaphore를 직접 구현하지 않아도 됩니다. 그러나 Semaphore를 직접 이해하면 체인 전체 흐름에서 더 세밀한 제어가 가능하고, FastAPI 엔드포인트에서 동시 요청 수를 제한하는 용도로도 응용할 수 있습니다.

---

## 6-3 | 2. asyncio.Semaphore — 동시 요청 수를 정밀하게 제어하기

### 핵심 개념

`asyncio.Semaphore`는 **동시에 실행 가능한 코루틴의 수를 제한**하는 동기화 도구입니다. `Semaphore(5)`는 "지금 이 시점에 최대 5개의 코루틴만 실행되게 허용"합니다. 6번째 코루틴은 앞의 것 중 하나가 완료될 때까지 자동으로 대기합니다. Semaphore를 gather와 함께 쓰면 Rate Limit 없이 100개, 1000개도 안전하게 처리할 수 있습니다.

### 상세 설명

**`async with semaphore`****: 슬롯 획득과 반납의 자동화**

Semaphore는 `async with` 구문과 함께 사용합니다. `async with`는 일반 `with`의 비동기 버전으로, 블록에 진입할 때 슬롯을 획득하고 블록이 끝나면 슬롯을 자동으로 반납합니다. 수동으로 `acquire()`/`release()`를 호출하지 않아도 됩니다.

```
async with semaphore:        ← 슬롯 획득 (없으면 기다림)
    await llm.ainvoke(...)   ← LLM 호출
                             ← 블록 종료 → 슬롯 자동 반납

```

> 💡 **핵심**: Semaphore(5)는 다리 통행 제한 표지판과 같습니다. 차(코루틴)가 10대 와도 5대만 다리를 건너고 나머지는 입구에서 기다립니다. `async with semaphore:` 블록에 들어가는 순간 통행권이 줄어들고, 블록을 빠져나가는 순간 자동으로 반납됩니다 — `acquire()`/`release()`를 직접 호출하지 않아도 됩니다. 단 대기 순서는 OS 스케줄러에 따라 달라질 수 있어, 특정 코루틴이 먼저 실행된다고 보장되지 않습니다.

### 코드 예시 — Semaphore + gather 기본 패턴

> 📓 **노트북 참조**: — Step 5 "Semaphore 적용 후 LangSmith에서 동시 실행 패턴 확인"

```
# semaphore_basic.py — 독립 실행 가능
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ─── Semaphore 생성 ──────────────────────────────────────────────────────────
# 동시 요청 최대 5개로 제한 (gpt-4o-mini Tier 1 권장값)
# 이 객체를 모든 코루틴이 공유 → 전역 또는 함수 인수로 전달
semaphore = asyncio.Semaphore(5)

async def safe_llm_call(text: str, idx: int) -> str:
    """Semaphore로 보호된 LLM 호출 함수"""
    async with semaphore:
        # ← 이 시점에 슬롯 획득 (현재 5개 이미 실행 중이면 여기서 대기)
        print(f"  [{idx:02d}] 시작")
        try:
            result = await llm.ainvoke(f"한 문장으로 요약: {text}")
            print(f"  [{idx:02d}] 완료")
            return result.content
        except Exception as e:
            print(f"  [{idx:02d}] 오류: {type(e).__name__}")
            return f"오류: {e}"
        # ← async with 블록 종료 → 슬롯 자동 반납, 대기 중인 코루틴 진입 가능

async def process_safely(texts: list) -> list:
    """gather + Semaphore 조합 — 20개도 안전하게"""
    print(f"총 {len(texts)}개 처리 시작 (동시 최대 5개)")

    results = await asyncio.gather(
        # 20개 코루틴 모두 생성 → 동시에 대기열에 등록
        # 하지만 Semaphore가 5개씩만 실행 허용
        *[safe_llm_call(text, i) for i, text in enumerate(texts)],
        return_exceptions=True
    )

    successes = sum(1 for r in results if not isinstance(r, Exception))
    print(f"\n처리 완료: 성공 {successes}개 / 전체 {len(results)}개")
    return results

# 20개 처리 — Semaphore 없이는 Rate Limit 위험, 있으면 안전
texts = [f"파이썬 주요 라이브러리 {i}번에 대해 설명하면" for i in range(20)]
results = asyncio.run(process_safely(texts))

# 예상 출력:
#   총 20개 처리 시작 (동시 최대 5개)
#   [00] 시작
#   [01] 시작
#   [02] 시작
#   [03] 시작
#   [04] 시작       ← 여기까지만 동시 실행, 나머지 15개는 대기
#   [02] 완료
#   [05] 시작       ← 슬롯 하나 반납 → 다음 코루틴 진입
#   [00] 완료
#   [06] 시작
#   ...
#
#   처리 완료: 성공 20개 / 전체 20개

```

### 코드 예시 — Semaphore + 지수 백오프 재시도

Rate Limit 오류가 발생했을 때 단순히 포기하는 대신, 잠시 기다렸다가 재시도하는 전략이 **지수 백오프(Exponential Backoff)** 입니다. 1초 기다렸다 재시도, 그래도 실패하면 2초, 그래도 실패하면 4초 — 대기 시간이 2배씩 늘어납니다.

```
# semaphore_with_retry.py — 독립 실행 가능
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

semaphore = asyncio.Semaphore(5)

async def safe_call_with_retry(text: str, idx: int, max_retries: int = 3) -> str:
    """Semaphore + 지수 백오프 재시도 패턴"""
    async with semaphore:
        for attempt in range(max_retries):
            try:
                result = await llm.ainvoke(f"한 문장으로 요약: {text}")
                return result.content   # 성공하면 바로 반환

            except Exception as e:
                # 마지막 시도였다면 포기
                if attempt == max_retries - 1:
                    print(f"  [{idx:02d}] 최종 실패 ({max_retries}회 시도)")
                    return f"실패: {e}"

                # 재시도 대기 시간: 2^attempt 초 (1초 → 2초 → 4초)
                wait_time = 2 ** attempt
                print(f"  [{idx:02d}] {type(e).__name__} → {wait_time}초 후 재시도 "
                      f"({attempt + 1}/{max_retries})")

                # ✅ 반드시 await asyncio.sleep! time.sleep은 이벤트 루프 정지
                await asyncio.sleep(wait_time)

async def robust_batch(texts: list) -> list:
    """재시도 포함 안전 배치 처리 — 프로덕션 수준"""
    results = await asyncio.gather(
        *[safe_call_with_retry(text, i) for i, text in enumerate(texts)],
        return_exceptions=True
    )

    successes = sum(1 for r in results if not isinstance(r, Exception) and not str(r).startswith("실패"))
    print(f"\n배치 완료: 성공 {successes}개 / 전체 {len(results)}개")
    return results

texts = [f"텍스트 {i}입니다." for i in range(30)]
results = asyncio.run(robust_batch(texts))

# 예상 출력 (오류 없을 때):
#   배치 완료: 성공 30개 / 전체 30개
#
# 예상 출력 (429 일시 발생 시):
#   [07] RateLimitError → 1초 후 재시도 (1/3)
#   [07] RateLimitError → 2초 후 재시도 (2/3)
#   배치 완료: 성공 30개 / 전체 30개  ← 재시도로 결국 성공

```

**Semaphore 값 선택 기준**

| gpt-4o-mini 플랜 RPM 한도 권장 Semaphore 값  |          |                 |
| ------------------------------------- | -------- | --------------- |
| Tier 1 (최초 API 사용)                    | 약 500    | `Semaphore(3)`  |
| Tier 2 (누적 $50+ 사용)                   | 약 5,000  | `Semaphore(10)` |
| Tier 3+ (누적 $100+ 사용)                 | 약 10,000 | `Semaphore(20)` |

> ℹ️ **실습 환경 권장값**: `Semaphore(3~5)`. 수업 중 24명이 동시에 실습하면 API 리소스를 공유하므로 보수적으로 설정하는 것이 좋습니다.

### 💡 핵심 요약

- `asyncio.Semaphore(N)`: 동시 실행 코루틴을 최대 N개로 제한
- `async with semaphore:`: 슬롯을 획득하고 블록이 끝나면 자동 반납 — `acquire()`/`release()` 수동 호출 불필요
- **Semaphore + gather 조합**: 대량 처리의 표준 패턴. gather는 "모두 동시에", Semaphore는 "단 N개만 동시에"를 담당
- **지수 백오프**: 재시도 대기 시간을 2배씩 늘림(1→2→4초). `await asyncio.sleep()`만 사용 — `time.sleep()`은 이벤트 루프를 멈춤
- 실습 환경 권장: `Semaphore(5)` + `max_retries=3`

### 🔥 더 알아보기

`tenacity` 라이브러리는 재시도 로직을 데코레이터로 깔끔하게 처리합니다. `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))`처럼 선언적으로 쓸 수 있어 직접 구현한 지수 백오프보다 코드가 훨씬 간결해집니다. LangChain 자체도 내부적으로 `tenacity`를 사용해 API 호출을 자동 재시도합니다. 프로젝트 규모가 커지면 직접 구현보다 `tenacity`를 도입하는 것이 유지보수에 유리합니다.

---

## 🏋️ 실습 자료

### 🔰 기본 실습 — Semaphore 적용 확인

```
# 기본_semaphore.py
# 위 semaphore_example.py를 실행하고 LangSmith 트레이스에서
# 요청 5개가 동시 실행되고 나머지가 대기하는 패턴을 확인합니다.

```

**확인 항목**:

- LangSmith에서 트레이스가 “묶음”으로 생성되는 것을 확인 (Semaphore 5개 한도)
- 20개 처리 완료 출력 확인

### ⭐ 심화 실습 — Semaphore + 지수 백오프 재시도

```
# 심화_semaphore_backoff.py
import asyncio
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

semaphore = asyncio.Semaphore(3)  # 심화: 더 엄격한 제한으로 테스트

async def safe_call_with_retry(text: str, max_retries: int = 3) -> str:
    """지수 백오프(1초→2초→4초) 재시도 포함 안전 호출"""
    async with semaphore:
        for attempt in range(max_retries):
            try:
                result = await llm.ainvoke(f"요약:{text}")
                return result.content
            except Exception as e:
                if attempt == max_retries - 1:
                    return f"최종 실패:{e}"
                wait_time = 2 ** attempt   # 1초, 2초, 4초 — 지수 증가
                print(f"[재시도{attempt + 1}/{max_retries}]{wait_time}초 대기...")
                await asyncio.sleep(wait_time)  # ← asyncio.sleep! time.sleep 절대 금지

async def robust_batch(texts: list) -> list:
    return await asyncio.gather(
        *[safe_call_with_retry(t) for t in texts],
        return_exceptions=True
    )

texts = [f"텍스트{i}" for i in range(10)]
results = asyncio.run(robust_batch(texts))
print(f"성공:{sum(1 for r in results if '실패' not in str(r))}개 / 전체:{len(results)}개")

```

---

---

# 📦 모듈 6-4 · 가이드 실습 (개인·기본 미션)

| 항목 내용     |                                                                                             |
| --------- | ------------------------------------------------------------------------------------------- |
| **모듈 목표** | 순차·동시 처리 코드를 직접 실행해 속도 차이를 측정한 결과표를 제출하고, ⭐ 조기 완료자는 Semaphore+지수 백오프를 구현해 팀 블록에 조기 합류할 수 있다 |
| **선수 지식** | 6-1\~6-3 완료 (async 3패턴, Semaphore 코드 이해)                                                    |
| **난이도**   | 🔰 기본 (⭐ 심화 포함)                                                                             |

---

## 가이드 실습 — 직접 측정하고 팀 프로젝트에 적용하기

### 핵심 개념

오늘 배운 세 가지 패턴(`async def` / `await` / `asyncio.gather`)과 Semaphore를 직접 코드로 작성하고 실행합니다. 숫자로 확인한 벤치마크를 제출하는 것이 기본 미션이며, 조기 완료 시 팀 프로젝트 블록에 일찍 합류할 수 있습니다.

### 6-4 | 기본 미션 (🔰 전원 공통 · 개인 단위)

> 📓 **노트북 참조**: — Step 1\~4

**목표**: 동기 5건 vs 비동기 5건의 소요 시간을 직접 측정합니다.

**Step 1** — `day6_실습.ipynb`을 열고 셀 2(환경 점검)를 실행해 `환경 준비 완료`를 확인합니다.

**Step 2** — 아래 두 함수를 노트북에서 실행합니다.

```
# — Step 2 (그대로 실행)
import asyncio, time
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

QUESTIONS = [
    "파이썬 async/await의 장점을 한 문장으로.",
    "LangChain이란 무엇인지 한 문장으로.",
    "FastAPI의 특징을 한 문장으로.",
    "비동기 프로그래밍이 필요한 이유를 한 문장으로.",
    "Pydantic의 역할을 한 문장으로.",
]

def sequential():
    start = time.time()
    for q in QUESTIONS:
        llm.invoke(q)
    return time.time() - start

async def concurrent():
    start = time.time()
    await asyncio.gather(*[llm.ainvoke(q) for q in QUESTIONS])
    return time.time() - start

# ← Jupyter에서는 await 직접 사용 (asyncio.run() 아님)
seq_time  = sequential()
conc_time = await concurrent()

print(f"순차:{seq_time:.2f}초")
print(f"동시:{conc_time:.2f}초")
print(f"속도 향상:{seq_time / conc_time:.1f}배")

```

**Step 3** — LangSmith 대시보드에서 두 실행의 트레이스가 각각 5개씩 생성됐는지 확인합니다. 동시 실행의 트레이스는 시작 시각이 거의 같습니다.

| 방식 건수 소요 시간 LangSmith 트레이스  |   |           |    |
| --------------------------- | - | --------- | -- |
| 순차                          | 5 | \_\_\_\_초 | 링크 |
| 동시                          | 5 | \_\_\_\_초 | 링크 |
| 속도 향상                       | — | \_\_\_\_배 | —  |

---

### 6-4 | 심화 미션 (⭐ 조기 완료 시)

> 📓 **노트북 참조**: — Step 5\~6

**미션 A — Semaphore 적용 확인**

아래 `safe_llm_call` 함수를 완성하고, 20개 요청을 처리하면서 동시에 최대 5개만 실행되는 것을 출력으로 확인합니다.

```
# — Step 5 (TODO 채우기)
semaphore = asyncio.Semaphore(5)

async def safe_llm_call(text: str, idx: int) -> str:
    async with semaphore:
        #TODO(⭐): 아래 ___를 채우세요
        #   힌트: 섹션 8 "기본 패턴" 코드 구조와 동일
        result = await llm.ainvoke(___)
        print(f"  [{idx:02d}] 완료")
        return result.content

texts = [f"텍스트{i}입니다." for i in range(20)]
results = await asyncio.gather(
    *[safe_llm_call(text, i) for i, text in enumerate(texts)],
    return_exceptions=True
)
print(f"\n처리 완료:{len(results)}개")

```

**미션 B — 지수 백오프 직접 구현**

`safe_call_with_retry` 함수를 처음부터 작성합니다.

- `async with semaphore` 안에서 최대 3회 재시도
- 실패 시 대기: 1초 → 2초 → 4초 (2의 거듭제곱)
- 모든 재시도 실패 시 `"실패: {오류 내용}"` 반환
- `await asyncio.sleep()` 사용 (`time.sleep()` 금지)

---

### 트러블슈팅 — 실습 중 자주 마주치는 오류

| 오류 메시지 원인 해결 방법                                                 |                               |                                                    |
| --------------------------------------------------------------- | ----------------------------- | -------------------------------------------------- |
| `RuntimeError: This event loop is already running`              | Jupyter에서 `asyncio.run()` 사용  | `await concurrent()` 로 교체                          |
| `<coroutine object ... at 0x...>` 출력                            | `await` 누락                    | 호출 앞에 `await` 추가                                   |
| `AuthenticationError`                                           | `.env` 미로드 또는 키 오류            | `load_dotenv()` 호출 확인, `.env` 파일 존재 여부 확인          |
| `RateLimitError: 429`                                           | 동시 요청 과다                      | `Semaphore(3)` 으로 낮추거나 `await asyncio.sleep(1)` 추가 |
| `AttributeError: 'coroutine' object has no attribute 'content'` | `await` 누락 후 `.content` 접근 시도 | `result = await llm.ainvoke(...)` 로 수정             |

### 🏋️ 실습 자료

## 6-4 | 🔰 기본 미션 (오늘 제출)

### 순차 vs 동시 벤치마크

```
# benchmark_submission.py — 이것이 오늘의 기본 미션
import asyncio, time
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ❌ 수정 전: QUESTIONS = [f"나라 {i}번의 수도는? 한 단어로." for i in range(1, 6)]
# → "나라 1번의 수도"는 의미불명, LLM이 임의 답변 → 수강생 혼란 가능
# ✅ 수정 후: 과정 관련 질문으로 교체
# <!-- 수정: QUESTIONS 의미불명 문제 해소 -->
QUESTIONS = [
    "파이썬 async/await의 장점을 한 문장으로.",
    "LangChain이란 무엇인지 한 문장으로.",
    "FastAPI의 특징을 한 문장으로.",
    "비동기 프로그래밍이 필요한 이유를 한 문장으로.",
    "Pydantic의 역할을 한 문장으로.",
]

def sequential():
    """동기 순차 처리"""
    start = time.time()
    for q in QUESTIONS:
        llm.invoke(q)
    return time.time() - start

async def concurrent():
    """비동기 동시 처리"""
    start = time.time()
    await asyncio.gather(*[llm.ainvoke(q) for q in QUESTIONS])
    return time.time() - start

seq  = sequential()
# asyncio.run() — 스크립트 실행 시 비동기 함수 진입점
# ⚠️ Jupyter에서 실행 시 RuntimeError 발생 → 대신 `await concurrent()` 사용
conc = asyncio.run(concurrent())

# 결과 표 출력
print(f"| 방식  | 건수 | 소요 시간 |")
print(f"|------|------|---------|")
print(f"| 순차  |  5   |{seq:.2f}초  |")
print(f"| 동시  |  5   |{conc:.2f}초  |")
print(f"| 속도 향상:{seq/conc:.1f}배 |")
# 예상 출력:
# | 방식  | 건수 | 소요 시간 |
# |------|------|---------|
# | 순차  |  5   | 10.23초  |
# | 동시  |  5   |  2.41초  |
# | 속도 향상: 4.2배 |

```

**제출**: 위 표를 슬랙 `#day6-제출`에 스크린샷으로 제출

---

## 6-4 | ⭐ 심화 미션 — Semaphore + 지수 백오프

기본 미션 조기 완료자는 6-3 심화 실습(`심화_semaphore_backoff.py`)을 작성하고 완료 후 팀 블록에 조기 합류하세요.

**목표**: `safe_call_with_retry`를 사용해 10건 배치 처리, 재시도 로그 확인

**팀 블록 조기 합류 기준**: 결과 `성공: 10개 / 전체: 10개` 출력 스크린샷을 슬랙에 공유 후 팀 합류

---

## 6-4 | ⭐⭐ 마이 서비스 조각 연계 (팀 블록 연결)

> ℹ️ **기본 미션·심화 미션 모두 완료 후**: 내 마이 서비스 조각(1주차 개인 실습)의 LLM 호출을 확인하세요.
>
> “내 서비스 조각에 비동기를 적용하면”:
>
> 1. `llm.invoke()` → `await llm.ainvoke()`로 교체
> 2. 호출 함수 앞에 `async def` 추가
> 3. 여러 건 처리가 있다면 `asyncio.gather()`로 묶기
>
> 이렇게 전환한 코드가 **오늘 오후 팀 블록에서 팀 리포로 이관할 채택 코드의 기반**이 됩니다.
>  이미 ainvoke 버전으로 전환된 파일을 들고 팀 블록에 합류하면 팀 이관 속도가 빨라집니다.

---

---

## 📝 Day 6 종합 정리

> 오늘의 핵심 메시지 세 가지

**1. LLM 서비스의 병목은 "기다림"이고, 비동기는 그 기다림을 겹치는 전략입니다**

LLM 호출은 전형적인 I/O Bound 작업입니다. 동기 방식으로 5개를 처리하면 10초, 비동기로 처리하면 2초입니다. 이 3\~5배 차이가 Day 7 FastAPI, Day 9 SSE 스트리밍에서 `async def`와 `ainvoke`를 고집하는 이유입니다.

**2. async/await/gather — 세 패턴이면 대부분의 비동기 LLM 서비스를 만들 수 있습니다**

| 패턴 역할 언제                |                |                |
| ----------------------- | -------------- | -------------- |
| `async def f():`        | 코루틴 함수 선언      | 모든 비동기 함수      |
| `await 코루틴()`           | 코루틴 실행 + 결과 대기 | LLM 호출, I/O 작업 |
| `asyncio.gather(*코루틴들)` | 여러 코루틴 동시 시작   | 배치·병렬 처리       |

**3. Semaphore는 "안전망"입니다 — 대량 처리에서 Rate Limit을 방지합니다**

`asyncio.gather`는 강력하지만 무제한으로 사용하면 API 429 오류가 발생합니다. `Semaphore(5)`는 동시 실행 수를 제한해 Rate Limit 없이 100개, 1000개도 안전하게 처리하게 합니다. 지수 백오프와 조합하면 일시적 오류도 자동으로 복구됩니다.

---

## ✅ Day 6 최종 체크포인트

- [ ]  벤치마크 숫자(순차 vs 동시 소요 시간)를 직접 측정해 제출했다
- [ ]  `<coroutine object ...>`가 출력됐을 때 `await` 누락임을 안다
- [ ]  `async def` 안에서 `invoke()` 대신 `ainvoke()`를 써야 하는 이유를 설명할 수 있다
- [ ]  Jupyter에서 `asyncio.run()` 대신 `await`를 직접 쓰는 이유를 안다