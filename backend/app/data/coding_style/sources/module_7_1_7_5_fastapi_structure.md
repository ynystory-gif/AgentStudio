# FastAPI 구조

# 📋 오리엔테이션

---

## 핵심 메시지

### 서비스 골격을 세웁니다

| 항목 내용     |                                                                   |
| --------- | ----------------------------------------------------------------- |
| **학습 목표** | FastAPI 표준 프로젝트 구조를 이해하고, 라우터·서비스·스키마를 분리해 `/health` 엔드포인트를 동작시킨다 |
| **핵심 연결** | 이 레이아웃이 9월 RAG → 10월 MCP → 최종 프로젝트까지 그대로 확장됩니다                    |

---

## 모듈 구성

| # 모듈명  |                         |
| ------ | ----------------------- |
| 7-1    | HTTP 기초 압축 & FastAPI 소개 |
| 7-2    | FastAPI 표준 프로젝트 구조      |
| 7-3    | 경로·쿼리·바디 파라미터           |
| 7-4    | devcontainer 개요         |
| 7-5    | 가이드 실습 (개인)             |

---

---

# 📦 모듈 7-1 · HTTP 기초 & FastAPI 소개

| 항목 내용     |                                                         |
| --------- | ------------------------------------------------------- |
| **모듈 목표** | HTTP 핵심 메서드·상태코드를 설명하고, FastAPI로 최소 서버를 30초 안에 실행할 수 있다 |
| **선수 지식** | Day 6 async/await 기초, 파이썬 함수·데코레이터 개념                   |
| **난이도**   | 🔰⭐ 기본+심화                                               |

---

### 📚 강의 교안

#### 왜 배우는가

FastAPI로 LLM 서비스를 만들기 전에, 클라이언트와 서버가 “어떤 언어로 대화하는지” 알아야 합니다. 그 언어가 HTTP입니다. HTTP를 모르면 에러 코드가 왜 뜨는지, 요청이 왜 실패하는지 알 수 없습니다. 오늘 30분만 투자하면 5개월 내내 에러 메시지를 해석할 수 있게 됩니다.

---

## 7-1 | 1. HTTP — 웹 통신의 표준 언어

### 핵심 개념

HTTP(HyperText Transfer Protocol)는 클라이언트(브라우저, 앱, httpx)와 서버(FastAPI)가 데이터를 주고받을 때 지켜야 하는 **세계 표준 규약**입니다. "어떤 형식으로 요청하고, 어떤 형식으로 응답하느냐"를 정해놓은 약속입니다.

우리가 FastAPI로 만드는 LLM 서비스도, 목요일 구현할 SSE 스트리밍도, 팀 프로젝트의 모든 API도 이 HTTP 위에서 동작합니다. **HTTP를 이해하면 이후 에러 메시지 90%를 혼자 해석할 수 있게 됩니다.**

### 상세 설명

**클라이언트 — 서버 구조**

HTTP는 반드시 **클라이언트가 먼저 요청(Request)** 을 보내고, **서버가 응답(Response)** 을 돌려주는 구조입니다. 서버가 먼저 데이터를 보내는 것은 기본 HTTP에서 불가능합니다. (SSE는 연결을 유지한 채 서버가 지속적으로 데이터를 보내는 방식으로 이 한계를 우회합니다.)

```
클라이언트 (httpx, 브라우저)          서버 (FastAPI)
       │                                   │
       │──────── GET /health ────────────▶│  요청 (Request)
       │                                   │  처리 중...
       │◀─────── 200 OK ───────────────── │  응답 (Response)
       │         {"status": "ok"}          │

```

**HTTP 요청의 4가지 구성 요소**

| 구성 요소 역할 실제 예시   |                        |                                  |
| ---------------- | ---------------------- | -------------------------------- |
| **메서드 (Method)** | 무엇을 하려는가 — 동사 역할       | `GET`, `POST`                    |
| **URL (경로)**     | 어디에 요청하는가              | `/health`, `/chat/`              |
| **헤더 (Headers)** | 부가 정보 — 메타데이터          | `Content-Type: application/json` |
| **바디 (Body)**    | 전달할 데이터 (주로 POST에서 사용) | `{"message": "안녕"}`              |

**HTTP 메서드 — 동사로 의도를 표현합니다**

| 메서드 의미 서버 상태 변경 LLM 서비스에서의 실제 활용  |       |      |                                                  |
| --------------------------------- | ----- | ---- | ------------------------------------------------ |
| **GET**                           | 조회    | ❌ 없음 | `GET /health` 서버 상태 확인, `GET /docs` API 문서       |
| **POST**                          | 생성·전송 | ✅ 있음 | `POST /chat/` AI 메시지 전송, `POST /chat/stream` SSE |
| **PUT**                           | 전체 교체 | ✅ 있음 | 문서 전체 업데이트 (이 과정에서는 사용하지 않음)                     |
| **PATCH**                         | 일부 수정 | ✅ 있음 | 특정 필드 수정 (이 과정에서는 사용하지 않음)                       |
| **DELETE**                        | 삭제    | ✅ 있음 | 대화 세션 삭제 (8/18 이후 활용)                            |

> 💡 **핵심**: LLM 서비스의 90%는 GET과 POST 두 가지면 충분합니다. GET은 "정보를 읽는 것"(서버를 바꾸지 않음), POST는 "데이터를 보내는 것"(서버에 무언가를 만들거나 처리 요청)입니다.

---

**HTTP 상태 코드 — 응답 결과를 숫자로 표현합니다**

첫 번째 자리가 응답의 대분류를 나타냅니다.

| 분류 의미 앞으로 자주 보는 코드 마주치는 상황  |            |                                                  |                 |
| --------------------------- | ---------- | ------------------------------------------------ | --------------- |
| **2xx**                     | ✅ 성공       | **200 OK**                                       | 정상 요청 → 정상 응답   |
| **3xx**                     | ↪️ 리다이렉션   | (실습에서 드묾)                                        | —               |
| **4xx**                     | ❌ 클라이언트 오류 | **404** Not Found · **422** Unprocessable Entity | 잘못된 URL, 잘못된 입력 |
| **5xx**                     | 💥 서버 오류   | **500** Internal Server Error                    | 서버 코드에 버그가 있을 때 |

> ⚠️ **422를 가장 자주 만납니다**
>
> FastAPI에서 422는 "요청 형식은 맞지만 Pydantic 스키마를 통과하지 못했다"는 뜻입니다. `message` 필드가 비어있거나, 경로 파라미터에 잘못된 타입을 넣었을 때 자동으로 반환됩니다.
>
> **422를 만나면 → 응답 JSON의** **`detail`** **배열을 먼저 확인하세요.**
>
> ```
> {
>   "detail": [
>     {
>       "type": "int_parsing",
>       "loc": ["path", "item_id"],   ← 어느 파라미터가 문제인지
>       "msg": "Input should be a valid integer",  ← 거절 이유
>       "input": "abc"   ← 실제로 들어온 값
>     }
>   ]
> }
>
> ```
>
> `loc`의 두 번째 항목이 문제 파라미터명, `msg`가 이유, `input`이 받은 값입니다.

> 💡 **핵심**: HTTP는 레스토랑 주문 시스템과 같습니다. 고객(클라이언트)이 메서드+URL+헤더+바디로 구성된 주문서를 건네면, 주방(FastAPI)이 처리 후 200·422·500 같은 상태 코드와 함께 응답을 돌려줍니다. 실습에서는 `GET /health`(주문 현황 확인)와 `POST /chat/`(새 주문 접수) 두 가지면 LLM 서비스의 90%가 해결됩니다. 단 레스토랑 단골과 달리 HTTP는 무상태(stateless) — 같은 클라이언트도 매 요청마다 새 손님처럼 대하므로, 대화 이력을 유지하려면 `session_id` 같은 별도 장치가 필요합니다.

---

### 💡 **HTTP 핵심 요약**

- HTTP = 클라이언트·서버 통신 규약 — 항상 **요청 → 응답** 순서
- LLM 서비스 핵심 메서드: **GET**(상태 확인·조회) + **POST**(메시지 전송·AI 응답 요청)
- 상태 코드 3개만 먼저: **200**(성공) · **422**(입력 형식 오류) · **500**(서버 내부 오류)
- 422 원인은 응답의 `detail[0]["loc"]`와 `detail[0]["msg"]`에 있습니다

---

### 🔥 **더 알아보기 — RESTful API 설계 원칙**

REST(REpresentational State Transfer)는 HTTP를 "어떻게 잘 쓸 것인가"에 대한 설계 원칙입니다. 핵심은 **URL은 자원(명사), 메서드가 동작(동사)** 입니다.

- ✅ REST: `POST /chat/` (채팅이라는 자원에 POST — "채팅을 전송한다")
- ❌ non-REST: `POST /sendChatMessage` (동사를 URL에 포함)

FastAPI는 이 REST 원칙을 자연스럽게 구현하도록 설계되어 있습니다. 팀 프로젝트의 URL 설계에 이 원칙을 적용해보세요. 나중에 다른 개발자가 URL만 보고도 용도를 이해할 수 있습니다.

---

## 7-1 | 2. FastAPI — 파이썬 고성능 웹 프레임워크

### 핵심 개념

FastAPI는 파이썬으로 HTTP API 서버를 만드는 프레임워크입니다. 기존 Flask나 Django와 달리 **타입 힌트 하나로 입력 검증·에러 처리·API 문서화를 자동으로** 처리하고, 어제 배운 async/await를 네이티브로 지원합니다.

LLM 호출처럼 I/O 대기가 많고, 입력 형식이 중요하며, 팀원 간 API 명세 공유가 필요한 서비스 — **이 세 조건 모두에 최적화된 선택이 FastAPI입니다.**

### 상세 설명

**파이썬 웹 프레임워크 3파전 비교**

| 구분 Flask Django **FastAPI**  |               |              |                        |
| ---------------------------- | ------------- | ------------ | ---------------------- |
| 출시 연도                        | 2010          | 2005         | 2018                   |
| 철학                           | 마이크로 (필요한 것만) | 풀스택 (배터리 포함) | 고성능 API                |
| 학습 곡선                        | 낮음            | 높음           | 중간                     |
| **비동기 지원**                   | 부분적 (0.11+)   | 부분적 (3.1+)   | ✅ **설계 단계부터 네이티브**     |
| **입력 자동 검증**                 | ❌ 직접 구현       | 폼 검증만        | ✅ **Pydantic 내장**      |
| **API 문서 자동 생성**             | ❌             | ❌            | ✅ **Swagger UI·ReDoc** |
| LLM 서비스 적합성                  | 보통            | 보통           | **최적**                 |

#### **FastAPI의 3가지 핵심 강점**

**강점 ①: 타입 힌트 → 자동 입력 검증**

```
# Flask: 검증 코드를 개발자가 직접 작성해야 함
@app.route("/items/<item_id>")
def get_item_flask(item_id):
    if not item_id.isdigit():                  # ← 직접 작성
        return jsonify(error="정수여야 합니다"), 422
    return jsonify(item_id=int(item_id))

# FastAPI: 타입 힌트 하나로 동일한 검증이 자동
@app.get("/items/{item_id}")
async def get_item_fastapi(item_id: int):      # ← 타입 힌트만 쓰면 끝
    return {"item_id": item_id}
# → /items/abc 요청 시 422 + detail 자동 반환

```

**강점 ②: 타입 힌트 → /docs 자동 생성**

서버를 실행하는 순간 `http://localhost:8000/docs`에서 **Swagger UI**가 자동으로 생성됩니다. 별도 API 문서를 작성하지 않아도 팀원에게 엔드포인트 명세를 공유할 수 있고, 브라우저에서 직접 테스트도 가능합니다.

**강점 ③: async/await 네이티브 지원**

```
@app.post("/chat/")
async def chat_endpoint(message: str):
    # async def — LLM이 응답을 기다리는 동안 다른 요청을 처리 (Day 6 복습)
    result = await llm.ainvoke(message)   # await 없으면 coroutine 객체가 반환됨!
    return {"message": result.content}

```

LLM 호출은 2\~10초의 I/O 대기가 발생합니다. `async def`를 쓰면 기다리는 동안 다른 요청을 처리할 수 있습니다. Flask는 이 패턴을 추가 설정 없이는 지원하지 않습니다.

> 💡 **핵심**: FastAPI는 타입 힌트가 붙은 레시피 검증 주방과 같습니다. `item_id: int` 한 줄을 쓰는 것만으로 형식 검증(422 자동 반환)·API 문서(`/docs` 자동 생성)·비동기 처리(`async def` 네이티브)가 동시에 활성화됩니다. Flask에서는 이 세 가지를 각각 별도로 구현해야 했습니다. 단 Flask보다 초기 설정이 조금 더 명시적이며, 비즈니스 검증(접근 권한 확인 등)은 타입 힌트와 별개로 구현해야 합니다.

### 💡 **FastAPI 핵심 요약**

- FastAPI = "타입 힌트 하나로 **검증 + 문서 + 비동기** 를 동시에 해결"
- Flask는 훌륭한 프레임워크지만, LLM API처럼 타입 안전성·비동기·자동 문서화가 모두 필요한 서비스에는 FastAPI가 더 적합합니다
- **이 과정에서 FastAPI를 배우는 이유**: 오늘의 구조가 9월 RAG → 10월 MCP → 최종 프로젝트까지 그대로 확장됩니다. 한 번 익히면 5개월 내내 씁니다

### 🔥 **더 알아보기 — ASGI vs WSGI, 그리고 Starlette**

FastAPI는 내부적으로 **Starlette**(ASGI 웹 프레임워크)와 **Pydantic**(데이터 검증)을 결합한 프레임워크입니다.

- **WSGI** (Web Server Gateway Interface): Flask·Django가 사용하는 동기 방식. 요청 하나를 처리하는 동안 다음 요청은 대기합니다.
- **ASGI** (Asynchronous Server Gateway Interface): FastAPI·Starlette가 사용하는 비동기 방식. 요청 하나가 I/O를 기다리는 동안 다른 요청을 처리합니다.

`uvicorn`이 ASGI 서버 역할을 담당합니다. FastAPI의 성능 우위는 대부분 이 ASGI + uvicorn 조합에서 옵니다. 프로덕션에서는 `gunicorn + uvicorn workers` 조합으로 멀티프로세스를 추가합니다.

---

## 7-1 | 3. 최소 실행 가능 서버 (v1) — Hello, FastAPI!

### 핵심 개념

코드를 배우는 가장 빠른 방법은 실제로 실행해보는 것입니다. v1은 단 9줄로 FastAPI 서버를 만드는 예제입니다. 이 예제에서 FastAPI의 핵심 패턴인 **라우팅 · 데코레이터 · async 함수 · JSON 자동 변환** 을 한 번에 확인합니다.

이 v1이 이후 7-2에서 routers/services/schemas 구조로 확장됩니다 — 오늘 이 9줄을 완전히 이해하면 7-2 전체가 수월해집니다.

### 상세 설명

**설치**

```
# 가상환경 활성화 확인 후 (프롬프트 앞 (.venv) 표시)
pip install fastapi uvicorn[standard]

# fastapi          : 웹 프레임워크 본체 — 라우팅·검증·자동 문서 생성 담당
# uvicorn          : ASGI 서버 — FastAPI를 실제로 실행하는 서버 엔진
# [standard]       : websockets 등 추가 기능 포함 (권장 옵션)

```

**v1 코드 — 줄별 완전 해설**

```
# minimal_app.py — v1: 9줄짜리 FastAPI 서버 (7-2에서 표준 구조로 확장)

# ─── ① 임포트 ─────────────────────────────────────────────────────────────
from fastapi import FastAPI
# FastAPI 클래스: 앱 전체를 대표하는 객체. 라우터 등록, 미들웨어, 설정의 진입점

# ─── ② 앱 인스턴스 생성 ────────────────────────────────────────────────────
app = FastAPI(title="첫 번째 FastAPI 서버")
# title= : /docs 상단에 표시되는 서비스 이름
# 이 변수명 "app"이 uvicorn 실행 명령에서 :app 에 해당 ("uvicorn minimal_app:app")

# ─── ③ 엔드포인트 정의 ─────────────────────────────────────────────────────
@app.get("/")
# @app.get("/") : 라우터 데코레이터 — "GET 메서드로 / 경로에 요청이 오면 아래 함수를 실행"
# HTTP 메서드(get)와 URL 경로("/")를 함수에 연결하는 역할
# FastAPI는 @app.post, @app.put, @app.delete 도 제공

async def root():
# async def : 비동기 함수 (Day 6 복습) — I/O 대기 중 다른 요청 처리 가능
# 함수명(root)은 /docs에 엔드포인트 이름으로 표시됨

    return {"message": "Hello, FastAPI!"}
    # dict를 return → FastAPI가 JSON으로 자동 변환
    # {"message": "Hello, FastAPI!"} → Content-Type: application/json
    # 예상 응답: {"message": "Hello, FastAPI!"}

@app.get("/health")
# /health : 서버 상태 확인 엔드포인트 — 거의 모든 서비스에 관례적으로 존재
# 로드 밸런서·모니터링 도구가 이 URL을 주기적으로 호출해 서버 생존을 확인

async def health():
    return {"status": "ok"}
    # 예상 응답: {"status": "ok"}
    # Day 7 실습 노트북()에서 이 응답을 httpx로 직접 확인합니다

```

**실행 명령 — 각 옵션의 의미**

```
uvicorn minimal_app:app --reload

# uvicorn     : ASGI 서버 실행 명령
# minimal_app : 파이썬 모듈명 (파일명에서 .py 제거)
# :app        : 모듈 안에서 FastAPI()로 생성한 인스턴스 변수명
# --reload    : 코드 수정 시 서버 자동 재시작 — 개발 시에만 사용, 배포 시 제거!

```

성공 시 터미널에 보이는 메시지:

```
INFO:     Uvicorn running on <http://127.0.0.1:8000> (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.    ← 이 줄이 보이면 준비 완료!

```

**브라우저에서 확인하는 3가지 URL**

| URL 확인 내용 예상 결과                |                      |                                  |
| ------------------------------ | -------------------- | -------------------------------- |
| `http://localhost:8000/`       | 루트 엔드포인트 응답          | `{"message": "Hello, FastAPI!"}` |
| `http://localhost:8000/health` | 서버 상태                | `{"status": "ok"}`               |
| `http://localhost:8000/docs`   | **Swagger UI** 자동 문서 | 등록된 엔드포인트 목록 + 브라우저 직접 테스트       |

---

> ⚠️ **흔한 실수 — PYTHONPATH 오류**
>
> `uvicorn minimal_app:app`은 **파일이 있는 폴더에서 실행**해야 합니다.
>  7-2에서 `app/main.py` 구조가 되면 프로젝트 루트에서 `uvicorn app.main:app`으로 변경됩니다.
>
> bash
>
> ```
> # 오류 상황
> cd /Users/me/projects        # ← 상위 폴더에서 실행하면
> uvicorn minimal_app:app      # ModuleNotFoundError: No module named 'minimal_app'
>
> # 올바른 실행
> cd /Users/me/projects/my_llm_service   # ← 파일이 있는 폴더로 이동 후
> uvicorn minimal_app:app                # 정상 실행
>
> ```

> 💡 **핵심**: FastAPI 서버 구동은 IKEA 가구 조립과 같습니다. `app = FastAPI()`로 뼈대를 만들고, `@app.get("/")`으로 URL 표지판을 붙이고, `uvicorn minimal_app:app --reload`로 전원을 켜면 완성됩니다. `dict`를 `return`하는 것만으로 JSON 변환이 자동이고, 코드가 존재하는 것만으로 `/docs` 문서가 자동 생성됩니다. 단 `uvicorn minimal_app:app`에서 `minimal_app`은 파일명, `app`은 인스턴스 변수명 — 7-2 표준 구조에서는 `uvicorn app.main:app`으로 바뀝니다.

---

### 💡 **최소 서버 핵심 요약**

- `@app.get("/경로")` 데코레이터가 **URL 경로와 함수**를 연결합니다
- 함수가 `dict`를 `return`하면 FastAPI가 **JSON으로 자동 변환**합니다
- `/docs`는 코드만 작성하면 **자동으로 생성**됩니다 — 팀원과의 API 소통 도구
- `Application startup complete.` 가 터미널에 보이면 서버 준비 완료
- v1의 `uvicorn minimal_app:app` → 7-2에서 `uvicorn app.main:app` 으로 변경됩니다

---

### 🔥 **더 알아보기 —** **`uvicorn 모듈명:인스턴스명`** **규칙**

`uvicorn minimal_app:app`에서 두 부분의 의미:

- `minimal_app` → 파이썬 모듈명 (파일 경로를 `.`으로 구분한 것)
- `app` → 파일 안에서 `FastAPI()`로 생성한 변수명

7-2에서 표준 구조(`app/main.py`)로 바뀌면 `uvicorn app.main:app`입니다.
 `app` 패키지(폴더) 안의 `main` 모듈에 있는 `app` 인스턴스를 실행하라는 뜻입니다.

인스턴스 변수명을 `server = FastAPI()`처럼 바꾸면 `uvicorn minimal_app:server`로 실행해야 합니다. **모듈명·인스턴스명이 명령어와 반드시 일치해야 합니다.**

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  FastAPI와 uvicorn을 설치하고 `minimal_app.py`를 실행한다
- [ ]  브라우저에서 `/health`와 `/docs`를 열어 동작을 확인한다

#### 🔰 기본 실습 — 단계별 가이드

> AI 코파일럿(Claude Code / Cursor) 사용 권장. 코드 암기가 아닌 흐름 이해가 목표.

📖 강의 연계: Day 7 실습 노트북  → 셀 03\~05 (서버 확인 단계)

**Step 1** 가상환경 활성화 확인 — 터미널 프롬프트 앞에 `(.venv)` 표시 여부

**Step 2** `pip install fastapi uvicorn[standard]`

**Step 3** 강의 코드를 보고 `minimal_app.py` 직접 작성 (코파일럿 없이 한 번 시도)

**Step 4** `uvicorn minimal_app:app --reload` 실행 → `Application startup complete.` 확인

**Step 5** 브라우저에서 `http://localhost:8000/docs` 열기

**Step 6** Swagger UI에서 `/health` 클릭 → **"Try it out"** → **Execute** → 응답 JSON 확인

#### ⭐ 심화 실습

```
# 심화 실습 사전 준비:
# 1. pip install anthropic
# 2. .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 추가
#    (Anthropic Console: <https://console.anthropic.com> 에서 발급)

# anthropic SDK를 사용하는 헬스체크 엔드포인트 추가
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
load_dotenv()   # .env에서 API 키 로드

@app.get("/ping-claude")
async def ping_claude():
    """Claude API 연결 상태를 확인하는 헬스체크 엔드포인트"""
    client = AsyncAnthropic()
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": "OK?"}]
    )
    return {"claude_status": "ok", "response": msg.content[0].text}
    # 예상 응답: {"claude_status": "ok", "response": "OK"}

```

⭐ **추가 도전**: OpenAI(`/ping-openai`)와 Claude(`/ping-claude`) 두 엔드포인트를 모두 만들고 `/docs`에서 두 응답 속도를 비교해보세요. 어느 쪽이 더 빠른가요?

#### 예상 결과물 & 제출 기준

| 구분 내용 확인 방법  |                              |                                       |
| ------------ | ---------------------------- | ------------------------------------- |
| 🔰 기본        | `uvicorn` 실행 후 `/docs` 스크린샷  | Swagger UI에 `/health`, `/` 두 엔드포인트 표시 |
| ⭐ 심화         | `/ping-claude` 엔드포인트 응답 JSON | 터미널 또는 `/docs` Try it out 결과          |

---

---

# 📦 모듈 7-2 · FastAPI 표준 프로젝트 구조

| 항목 내용                  |                                                       |
| ---------------------- | ----------------------------------------------------- |
| **모듈 목표**              | routers/services/schemas 3계층으로 분리된 FastAPI 프로젝트를 생성하고 |
| `/health` 엔드포인트를 동작시킨다 |                                                       |
| **선수 지식**              | 7-1 FastAPI 기초, Day 3 Pydantic BaseModel 개념           |
| **난이도**                | 🔰⭐ 기본+심화                                             |

---

### 📚 강의 교안

## 7-2 | 1. 왜 구조가 필요한가 — 스파게티 코드의 문제

### 핵심 개념

7-1에서 만든 `minimal_app.py` 한 파일로 서비스가 성장하면 어떻게 될까요? 기능이 추가될수록 파일은 수백 줄로 불어나고, 어디서 버그가 나는지, 어느 함수가 무슨 역할인지 파악하기 어려워집니다. 이것이 **스파게티 코드**입니다. 면발이 서로 엉켜 어느 가닥을 잡아당겨도 다 따라오는 것처럼, 코드 한 줄 고치려다 전혀 다른 기능이 망가집니다.

**표준 프로젝트 구조는 이 문제를 "각자 맡은 파일에서만 일하는 구조"로 해결합니다.** 오늘 만드는 이 골격은 9월 RAG → 10월 MCP → 최종 프로젝트까지 파일만 추가하며 그대로 확장됩니다.

### 상세 설명

**스파게티 코드 vs 계층 분리 — 실제 비교**

```
# ❌ 스파게티 코드 — main.py 한 파일에 모든 것이 섞임
# 2주 후: 300줄, 누가 무슨 역할인지 모름
from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os, time, json

load_dotenv()
app = FastAPI()
llm = ChatOpenAI(model="gpt-4o-mini")

@app.get("/health")
async def health(): ...             # 상태 확인 로직

@app.post("/chat/")
async def chat(message: str):       # LLM 호출 로직 — 서비스 레이어가 없음
    result = await llm.ainvoke(...)
    return result                   # 파싱도 여기서

@app.post("/summarize/")
async def summarize(text: str):     # 또 다른 LLM 로직
    ...                             # LLM 객체를 또 만들어야 하나?

```

```
# ✅ 계층 분리 — 각자 맡은 파일에서만 일함
routers/chat.py      → "어떤 URL로 요청이 들어오는가?" 만 담당
services/llm_service.py → "LLM을 어떻게 호출하는가?" 만 담당
schemas/chat.py      → "데이터 모양이 어떠한가?" 만 담당
main.py              → "라우터를 어디에 연결하는가?" 만 담당

```

**변경에 강한 구조**

| 변경 시나리오 스파게티 코드 계층 분리  |                                     |                                                    |
| ---------------------- | ----------------------------------- | -------------------------------------------------- |
| 프롬프트 수정                | [main.py](http://main.py) 전체를 뒤져야 함 | `services/llm_service.py` 1개 파일만                   |
| 새 엔드포인트 추가             | 기존 코드에 끼워넣기                         | `routers/`에 새 파일 추가 + [main.py](http://main.py) 1줄 |
| 9월 RAG 기능 추가           | 기존 코드와 얽힘                           | `routers/rag.py` + `services/rag_service.py` 추가    |
| 10월 MCP 연동             | 어디서부터 건드려야?                         | `routers/mcp.py` + `services/mcp_service.py` 추가    |

> 💡 **핵심**: 계층을 나누는 기준은 "**변경 이유**"입니다. 프롬프트를 바꿀 때, URL을 바꿀 때, 데이터 구조를 바꿀 때 — 각각 다른 이유로 변경됩니다. 이유가 다르면 파일을 분리하세요. 이것이 소프트웨어 설계의 단일 책임 원칙(SRP)입니다.

---

### 💡 **구조 분리 핵심 요약**

- 스파게티 코드: 기능이 늘수록 한 파일이 비대해져 유지보수 불가
- 계층 분리: 변경 이유가 다른 코드를 다른 파일에 — 수정 범위가 명확해짐
- **오늘 만드는 구조는 최종 프로젝트까지 그대로 씁니다 — 한 번만 제대로 이해하면 됩니다**

---

### 🔥 **더 알아보기 — MVC 패턴과의 관계**

FastAPI의 routers/services/schemas 구조는 전통적인 **MVC(Model-View-Controller)** 패턴의 변형입니다.

| MVC FastAPI 계층 역할  |             |                      |
| ------------------ | ----------- | -------------------- |
| Controller         | `routers/`  | HTTP 요청 수신·응답 반환     |
| Model              | `schemas/`  | 데이터 구조 정의 (Pydantic) |
| Service(Logic)     | `services/` | 비즈니스 로직 (LLM 호출 등)   |

View(화면)는 FastAPI가 API 서버이므로 존재하지 않습니다. 8/22 Streamlit이 View 역할을 담당합니다.
 이 패턴을 이해하면 Spring, Django REST, Express.js 어떤 프레임워크도 구조가 익숙하게 느껴집니다.

---

## 7-2 | 2. 3계층 설계 — 각 파일의 역할과 책임

### 핵심 개념

표준 구조의 각 폴더는 명확한 한 가지 책임만 집니다. `routers/`는 "어떤 URL로 요청이 들어오는가", `services/`는 "실제로 무슨 일을 하는가", `schemas/`는 "데이터 모양이 어떠한가"입니다. `main.py`는 이 세 계층을 연결하는 안내 데스크입니다.

### 상세 설명

**데이터 흐름: 요청이 들어와서 응답이 나가기까지**

```
사용자 요청 POST /chat/
        │
        ▼
┌─────────────────────┐
│  main.py            │  ← "이 URL은 chat.router가 처리"를 등록해둠
│  (안내 데스크)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  routers/chat.py    │  ← URL 수신, 파라미터 파싱
│  (부서 담당자)       │     service 함수 호출
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  services/          │  ← LLM 호출, 프롬프트 조합, 결과 처리
│  llm_service.py     │     (비즈니스 로직의 집)
│  (실무 부서)         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  schemas/chat.py    │  ← 입력·출력 데이터 모양 정의
│  (공통 양식 서랍)    │     (Day 8부터 본격 활용)
└─────────────────────┘
           │
           ▼
       응답 반환

```

**표준 디렉토리 구조 — 파일별 역할 주석 포함**

```
my_llm_service/               ← 프로젝트 루트 (uvicorn 실행 위치)
│
├── app/                      ← Python 패키지 (__init__.py 필요)
│   ├── __init__.py           ← "app 폴더를 Python 패키지로 인식" 선언
│   │
│   ├── main.py               ← ① 앱 초기화 + 라우터 등록 (안내 데스크)
│   │                            "어떤 URL을 어느 라우터가 처리하는가"만 담당
│   ├── dependencies.py       ← ② Depends 주입 대상 (Day 8에서 작성)
│   │                            LLM 클라이언트 싱글턴 등
│   ├── routers/              ← ③ HTTP 엔드포인트 정의 (URL · 메서드 · 파라미터)
│   │   ├── __init__.py
│   │   ├── health.py         ←    GET /health
│   │   └── chat.py           ←    POST /chat/, POST /chat/stream
│   │
│   ├── services/             ← ④ 비즈니스 로직 (LLM 호출, 프롬프트, 후처리)
│   │   ├── __init__.py
│   │   └── llm_service.py    ←    get_chat_response(), stream_chat_response()
│   │
│   └── schemas/              ← ⑤ Pydantic 데이터 모델 (요청·응답 타입 계약서)
│       ├── __init__.py
│       └── chat.py           ←    ChatRequest, ChatResponse (Day 8에서 작성)
│
├── .env                      ← API 키 보관 — 절대 Git에 올리지 않음
├── .gitignore                ← .env, .venv/ 포함 필수
└── requirements.txt          ← pip install -r requirements.txt 로 일괄 설치

```

> ℹ️ **`__init__.py`****가 필요한 이유**
>
> Python은 `__init__.py`가 있는 폴더만 "패키지"로 인식합니다. 없으면 `from app.routers import chat`처럼 폴더를 가로지르는 임포트가 `ModuleNotFoundError`를 냅니다. 파일 내용은 완전히 비워도 됩니다 — 존재 자체가 선언입니다.

**9월·10월 확장 시 구조 변화**

```
# 9월 RAG 추가 시 — 기존 파일은 한 줄도 변경하지 않음
├── routers/
│   ├── health.py     ← 기존 (변경 없음)
│   ├── chat.py       ← 기존 (변경 없음)
│   └── rag.py        ← 새로 추가 (POST /rag/query)
└── services/
    ├── llm_service.py  ← 기존 (변경 없음)
    └── rag_service.py  ← 새로 추가

# main.py에 한 줄만 추가
app.include_router(rag.router, prefix="/rag", tags=["RAG"])

```

---

> 💡 **핵심**: 표준 프로젝트 구조는 잘 정리된 사무실과 같습니다. `routers/`는 부서 담당자("이 URL은 내 창구"), `services/`는 실무 부서("LLM을 어떻게 호출할지"), `schemas/`는 공통 양식 서랍("데이터 모양"), `main.py`는 안내 데스크("어느 부서로")입니다. 9월 RAG를 추가할 때도 기존 파일은 건드리지 않고 `routers/rag.py`와 `services/rag_service.py`만 추가하면 됩니다 — `include_router(rag.router)` 한 줄이 전부입니다. 단 서비스가 5개를 넘어가면 파일 간 의존성이 복잡해지므로 Day 8의 `Depends` 패턴이 필수입니다.

---

### 💡 **2. 3계층 설계 핵심 요약**

- **routers/** = URL 수신 · 파라미터 파싱 · 응답 반환 (HTTP 담당)
- **services/** = 실제 LLM 호출 · 프롬프트 · 후처리 (비즈니스 로직 담당)
- **schemas/** = 데이터 타입 계약서 (Day 8부터 본격 활용)
- [**main.py**](http://main.py) = 라우터 등록만 (안내 데스크)
- 기억 공식: **"URL 변경 → routers, 로직 변경 → services, 타입 변경 → schemas"**

---

### 🔥 **더 알아보기 —** **`prefix`****와** **`tags`****의 역할**

`app.include_router(chat.router, prefix="/chat", tags=["Chat"])`의 두 파라미터:

- **`prefix="/chat"`**: [chat.py](http://chat.py) 안의 `@router.post("/")` → 실제 URL은 `/chat/`으로 등록됩니다. `@router.post("/stream")` → `/chat/stream`으로 등록됩니다. prefix가 앞에 붙는 것입니다.
- **`tags=["Chat"]`**: Swagger UI(/docs)에서 엔드포인트를 그룹으로 묶는 라벨입니다. `tags=["Health"]`, `tags=["Chat"]`로 구분하면 /docs가 섹션별로 정리되어 보입니다.

흔한 실수: prefix를 `/chat/`(슬래시 끝에 포함)으로 쓰고 router 내부에도 `/`를 쓰면 `/chat//`가 됩니다. **prefix는 슬래시 없이** **`/chat`**, router 내부 경로는 `/`로 시작하는 것이 관례입니다.

---

## 7-2 | 3. 코드로 보는 3계층 — 파일별 완전 해설

### 핵심 개념

4개 파일이 어떻게 서로를 호출하는지 코드를 따라가며 확인합니다. `main.py`에서 시작해 `routers → services` 순서로 읽으면 데이터 흐름이 보입니다.

### 상세 설명

#### ① app/main.py — 안내 데스크

```
# app/main.py
# 역할: 앱 초기화 + 라우터 등록 (안내 데스크)
# 이 파일은 "어떤 URL을 어느 라우터가 처리하는가"만 담당
# LLM 호출 코드, 프롬프트, 검증 로직은 절대 이 파일에 넣지 않습니다

from fastapi import FastAPI
from app.routers import chat, health
# from app.routers import chat  →  app/routers/chat.py 를 모듈로 임포트
# → 이 임포트가 성공하려면 app/__init__.py, app/routers/__init__.py 가 존재해야 함

app = FastAPI(
    title="LG CNS AI 서비스",                     # /docs 상단 서비스명
    description="MCP 기반 Agentic AI 서비스 개발자 과정 미니프로젝트",  # /docs 설명
    version="0.1.0",                              # /docs 버전 표시
)

# ── 라우터 등록 ──────────────────────────────────────────────────────────
# include_router: "이 라우터를 앱에 연결해라" — 부서를 안내 데스크에 등록하는 것
app.include_router(health.router)
# health.router: health.py 안의 router = APIRouter() 인스턴스
# prefix 없음 → health.py 안의 @router.get("/health") 가 그대로 /health

app.include_router(chat.router, prefix="/chat", tags=["Chat"])
# prefix="/chat" → chat.py 안의:
#   @router.post("/")       → 실제 등록 URL: POST /chat/
#   @router.post("/stream") → 실제 등록 URL: POST /chat/stream  (Day 9에서 추가)
# tags=["Chat"] → /docs에서 Chat 그룹으로 묶임

```

#### ② app/routers/health.py — 상태 확인 엔드포인트

```
# app/routers/health.py
# 역할: GET /health 엔드포인트 하나만 담당
# 서비스 로직이 없으므로 services/ 를 임포트하지 않음

from fastapi import APIRouter

router = APIRouter()
# APIRouter(): 이 파일만의 라우터 인스턴스
# main.py 의 FastAPI() 앱 전체와 다름 — 부서 내 담당자 수준
# main.py에서 app.include_router(health.router)로 앱에 연결됨

@router.get("/health", tags=["Health"])
# @router.get → APIRouter 인스턴스의 GET 등록 (app.get 이 아님!)
# "/health" → main.py에서 prefix 없이 등록되므로 실제 URL도 /health
# tags=["Health"] → /docs에서 Health 그룹으로 표시
async def health_check():
    """
    서버 상태를 확인합니다.
    로드 밸런서·쿠버네티스·모니터링 도구가 주기적으로 호출합니다.
    이 엔드포인트가 200을 반환하면 "서버 정상"으로 판단합니다.
    """
    return {"status": "ok", "service": "lgcns-ai-service"}
    # dict 반환 → FastAPI가 JSON 자동 변환
    # 예상 응답: {"status": "ok", "service": "lgcns-ai-service"}

```

#### ③ app/services/llm\_service.py — LLM 호출 비즈니스 로직

```
# app/services/llm_service.py
# 역할: "실제로 LLM을 어떻게 호출하는가"만 담당
# routers/가 이 파일의 함수를 "호출"만 함 — 로직을 이해할 필요 없이

# ── ① 환경변수 로드 (필수! 없으면 401 AuthenticationError) ──────────────
from dotenv import load_dotenv
load_dotenv()   # .env 파일 → 환경변수로 등록
                # 이 줄이 없으면 OPENAI_API_KEY를 못 읽어 첫 호출부터 에러

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ── ② LLM 비즈니스 로직 함수 ──────────────────────────────────────────────
async def get_chat_response(message: str, session_id: str) -> str:
    """
    사용자 메시지를 받아 LLM 응답 텍스트를 반환합니다.

    Args:
        message   : 사용자 입력 텍스트 (routers/chat.py에서 전달)
        session_id: 세션 식별자
                    현재는 미사용 — 8/18 DB 기반 대화 이력 구현 시 활용 예정
    Returns:
        str: LLM 응답 텍스트 (AIMessage.content)
    """
    # LLM 인스턴스 생성 — Day 8에서 Depends로 싱글턴 패턴으로 개선
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # 프롬프트 템플릿 (Day 2 복습 — ChatPromptTemplate + 변수)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "유용한 AI 어시스턴트입니다. 한국어로 친절하게 답하세요."),
        ("human", "{message}"),   # {message} 자리에 사용자 입력이 채워짐
    ])

    chain = prompt | llm          # LCEL 파이프 (Day 3 복습)
                                  # PromptTemplate → ChatOpenAI 순서로 실행

    result = await chain.ainvoke({"message": message})
    # await   : 비동기 — LLM 응답 기다리는 동안 다른 요청 처리 가능 (Day 6 복습)
    # ainvoke : async 버전 invoke — async def 안에서는 반드시 ainvoke!
    # {"message": message} : 프롬프트 템플릿의 {message} 자리에 채울 값

    return result.content
    # result  : AIMessage 객체 (메시지 전체)
    # .content: 그 중 텍스트만 추출
    # 예상 반환: "안녕하세요! 무엇을 도와드릴까요?"

```

> ⚠️ 이번 **주차 절대 규칙 — async def 안에서 동기 호출 금지**
>
> ```
> # ❌ 절대 금지 — async def 안에서 동기 invoke()
> result = chain.invoke({"message": message})   # 이벤트 루프 점유 → 서버 전체 정지
>
> # ✅ 반드시 await + ainvoke()
> result = await chain.ainvoke({"message": message})
>
> ```
>
> `async def` 안에서 동기 `invoke()`를 호출하면 해당 LLM 응답이 오기까지 이벤트 루프 전체가 멈춥니다. 10명이 동시에 요청하면 9명은 첫 번째 사람이 끝날 때까지 기다립니다. 이 규칙은 Day 8 Depends, Day 9 스트리밍에서도 동일하게 적용됩니다.

> 💡 **핵심**: 3계층의 코드 흐름은 회사 조직도와 같습니다. `main.py`(안내 데스크)가 `include_router(chat.router, prefix="/chat")`으로 부서를 등록하면, `POST /chat/` 요청이 오면 `routers/chat.py`(부서 담당자)가 받아 `services/llm_service.py`(실무 부서)에 `await get_chat_response(message, session_id)`로 위임합니다. 실무 부서는 담당자가 누군지 몰라도 됩니다 — 단방향 임포트(`from app.services.llm_service import get_chat_response`)만 합니다. 단 순환 임포트(services가 routers를 참조하는 등)가 생기면 `ImportError`가 발생하므로 의존성 방향은 항상 `main → routers → services` 한 방향이어야 합니다.

#### ④ app/routers/chat.py — 채팅 엔드포인트 (기초 버전)

```
# app/routers/chat.py
# 역할: /chat/ URL 수신, service 함수 호출, 응답 반환
# 이 파일은 LLM 호출 방법을 몰라도 됨 — get_chat_response() 를 호출만 함

from fastapi import APIRouter
from app.services.llm_service import get_chat_response
# services 레이어를 임포트 — routers는 services를 호출하지만
# services는 routers를 몰라야 합니다 (단방향 의존성)

router = APIRouter()

@router.post("/")
# prefix="/chat" (main.py에서 등록) + "/" → 실제 URL: POST /chat/
async def chat_endpoint(message: str, session_id: str = "default"):
    """
    AI 채팅 응답 엔드포인트

    현재 기초 버전: message는 쿼리 파라미터로 전달
    → POST /chat/?message=안녕&session_id=s1

    Day 8 업그레이드 예정: Pydantic ChatRequest 바디로 변경
    → POST /chat/ + JSON body {"message": "안녕", "session_id": "s1"}
    """
    # service 레이어에 실제 처리 위임 — 라우터는 호출만 함
    response = await get_chat_response(message, session_id)

    return {"message": response, "session_id": session_id}
    # 예상 응답: {"message": "안녕하세요!...", "session_id": "default"}

```

#### 서버 실행 & 확인

```
# 프로젝트 루트(my_llm_service/ 폴더)에서 실행
uvicorn app.main:app --reload --port 8000

# uvicorn     : ASGI 서버
# app.main    : app/ 패키지의 main 모듈 (app/main.py)
# :app        : main.py 안의 FastAPI() 인스턴스 변수명
# --reload    : 파일 변경 시 자동 재시작
# --port 8000 : 포트 지정 (기본값도 8000 — 명시적으로 쓰는 것 권장)

# ── 확인 순서 ──────────────────────────────────────────────────────────
# 1. 터미널: INFO: Application startup complete.
# 2. <http://localhost:8000/health> → {"status": "ok", "service": "lgcns-ai-service"}
# 3. <http://localhost:8000/docs>  → Swagger UI — Health / Chat 두 그룹 확인

```

---

#### ❌ vs ✅ — API 키 관리 규칙 (반드시 지킬 것)

```
# ❌ 절대 금지 — API 키를 코드에 직접 작성
llm = ChatOpenAI(api_key="sk-proj-xxxx...")
# GitHub에 한 번이라도 올라가면 봇이 즉시 수집 → 수십만 원 청구 사례 빈번

# ✅ 올바른 방법 — .env에 저장, load_dotenv()로 불러오기
from dotenv import load_dotenv
load_dotenv()           # .env 파일 읽기 → 환경변수로 등록
llm = ChatOpenAI()      # api_key를 명시하지 않아도 OPENAI_API_KEY 환경변수에서 자동 로드

```

```
# .gitignore — 프로젝트 루트에 반드시 생성
.env          # ← API 키 파일 Git 추적 제외
.venv/        # 가상환경 폴더
__pycache__/  # 파이썬 캐시

```

---

### 💡 **코드 완전 해설 핵심 요약**

- `main.py`는 라우터 등록만 — LLM·프롬프트·검증 코드가 이 파일에 있으면 구조 위반
- `routers/`는 URL·파라미터·응답 반환만 — 비즈니스 로직은 반드시 `services/`에
- `services/`는 `from dotenv import load_dotenv` + `load_dotenv()` 필수 — 없으면 401 에러
- `async def` 안에서는 반드시 `ainvoke()` — `invoke()`는 서버를 멈춤
- `prefix="/chat"` 은 슬래시 없이, router 내부 경로는 `/`로 시작 (중복 방지)

---

### 🔥 **더 알아보기 — 단방향 의존성 원칙**

파일 간 임포트 방향이 중요합니다.

```
main.py → routers/ → services/ → (LangChain, OpenAI)
                     schemas/

```

화살표는 항상 위에서 아래로만 흘러야 합니다. `services/`가 `routers/`를 임포트하거나, `routers/`가 `main.py`를 임포트하면 순환 임포트(circular import) 에러가 발생합니다.

이 단방향 의존성은 Clean Architecture, Hexagonal Architecture의 핵심 원칙이기도 합니다. 오늘 자연스럽게 이 원칙대로 코드를 작성하게 됩니다.

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  표준 구조 디렉토리를 처음부터 생성한다
- [ ]  `/health` 엔드포인트가 응답하고 `/docs`에 표시된다
- [ ]  팀 리포에도 같은 구조를 적용할 준비를 마친다

#### 🔰 기본 실습 — 단계별 가이드

> AI 코파일럿(Claude Code / Cursor) 사용 권장. 단, 각 파일의 "역할"은 본인 언어로 설명할 수 있어야 합니다.

📖 강의 연계: Day 7 실습 노트북  → 셀 03\~05 (서버 확인)

**Step 1** 폴더 구조 생성

```
mkdir -p app/routers app/services app/schemas

```

**Step 2** `__init__.py` 생성 (각 폴더마다)

```
# macOS/Linux
touch app/__init__.py app/routers/__init__.py app/services/__init__.py app/schemas/__init__.py

# Windows PowerShell
"" | Out-File app/__init__.py
"" | Out-File app/routers/__init__.py
"" | Out-File app/services/__init__.py
"" | Out-File app/schemas/__init__.py

```

**Step 3** `app/main.py`, `app/routers/health.py`, `app/services/llm_service.py` 작성 (강의 교안 참조)

**Step 4** `uvicorn app.main:app --reload` — `Application startup complete` 확인

**Step 5** `http://localhost:8000/health` 응답 + `/docs` Swagger 스크린샷을 슬랙 `#day7-제출`

#### ⭐ 심화 실습

```
# 심화 1: 요청 로깅 미들웨어 — 모든 요청의 메서드·경로·상태코드·소요시간을 출력
# 위치: app/main.py에 include_router 위에 삽입

import time
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # call_next: 실제 엔드포인트 함수를 실행하는 콜백
    start = time.time()
    response = await call_next(request)        # 엔드포인트 처리
    duration = time.time() - start
    # 터미널에 출력: "POST /chat/ → 200 (2.341s)"
    print(f"{request.method}{request.url.path} →{response.status_code} ({duration:.3f}s)")
    return response

# 심화 2: CORS 설정 — 브라우저 프론트엔드에서 이 API를 호출할 때 필요
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["<http://localhost:3000>"],  # Streamlit 포트 (8/22 Streamlit 수업 대비)
    allow_methods=["*"],
    allow_headers=["*"],
)

```

⭐ **추가 도전**: 미들웨어를 추가한 후 `/chat/`에 요청을 보내보세요. 터미널에 `POST /chat/ → 200 (X.XXXs)` 로그가 찍히는 것을 확인하고, LLM 응답에 몇 초가 걸리는지 측정해보세요.

---

---

# 📦 모듈 7-3 · 파라미터 처리

| 항목 내용                                                     |                                                  |
| --------------------------------------------------------- | ------------------------------------------------ |
| **모듈 목표**                                                 | 경로·쿼리 파라미터를 직접 구현해 타입 힌트 자동 검증을 확인하고,            |
| 바디 파라미터의 개념을 이해한다 (바디는 Day 8에서 Pydantic BaseModel로 완전 구현) |                                                  |
| **선수 지식**                                                 | 7-2 FastAPI 기초, 파이썬 타입 힌트 (`int`, `str`, `bool`) |
| **난이도**                                                   | 🔰⭐ 기본+심화                                        |

---

### 📚 강의 교안

#### 왜 배우는가

FastAPI에 요청을 보내는 방법은 3가지입니다. “URL에 주소처럼 넣는 값”, “URL 뒤 `?`로 붙이는 값”, “요청 본문에 숨기는 값” — 각각 쓰임새가 다르고, FastAPI는 이 위치에 따라 자동으로 파싱하고 타입을 검증합니다. 이걸 이해하면 API 에러(422)의 90%를 혼자 해결할 수 있게 됩니다.

---

## 7-3 | 1. 파라미터 — 클라이언트가 서버에 정보를 전달하는 3가지 위치

### 핵심 개념

서버에 요청을 보낼 때 "어떤 데이터를 원하는지"를 함께 전달해야 합니다. 예를 들어 "42번 상품"을 조회하거나, "AI"라는 키워드로 검색하거나, 긴 채팅 메시지를 보낼 때 — 이 값들을 담는 위치가 3가지입니다: **URL 경로 안**, **URL 뒤 ?로 붙이는 것**, **요청 본문**. FastAPI는 이 위치에 따라 파라미터를 자동으로 구분하고 타입을 검증합니다.

### 상세 설명

**3가지 파라미터 — 한눈에 비교**

| 구분 위치 URL 예시 특징 주로 사용하는 메서드  |                    |                              |                      |                  |
| ---------------------------- | ------------------ | ---------------------------- | -------------------- | ---------------- |
| **경로 파라미터**                  | URL 경로 안 `{변수}`    | `/items/42`                  | 항상 필수 · 리소스 식별용      | GET, DELETE      |
| **쿼리 파라미터**                  | URL 뒤 `?key=value` | `/search?keyword=AI&limit=5` | 선택 가능 · 필터·정렬·페이지    | GET              |
| **바디 파라미터**                  | 요청 본문 (JSON)       | (URL에 안 보임)                  | 복잡한 구조 가능 · 길이 제한 없음 | POST, PUT, PATCH |

**FastAPI가 파라미터 종류를 자동으로 구분하는 방법**

FastAPI는 별도 설정 없이 **파이썬 타입 힌트만 보고** 파라미터 종류를 판단합니다.

```
규칙 1. 경로 파라미터 : 데코레이터 URL에 {변수명} 이 있으면 → 경로 파라미터
규칙 2. 바디 파라미터 : 타입이 Pydantic BaseModel 이면 → 요청 본문에서 읽음 (Day 8)
규칙 3. 쿼리 파라미터 : 위 두 가지가 아닌 나머지 전부 → 쿼리 파라미터 (?key=value)

```

```
@app.get("/items/{item_id}")          # URL에 {item_id} 있음
async def example(
    item_id: int,                     # → 경로 파라미터 (규칙 1)
    keyword: str,                     # → 쿼리 파라미터 (규칙 3, 필수)
    limit: int = 10,                  # → 쿼리 파라미터 (규칙 3, 선택 — 기본값 있음)
    # request: ChatRequest            # → 바디 파라미터 (규칙 2, Day 8에서 추가)
):
    ...
# 이 함수는 세 파라미터 모두 다 다른 위치에서 읽습니다
# GET /items/42?keyword=AI&limit=5

```

---

> 💡 **핵심**: 파라미터 위치는 편지에 정보를 어디에 담느냐와 같습니다. 봉투 겉면(경로 파라미터 `/items/42`)은 필수 식별자로, 바꾸면 다른 리소스가 됩니다. 봉투 뒷면 메모(쿼리 파라미터 `?keyword=AI&limit=5`)는 있어도 없어도 되는 조건 값입니다. 봉투 안 내용물(바디 파라미터 — Day 8)은 겉에서 안 보이고 복잡한 구조를 담습니다. FastAPI는 타입 힌트 규칙 3가지(`{변수명}` → 경로, `BaseModel` → 바디, 나머지 → 쿼리)만으로 이 위치를 자동 판단합니다. 단 GET 요청에 바디를 쓰는 것은 HTTP 관례에 맞지 않으며, API는 형식이 맞지 않는 요청을 자동으로 422로 거절합니다.

---

### 💡 **파라미터 개요 핵심 요약**

- **경로 파라미터**: URL 경로 안 `{변수명}` — 항상 필수 · 리소스 식별
- **쿼리 파라미터**: URL 뒤 `?key=value` — 선택 가능 · 필터·정렬
- **바디 파라미터**: 요청 본문 — 복잡한 구조 · POST에서 사용 (Day 8에서 완전 구현)
- FastAPI는 **타입 힌트 위치만 보고** 세 가지를 자동으로 구분합니다 — 별도 데코레이터 불필요

---

### 🔥 **더 알아보기 — 언제 경로? 언제 쿼리? 실전 선택 기준**

| 상황 권장 파라미터 이유     |        |                                         |
| ----------------- | ------ | --------------------------------------- |
| 특정 리소스를 하나만 가리킬 때 | **경로** | `/users/42`, `/posts/123` — 고유 식별자      |
| 선택 필터·정렬·페이지네이션   | **쿼리** | `/posts?author=kim&sort=date&page=2`    |
| 복잡한 생성·수정 데이터     | **바디** | `POST /chat/` — 긴 메시지, 여러 필드            |
| 검색어 전달            | **쿼리** | `/search?q=LangChain` — 브라우저에서 직접 공유 가능 |

규칙: **"URL로 리소스를 특정하고, 쿼리로 조건을 붙이고, 바디로 내용을 담는다."**

---

## 7-3 | 2. 경로 파라미터 — URL에 직접 박힌 필수값

### 핵심 개념

경로 파라미터는 URL 경로의 일부입니다. `/items/42`에서 `42`가 경로 파라미터입니다. 리소스를 **고유하게 식별**할 때 씁니다. 경로 파라미터가 없으면 "어떤 아이템"인지 알 수 없으므로 항상 필수입니다.

### 상세 설명

```
# app/routers/items.py

from fastapi import APIRouter

router = APIRouter()

# ── 경로 파라미터 기본 ──────────────────────────────────────────────────────
@router.get("/items/{item_id}")
# {item_id} : 중괄호로 감싼 부분이 경로 파라미터 자리표시자
# URL /items/42 → item_id = 42 으로 함수에 전달됨
async def get_item(item_id: int):
# item_id: int : 타입 힌트 int → FastAPI가 문자열→정수 자동 변환 + 실패 시 422
    return {"item_id": item_id}
    # GET /items/42  → {"item_id": 42}     ✅ (문자열 "42" → 정수 42 자동 변환)
    # GET /items/abc → 422 자동 반환       ❌ (정수 변환 불가)
    # GET /items/3.5 → 422 자동 반환       ❌ (float은 int가 아님)

# ── 경로 파라미터 여러 개 사용 ───────────────────────────────────────────────
@router.get("/users/{user_id}/posts/{post_id}")
async def get_user_post(user_id: int, post_id: int):
    # URL: /users/7/posts/42 → user_id=7, post_id=42
    # 파라미터 이름이 URL 자리표시자 이름과 반드시 일치해야 함
    return {"user_id": user_id, "post_id": post_id}

```

**422 에러 완전 해부 —** **`/items/abc`** **요청 시**

```
{
  "detail": [
    {
      "type": "int_parsing",         ← 에러 종류: 정수 파싱 실패
      "loc": ["path", "item_id"],    ← 위치: path 파라미터의 item_id
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "abc",                ← 실제로 들어온 값
      "url": "<https://errors.pydantic.dev/>..."   ← 상세 문서 링크
    }
  ]
}

```

> 💡 **422 읽는 순서**: `loc[1]`(어느 파라미터?) → `msg`(왜 거절?) → `input`(무엇을 넣었나?)
>  이 세 가지만 보면 원인과 해결책이 보입니다.

**타입별 자동 검증 동작**

| 타입 힌트 통과 예시 거절 예시 자동 변환  |                                                      |                  |                   |
| ------------------------ | ---------------------------------------------------- | ---------------- | ----------------- |
| `int`                    | `42`, `"42"`                                         | `"abc"`, `"3.5"` | `"42"` → `42` ✅   |
| `str`                    | 모든 값                                                 | (없음)             | —                 |
| `float`                  | `3.14`, `"3.14"`, `"42"`                             | `"abc"`          | `"42"` → `42.0` ✅ |
| `bool`                   | `true`, `1`, `yes`, `on` / `false`, `0`, `no`, `off` | `"maybe"`        | `"1"` → `True` ✅  |

> ℹ️ **`str`** **타입은 항상 통과합니다.** URL로 들어온 값은 원래 문자열이므로, `str` 타입 힌트는 추가 검증 없이 그대로 받습니다. 특정 값만 허용하려면 Day 3에서 배운 `Literal["A", "B", "C"]` 또는 `Enum`을 씁니다.

> 💡 **핵심**: 경로 파라미터는 건물 호수 표지판과 같습니다. `/users/42`에서 `42`는 "42호 입주자"를 특정하는 필수 식별자로, 없으면 `/users/`라는 전혀 다른 주소가 됩니다. `user_id: int` 타입 힌트 하나로 FastAPI가 문자열 "42"를 정수 42로 자동 변환하고, "abc"처럼 변환 불가한 값은 422와 함께 `detail[0]["loc"]`·`msg`·`input`이 담긴 진단서를 반환합니다. 단 `str` 타입은 모든 값이 통과하므로, 특정 패턴만 허용하려면 `Path(pattern=r"^EMP\d{3}$")` 또는 `Literal`을 써야 합니다.

---

### 💡 **경로 파라미터 핵심 요약**

- `@router.get("/items/{item_id}")` — 중괄호가 경로 파라미터 자리표시자
- 함수 파라미터 이름이 자리표시자 이름과 반드시 일치해야 함
- 타입 힌트가 자동 변환 + 검증 역할: `"42"` → `42`, `"abc"` → 422
- 422 응답의 `loc[1]`(파라미터명), `msg`(이유), `input`(받은 값) 순으로 읽기

---

## 7-3 | 3. 쿼리 파라미터 — URL 뒤에 붙이는 선택적 조건

### 핵심 개념

쿼리 파라미터는 URL 끝에 `?key=value` 형태로 붙습니다. 여러 개를 쓸 때는 `&`로 연결합니다. 경로 파라미터와 달리 **선택적으로 사용**할 수 있고, 검색 조건·필터·페이지 번호처럼 **조건이나 옵션**을 전달할 때 적합합니다.

### 상세 설명

```
# ── 쿼리 파라미터 기본 ──────────────────────────────────────────────────────
@router.get("/search")
async def search(keyword: str, limit: int = 10):
# keyword: str      — 기본값 없음 → 필수 쿼리 파라미터
# limit: int = 10   — 기본값 있음 → 선택 쿼리 파라미터 (생략하면 10 사용)

    # GET /search?keyword=AI&limit=5 → keyword="AI", limit=5           ✅
    # GET /search?keyword=AI         → keyword="AI", limit=10 (기본값)  ✅
    # GET /search                    → 422 (keyword 필수, 기본값 없음)   ❌
    # GET /search?keyword=AI&limit=x → 422 (limit이 int가 아님)         ❌
    return {"keyword": keyword, "limit": limit}

# ── bool 타입 쿼리 파라미터 — 다양한 표현을 자동 변환 ──────────────────────
@router.get("/users/{user_id}")
async def get_user(user_id: int, active: bool = True):
    # bool 타입은 여러 표현을 자동으로 True / False 로 변환합니다
    #
    # True  로 변환되는 값: ?active=true  ?active=1  ?active=yes  ?active=on
    # False 로 변환되는 값: ?active=false ?active=0  ?active=no   ?active=off
    #
    # GET /users/123              → user_id=123, active=True   (기본값)  ✅
    # GET /users/123?active=false → user_id=123, active=False            ✅
    # GET /users/123?active=0     → user_id=123, active=False (0 → False) ✅
    # GET /users/123?active=xyz   → 422 (bool 변환 불가)                  ❌
    return {"user_id": user_id, "active": active}
    # 예상 응답 (/users/123): {"user_id": 123, "active": true}

# ── Optional 쿼리 파라미터 — 없어도 되는 값 ────────────────────────────────
from typing import Optional   # 또는 파이썬 3.10+에서는 str | None

@router.get("/items")
async def list_items(
    category: Optional[str] = None,   # None이 기본값 → 없어도 됨
    min_price: Optional[int] = None,  # 없으면 None → 코드에서 분기 처리
):
    # GET /items                          → category=None, min_price=None
    # GET /items?category=food            → category="food", min_price=None
    # GET /items?category=food&min_price=5 → category="food", min_price=5
    result = {}
    if category:
        result["category"] = category     # None이 아닐 때만 필터 적용
    if min_price is not None:
        result["min_price"] = min_price
    return result

```

**httpx에서 쿼리 파라미터 전달하는 방법**

```
import httpx

# 방법 1: URL에 직접 문자열로 작성
r = httpx.get("<http://localhost:8000/search?keyword=AI&limit=5>")

# 방법 2: params 딕셔너리 (권장 — URL 인코딩 자동 처리)
r = httpx.get("<http://localhost:8000/search>", params={"keyword": "AI", "limit": 5})
# 한국어도 자동 URL 인코딩: {"keyword": "인공지능"} → ?keyword=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5

# 두 방법의 결과는 동일 — params 딕셔너리 방식이 오타·인코딩 오류가 없어 권장
print(r.url)   # <http://localhost:8000/search?keyword=AI&limit=5> 확인 가능

```

> 💡 **핵심**: 쿼리 파라미터는 포털 사이트 검색 필터와 같습니다. `google.com/search?q=FastAPI&num=10`처럼 기본 URL에 `?`로 조건을 덧붙입니다. FastAPI에서 기본값 없음(`keyword: str`)은 필수, 기본값 있음(`limit: int = 10`)은 선택, `Optional[str] = None`은 생략 가능입니다. `bool` 타입은 `true/1/yes/on` → `True`, `false/0/no/off` → `False`를 모두 수용합니다. httpx에서는 `params={"keyword": "AI"}` 딕셔너리로 전달하면 한국어 URL 인코딩이 자동 처리됩니다. 단 `str` 타입은 항상 통과하므로, 범위·길이 제약이 필요하면 `Query(ge=1, max_length=50)`을 써야 합니다.

---

### 💡 **쿼리 파라미터 핵심 요약**

- 기본값 없음(`keyword: str`) → 필수 쿼리 파라미터 · 누락 시 422
- 기본값 있음(`limit: int = 10`) → 선택 쿼리 파라미터 · 생략 가능
- `Optional[str] = None` → "있어도 되고 없어도 되는" 쿼리 파라미터
- `bool` 타입: `true/1/yes/on` → True, `false/0/no/off` → False 자동 변환
- httpx에서는 `params={}` 딕셔너리로 전달하면 URL 인코딩이 자동 처리됨

---

### 🔥 **더 알아보기 —** **`Query()`** **로 검증 세밀하게 제어하기**

타입 힌트 대신 `Query()` 를 쓰면 범위·길이·정규식까지 제약을 걸 수 있습니다.

```
from fastapi import Query

@router.get("/products")
async def list_products(
    page: int  = Query(default=1, ge=1,          description="페이지 번호 (1 이상)"),
    size: int  = Query(default=10, ge=1, le=100, description="페이지 크기 (1~100)"),
    q:    str  = Query(default=None, max_length=50, description="검색어 (50자 이내)"),
):
    # /products?page=0   → 422 (ge=1 위반 — 1 이상이어야 함)
    # /products?size=200 → 422 (le=100 위반 — 100 이하여야 함)
    return {"page": page, "size": size, "q": q}

```

`Query()` 주요 옵션: `ge`(이상), `gt`(초과), `le`(이하), `lt`(미만), `min_length`, `max_length`, `regex`, `description`(Swagger 설명)

---

## 7-3 | 4. 바디 파라미터

### 핵심 개념

바디 파라미터는 요청 **본문(Body)** 에 JSON 형태로 전달됩니다. URL에는 나타나지 않습니다. 채팅 메시지처럼 **길거나 복잡한 데이터**, 또는 **민감한 데이터**를 전달할 때 사용합니다. FastAPI에서 바디 파라미터는 Pydantic `BaseModel`로 정의합니다.

### 상세 설명

```
# 오늘(7-3)의 기초 버전: message를 쿼리 파라미터로 전달
POST /chat/?message=안녕하세요&session_id=s1

# Day 8에서 업그레이드: Pydantic BaseModel로 요청 본문에 전달
POST /chat/
Content-Type: application/json

{
  "message": "안녕하세요",
  "session_id": "s1",
  "temperature": 0.7
}

```

쿼리 파라미터 방식의 한계:

- URL 길이 제한 (브라우저별 다르지만 보통 2,048자)
- URL에 메시지 내용이 노출 (로그에 남을 수 있음)
- 복잡한 중첩 구조를 표현 불가

Pydantic BaseModel 방식의 장점:

- 길이 제한 없음
- URL에 내용 노출 없음 (HTTPS 암호화 대상)
- `field_name: List[str]`, `nested: Dict[str, Any]` 같은 복잡한 구조 가능
- 타입 힌트 + Field(description=, min\_length=, max\_length=) 로 세밀한 검증

> ℹ️ **미리보기**: 오늘 만든 `GET /chat/?message=...` 는 내일 아래로 바뀝니다.
>
> ```
> # Pydantic BaseModel로 업그레이드
> from app.schemas.chat import ChatRequest, ChatResponse
>
> @router.post("/", response_model=ChatResponse)
> async def chat_endpoint(
>     request: ChatRequest,        # ← 이 줄만으로 본문에서 자동 파싱·검증
>     llm = Depends(get_llm),
> ):
>     ...
>
> ```
>
> 오늘 경로·쿼리 파라미터를 충분히 익히면 내일 Pydantic BaseModel이 훨씬 자연스럽게 느껴집니다.

---

### 💡 **바디 파라미터 핵심 요약**

- 바디 파라미터 = 요청 본문 (JSON) — URL에 나타나지 않음
- 긴 텍스트·복잡한 구조·민감한 데이터에 적합
- FastAPI에서 Pydantic `BaseModel`로 정의 → Day 3 `EmailSummary`와 동일 문법
- **오늘 배운 경로·쿼리 파라미터가 Day 8 바디 파라미터의 기초**

---

## 7-3 | 5. 경로 vs 쿼리 vs 바디 — 실전 판단 기준

```
질문 1. URL로 특정 리소스를 가리키는 필수값인가?
          → YES → 경로 파라미터  /users/{user_id}

질문 2. 필터·정렬·페이지 같은 조건값인가? 선택적인가?
          → YES → 쿼리 파라미터  /search?keyword=AI&page=2

질문 3. 복잡한 구조이거나 길거나 민감한 데이터인가?
          → YES → 바디 파라미터  POST /chat/ + JSON body

```

**실전 예시 — LLM 채팅 서비스**

| 기능 파라미터 종류 URL / 본문  |    |                                                           |
| -------------------- | -- | --------------------------------------------------------- |
| 특정 대화 조회             | 경로 | `GET /conversations/42`                                   |
| 대화 목록 (최근 10개)       | 쿼리 | `GET /conversations?limit=10`                             |
| 채팅 메시지 전송            | 바디 | `POST /chat/` + `{"message": "...", "session_id": "..."}` |
| 메시지 삭제               | 경로 | `DELETE /messages/99`                                     |
| 스트리밍 응답              | 바디 | `POST /chat/stream` + `{"message": "..."}`                |

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  경로 파라미터 `GET /items/{item_id}` 를 만들고 정상(200)·오류(422) 모두 확인한다
- [ ]  쿼리 파라미터 `GET /search` 를 만들고 필수값 누락 422 를 의도적으로 발생시킨다
- [ ]  422 응답 JSON의 `loc`, `msg`, `input` 세 필드를 직접 읽는다

#### 🔰 기본 실습 — 단계별 가이드

📖 강의 연계: Day 7 실습 노트북 → 셀 06\~13 (경로·쿼리 파라미터 테스트)

**Step 1** `app/routers/items.py` 파일 생성

**Step 2** 경로 파라미터 `GET /items/{item_id}` 작성 (`item_id: int`)

**Step 3** 쿼리 파라미터 `GET /search` 작성 (`keyword: str`, `limit: int = 10`)

**Step 4** `app/main.py` 에 `items` 라우터 등록:

```
from app.routers import items
app.include_router(items.router, tags=["Items Practice"])

```

**Step 5** `/docs`에서 두 엔드포인트 테스트 — 정상 요청 + 422 에러 각각 확인

**Step 6** 422 응답 JSON에서 `loc`와 `msg` 필드 찾아보기

#### ⭐ 심화 실습

```
# 심화: Query()로 파라미터에 범위·길이 제약 추가
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

@router.get("/products")
async def list_products(
    page: int = Query(default=1, ge=1,
                      description="페이지 번호 (1 이상)"),
    size: int = Query(default=10, ge=1, le=100,
                      description="페이지 크기 (1~100)"),
    q: Optional[str] = Query(default=None, max_length=50,
                             description="검색어 (최대 50자)"),
):
    """
    Query() 검증 확인:
    /products?page=0   → 422 (ge=1 위반)
    /products?size=200 → 422 (le=100 위반)
    /products?q=가나다...51자 → 422 (max_length=50 위반)
    """
    return {"page": page, "size": size, "q": q}

```

⭐ **추가 도전**: `/docs`에서 `Query()` 에 설정한 `description`이 파라미터 설명으로 표시되는 것을 확인하세요. `ge`, `le` 제약을 위반하는 값을 Try it out에서 직접 입력해 422 응답을 확인하세요.

---

---

# 📦 모듈 7-4 · devcontainer 개요

| 항목 내용       |                                                                       |
| ----------- | --------------------------------------------------------------------- |
| **모듈 목표**   | devcontainer 개념을 이해하고, 팀 리포에 `.devcontainer/devcontainer.json`을       |
| 적용할 준비를 마친다 |                                                                       |
| **선수 지식**   | VS Code Remote Containers 확장 설치, Docker Desktop 설치 (선수 조건 — 아래 ⚠️ 참조) |
| **난이도**     | 🔰 기본                                                                 |

---

---

> ⚠️ **사전 조건 — Docker Desktop이 설치되어 있어야 합니다**
>
> devcontainer는 Docker 위에서 동작합니다. Docker Desktop이 없으면 VS Code에서 "Reopen in Container" 버튼이 나타나지 않습니다.
>
> ```
> # 설치 여부 확인 (터미널)
> docker --version
> # Docker Desktop 24.x.x 같은 버전이 출력되면 준비 완료
> # command not found 가 나오면 → <https://www.docker.com/products/docker-desktop> 에서 설치
>
> ```
>
> Docker Desktop 미설치 상태라면 이 모듈의 실습은 7-P 팀 블록에서 진행하세요.

---

### 📚 강의 교안

#### 왜 배우는가

팀 프로젝트가 시작되면 “제 컴퓨터에서는 되는데요” 문제가 반드시 발생합니다. 팀원 4명이 Python 버전, 패키지 버전, OS가 다르면 환경 차이로 인한 디버깅에 하루를 날릴 수 있습니다. devcontainer는 이 문제를 “팀 개발 밀키트”로 해결합니다.

## 7-4 | 1. "제 컴퓨터에서는 되는데요" — 환경 불일치 문제

### 핵심 개념

팀 프로젝트에서 가장 자주 듣는 말이 있습니다. **"제 컴퓨터에서는 잘 되는데요."** 이것은 실력 문제가 아니라 **환경 불일치** 문제입니다. 팀원 4명이 서로 다른 Python 버전, 패키지 버전, 운영체제를 사용하면 동일한 코드도 다르게 동작합니다. devcontainer는 이 문제를 **"모든 팀원이 완전히 동일한 컨테이너 안에서 개발한다"** 는 방식으로 해결합니다.

### 상세 설명

**팀원 4명이 사용하는 실제 환경 차이 — 흔한 사례**

| 팀원 A 팀원 B 팀원 C 팀원 D  |          |            |              |                 |
| -------------------- | -------- | ---------- | ------------ | --------------- |
| OS                   | macOS 14 | Windows 11 | Ubuntu 22.04 | macOS 13        |
| Python               | 3.12.1   | 3.10.9     | 3.11.4       | 3.11.0          |
| langchain            | 0.3.7    | 0.3.4      | 0.3.7        | 0.2.16          |
| pydantic             | v2.5     | v2.3       | v2.5         | **v1.10** ← 충돌! |
| 터미널                  | zsh      | PowerShell | bash         | zsh             |

Pydantic v1과 v2는 문법이 달라서 같은 코드가 한 컴퓨터에서는 돌고 다른 곳에서는 `ImportError`가 납니다. 이 차이를 맞추는 데 팀 전체가 오후를 날린 경험이 이 과정 수강생 중에도 반드시 있을 것입니다.

**devcontainer가 이 문제를 해결하는 방법**

```
devcontainer.json 파일 하나로 정의:
  - Python 버전: 3.11  (고정)
  - 패키지: requirements.txt 기준  (고정)
  - VS Code 확장: ms-python.python 등  (고정)
  - 포트 포워딩: 8000번  (자동)

→ 팀원 누가 열어도 → 동일한 컨테이너 → 동일한 결과

```

**로컬 venv vs devcontainer — 언제 무엇을 쓰는가**

| 로컬 venv devcontainer  |                        |                         |
| --------------------- | ---------------------- | ----------------------- |
| 설정 속도                 | ⚡ 즉시                   | 🐢 첫 빌드 3\~5분           |
| 환경 보장                 | △ 팀원마다 다를 수 있음         | ✅ 완전 동일                 |
| OS 의존성                | 있음 (Windows/Mac 명령 다름) | ❌ 없음 (컨테이너 안은 항상 Linux) |
| 추가 도구                 | Docker 불필요             | Docker Desktop 필요       |
| 재현성                   | 팀원 수동 맞추기 필요           | 파일 하나로 자동               |
| **이 과정 추천**           | 1주차 개인 실습 ✅            | **2주차 팀 프로젝트 ✅**        |

> 💡 **핵심**: devcontainer는 팀 개발 밀키트와 같습니다. `devcontainer.json` 파일 하나에 Python 3.11·`requirements.txt` 패키지·VS Code 확장을 명시하면, 누가 열어도 완전히 동일한 컨테이너 환경이 만들어집니다 — 온라인 게임 서버가 특정 클라이언트 버전만 허용하듯, "팀 표준 버전"을 고정합니다. 1주차에 개인이 만든 코드를 팀 리포에 올리는 지금 도입하는 것이 최적 타이밍입니다. 단 처음 빌드 시 이미지 다운로드(약 1GB)로 3\~5분이 소요되며, 팀원이 자발적으로 열어야 한다는 점에서 강제 적용 도구는 아닙니다 — 이후 재빌드는 캐시 덕분에 30초 내로 완료됩니다.

---

### 💡 **환경 불일치 문제 핵심 요약**

- 팀 프로젝트에서 "제 컴퓨터에서는 되는데요"의 원인 = 환경 불일치
- devcontainer = `devcontainer.json` 파일 하나로 팀 전체 환경을 컨테이너로 통일
- **지금 이 시점(팀 리포 시작)** 이 devcontainer 도입의 최적 타이밍
- Docker Desktop 필수 — 없으면 7-P 팀 블록에서 페어로 진행

---

### 🔥 **더 알아보기 — Docker 컨테이너 vs 가상 머신(VM)**

devcontainer는 Docker **컨테이너** 위에서 동작합니다. VM과의 차이를 이해하면 왜 빠른지 알 수 있습니다.

| 가상 머신(VM) Docker 컨테이너  |              |              |
| ---------------------- | ------------ | ------------ |
| OS                     | 게스트 OS 전체 포함 | 호스트 OS 커널 공유 |
| 크기                     | 수 GB         | 수십\~수백 MB    |
| 시작 시간                  | 분 단위         | 초 단위         |
| 격리 수준                  | 완전 격리        | 프로세스 수준 격리   |

devcontainer가 VM보다 빠른 이유는 OS 전체를 새로 띄우지 않고 호스트 OS의 커널을 공유하기 때문입니다. `docker --version`이 설치된 Docker Desktop이 이 모든 것을 관리합니다.

---

## 7-4 | 2. devcontainer.json — 개발 환경 설계도

### 핵심 개념

`.devcontainer/devcontainer.json` 파일이 팀 개발 환경의 **설계도**입니다. 이 파일을 팀 리포에 커밋하면 모든 팀원이 동일한 설계도로 컨테이너를 빌드합니다.

### 상세 설명

**기본 설정 — 줄별 완전 해설**

```
// .devcontainer/devcontainer.json
// 위치: 프로젝트 루트/.devcontainer/devcontainer.json
{
  "name": "lgcns-ai-service",
  // name: VS Code 창 좌측 하단에 표시되는 컨테이너 이름
  //       팀원들이 "맞는 컨테이너를 열었다"를 확인하는 용도

  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  // image: 사용할 Docker 이미지
  //   mcr.microsoft.com : Microsoft Container Registry
  //   devcontainers/python:3.11 : Microsoft가 관리하는 Python 3.11 개발 전용 이미지
  //   이 이미지에는 Python 3.11 + git + 공통 개발 도구가 사전 설치되어 있음
  //   ※ 첫 실행 시 이미지 다운로드(약 1GB) → 3~5분 소요, 이후는 캐시 사용

  "postCreateCommand": "pip install -r requirements.txt",
  // postCreateCommand: 컨테이너가 생성된 직후 자동으로 실행할 명령
  //   requirements.txt 기준으로 모든 패키지를 자동 설치
  //   → 팀원이 수동으로 pip install 할 필요 없음
  //   ※ 컨테이너 재생성 시마다 실행됨 (재빌드 시 포함)

  "remoteEnv": {
    "PYTHONPATH": "${containerWorkspaceFolder}"
    // remoteEnv: 컨테이너 안에서 설정할 환경변수
    // PYTHONPATH: Python이 모듈을 찾는 경로
    // ${containerWorkspaceFolder}: 컨테이너 안에서 프로젝트 루트 경로 (자동 치환)
    // → "from app.routers import chat" 같은 임포트가 컨테이너에서도 동작하게 함
  }
}

```

**빌드 흐름 — 처음 실행할 때 일어나는 일**

```
VS Code F1 → "Dev Containers: Reopen in Container" 클릭
    │
    ▼
Docker Hub에서 이미지 다운로드 (첫 실행만 ~ 3~5분)
    │
    ▼
컨테이너 생성 및 시작
    │
    ▼
postCreateCommand 실행: pip install -r requirements.txt
    │
    ▼
VS Code가 컨테이너 안으로 접속
    │
    ▼
VS Code 창 좌측 하단: [lgcns-ai-service] 표시 → 성공!

```

두 번째 실행부터는 이미지가 캐시되어 있어 10\~30초 만에 시작됩니다.

**`.env`** **파일 처리 — 팀 작업 흐름**

```
팀 리포에 포함되는 것:
  ✅ .devcontainer/devcontainer.json   (환경 설계도)
  ✅ .env.example                      (키 이름만, 실제 값 없음)
  ❌ .env                              (.gitignore에 포함 — 절대 커밋 금지)

각 팀원이 로컬에서 해야 하는 것:
  1. git clone 또는 git pull
  2. cp .env.example .env
  3. .env 파일에 실제 API 키 입력
  4. VS Code → "Reopen in Container"

```

```
# .env.example 예시 (팀 리포에 커밋)
OPENAI_API_KEY=sk-proj-여기에-실제-키를-넣으세요
LANGCHAIN_API_KEY=lsv2-여기에-실제-키를-넣으세요
LANGCHAIN_PROJECT=lgcns-agentic-ai
LANGCHAIN_TRACING_V2=true

```

> ⚠️ **컨테이너 안에서 API 키 설정**
>
> `.env` 파일은 `.gitignore`에 포함되어 Git에 올라가지 않습니다. 컨테이너를 열어도 `.env`는 자동 생성되지 않습니다. **팀원 각자가 컨테이너 터미널에서 직접 만들어야 합니다.**
>
> ```
> # 컨테이너 터미널에서
> cp .env.example .env          # 템플릿 복사
> code .env                     # VS Code로 열어 실제 키 입력
> # 저장 후 uvicorn 실행
>
> ```

---

### 💡 **devcontainer.json 핵심 요약**

- `"image"`: 어떤 Python 환경을 쓸지 — `python:3.11` 이미지가 표준
- `"postCreateCommand"`: 컨테이너 생성 후 자동 실행 — `pip install -r requirements.txt`로 패키지 자동 설치
- `"remoteEnv"`: 컨테이너 안 환경변수 — `PYTHONPATH` 설정으로 임포트 오류 방지
- `.env`는 컨테이너에 자동으로 복사되지 않음 — `.env.example` 복사 후 직접 입력
- 첫 빌드 3\~5분 → 이후 캐시로 30초 이내

---

### 🔥 **더 알아보기 — 심화 설정: VS Code 확장 자동 설치 + 포트 포워딩**

```
// 심화 설정 — 팀 표준 확장과 포트까지 고정
{
  "name": "lgcns-ai-service",
  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  "postCreateCommand": "pip install -r requirements.txt",

  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",          // Python 언어 지원
        "ms-python.vscode-pylance",  // 타입 힌트 자동완성
        "charliermarsh.ruff"         // 코드 품질 자동 검사 (import 정렬 등)
      ]
      // → 컨테이너를 열 때마다 이 확장이 자동으로 설치됨
      // 팀원이 직접 설치하지 않아도 됨
    }
  },

  "forwardPorts": [8000],
  // uvicorn이 8000번 포트에서 실행될 때
  // 컨테이너 안의 8000번 → 호스트 컴퓨터의 8000번으로 자동 연결
  // → 브라우저에서 <http://localhost:8000/docs> 가 정상 작동

  "remoteEnv": {
    "PYTHONPATH": "${containerWorkspaceFolder}"
  }
}

```

`postCreateCommand`를 여러 명령으로 확장하는 것도 가능합니다:

```
"postCreateCommand": "pip install -r requirements.txt && pre-commit install"

```

pre-commit을 함께 설치하면 커밋 전 코드 품질 검사가 자동화됩니다.

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  `.devcontainer/devcontainer.json` 기본 설정을 작성한다
- [ ]  VS Code에서 "Reopen in Container"를 실행하고 컨테이너 안에서 uvicorn이 동작하는지 확인한다 *(Docker 설치자에 한함)*

#### 🔰 기본 실습 — 단계별 가이드

📖 강의 연계: 7-P 팀 프로젝트 블록에서 팀 리포에 동일하게 적용

**Step 1** 프로젝트 루트에 `.devcontainer/` 폴더 생성

```
mkdir .devcontainer

```

**Step 2** `devcontainer.json` 작성 — 강의 교안의 기본 설정 복사

**Step 3** VS Code 명령 팔레트 실행

```
F1 (또는 Cmd+Shift+P) → "Dev Containers: Reopen in Container" 입력 후 선택

```

**Step 4** 빌드 완료 확인 — VS Code 좌측 하단에 `[lgcns-ai-service]` 표시 여부

**Step 5** 컨테이너 터미널에서 환경 검증

```
python --version        # Python 3.11.x 확인
pip list | grep fastapi # fastapi가 requirements.txt 기준 설치됐는지 확인
uvicorn app.main:app --reload  # 서버가 컨테이너 안에서 정상 실행되는지 확인

```

#### ⭐ 심화 실습

심화 설정(`customizations` + `forwardPorts`)을 추가하고 컨테이너를 **재빌드**한 뒤, VS Code 확장이 자동으로 설치되는 것을 확인하세요.

```
# 컨테이너 재빌드 방법 (설정 변경 후)
F1 → "Dev Containers: Rebuild Container" 선택
# 첫 빌드와 달리 이미지 캐시가 있어 1~2분 내 완료

```

⭐ **추가 도전**: `.env.example` 파일을 팀 리포에 추가하고, `cp .env.example .env` 후 컨테이너 안에서 실제 API 키로 LLM을 호출해보세요.

---

---

# 📦 모듈 7-5 · 가이드 실습 (개인·기본 미션)

| 항목 내용     |                                            |
| --------- | ------------------------------------------ |
| **모듈 목표** | 표준 구조 스켈레톤을 처음부터 만들어 `/docs`에서 엔드포인트를 확인한다 |
| **선수 지식** | 7-1\~7-4 전 내용, 특히 표준 디렉토리 구조               |
| **난이도**   | 🔰⭐ 기본+심화                                  |

---

### 📚 강의 교안

> ℹ️ 이 모듈은 실습 중심입니다. 강의 교안 섹션을 짧게 유지하고 실습 자료에 집중합니다.
>
> 막히는 부분은 AI 코파일럿(Claude Code / Cursor)을 활용하되, **완성된 코드의 흐름을 반드시 설명할 수 있어야 합니다**.

---

### 🏋️ 실습 자료

#### 기본 미션 — 표준 구조 스켈레톤 완성

```
오늘 완성해야 하는 것:
① 표준 구조 디렉토리 생성 (app/routers, services, schemas)
② app/main.py 작성 (라우터 등록)
③ GET /health → {"status": "ok"} 동작
④ GET /items/{item_id} 엔드포인트 1개 추가 (타입 검증 포함)
⑤ uvicorn 실행 후 /docs에서 성공 스크린샷

```

**제출**: `/docs` 화면 스크린샷을 슬랙 `#day7-제출`에 제출

#### ⭐ 심화 미션

```
# pydantic-settings로 환경변수 타입 안전 관리

# 수정 전 (Pydantic v2 DeprecationWarning 발생):
# class Settings(BaseSettings):
#     class Config:
#         env_file = ".env"

# 수정 후 — Pydantic v2 권장 방식:
from pydantic_settings import BaseSettings, SettingsConfigDict  # SettingsConfigDict 임포트 추가

class Settings(BaseSettings):
    openai_api_key: str
    langchain_api_key: str
    langchain_project: str = "lgcns-agentic-ai"
    debug: bool = False

    model_config = SettingsConfigDict(env_file='.env')   # class Config 대신 이걸 씁니다

settings = Settings()
# os.getenv("OPENAI_API_KEY") → settings.openai_api_key (타입 안전!)
# 잘못된 타입(.env에 debug=hello) → 시작 시 ValidationError로 즉시 알림

```

```
# pydantic-settings는 별도 설치 필요
pip install pydantic-settings

```

#### ✅ 미션 체크포인트

- [ ]  표준 디렉토리 구조 (`app/routers/`, `services/`, `schemas/`) 생성 완료
- [ ]  `uvicorn app.main:app --reload` 실행 성공
- [ ]  `/health` → `{"status": "ok"}` 응답 확인
- [ ]  `/docs` Swagger UI에서 등록된 엔드포인트 확인