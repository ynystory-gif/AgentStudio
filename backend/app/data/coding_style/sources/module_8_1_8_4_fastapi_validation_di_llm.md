# FastAPI 검증 · 의존성 주입 + LLM 연결

# 📋 오리엔테이션

---

## 핵심 메시지

### Pydantic + async + FastAPI 골격 = 완전한 LLM API

| 항목 내용     |                                                      |
| --------- | ---------------------------------------------------- |
| **학습 목표** | Pydantic 검증이 포함된 엔드포인트에서 Depends로 LLM을 주입해 비동기로 호출한다 |
| **오늘 완성** | 팀 서비스의 핵심 POST /chat 엔드포인트 (필수 요건 1·3번)              |

---

## 모듈 구성

| # 모듈명  |                        |
| ------ | ---------------------- |
| 8-1    | Pydantic v2 in FastAPI |
| 8-2    | 의존성 주입 Depends         |
| 8-3    | API 문서화 & 엔드포인트 완성     |
| 8-4    | 가이드 실습 (개인)            |

---

---

# 📦 모듈 8-1 · Pydantic v2 in FastAPI

| 항목 내용                    |                                                                        |
| ------------------------ | ---------------------------------------------------------------------- |
| **모듈 목표**                | FastAPI에서 Pydantic BaseModel로 요청·응답 스키마를 정의하고,                         |
| 자동 검증(422)이 동작하는 것을 확인한다 |                                                                        |
| **선수 지식**                | Day 3 Pydantic BaseModel·Field(description=…) 문법, Day 7 FastAPI 라우터 구조 |
| **난이도**                  | 🔰⭐ 기본+심화                                                              |

---

### 📚 강의 교안

#### 핵심 개념

FastAPI와 Pydantic은 **“서버 입구에 서 있는 자동 서류 심사관”** 쌍을 이룹니다. 엔드포인트 함수의 타입 힌트만 읽어 요청 데이터를 자동으로 검증하고, 규칙을 어긴 요청에는 코드 한 줄 없이 즉시 422 에러를 돌려보냅니다. 통과한 데이터만 함수 본문에 도달합니다.

#### 왜 배우는가

오늘 Pydantic은 **“같은 문법, 다른 역할”** 로 재등장합니다. LLM 출력이라는 불확실한 외부 데이터를 구조화하기 위해 썼다면, 오늘은 HTTP 클라이언트 요청이라는 또 다른 불확실한 외부 데이터를 검증합니다. `EmailSummary`가 `ChatRequest`로 이름만 바뀐 것이고, `Field(description=...)`도 동일하게 씁니다.

그렇다면 Pydantic 없이 FastAPI를 쓰면 어떤 일이 생길까요? `message`에 빈 문자열이 오거나, `temperature`에 음수가 오거나, 필드 자체가 누락되어도 서버는 그걸 그대로 LLM에 전달합니다. LLM이 엉뚱한 답변을 내놓거나, 빈 프롬프트를 처리하느라 비용이 낭비됩니다. Pydantic이 그 **문지기** 역할을 합니다.

**그리고 이 스키마가 설계서 ‘입출력 정의’의 코드 구현체입니다.** 설계서에서 “message: 사용자 입력(필수)”라고 결정한 것이, 오늘 `Field(min_length=1, description="사용자 입력 메시지")`로 코드화됩니다. 설계 → 코드의 직접적인 연결입니다.

#### 상세 설명

**FastAPI가 Pydantic을 사용하는 방식**

FastAPI는 엔드포인트 함수 정의를 분석해 Pydantic 모델을 자동으로 활성화합니다. 개발자가 해야 할 일은 타입 힌트 하나뿐입니다.

```
# 타입 힌트 하나만으로 FastAPI가 아래를 자동 처리합니다:
# 1. 요청 바디를 JSON으로 파싱
# 2. ChatRequest 스키마 규칙에 따라 모든 필드 검증
# 3. 검증 통과 → 함수 본문에 ChatRequest 인스턴스 전달
# 4. 검증 실패 → 자동으로 422 JSON 반환 (코드 추가 불필요)
async def chat_endpoint(request: ChatRequest):   # ← 타입 힌트 하나가 전부
    ...

```

**Day 3 복기 → 오늘 확장**

| 관점 LLM 출력 파싱 HTTP 요청 검증  |                                  |                                |
| ------------------------ | -------------------------------- | ------------------------------ |
| **데이터 출처**               | LLM (불확실한 AI 출력)                 | HTTP 클라이언트 (불확실한 외부 입력)        |
| **사용 위치**                | 체인 끝단 (`with_structured_output`) | 엔드포인트 입구 (타입 힌트)               |
| **검증 시점**                | LLM이 응답 생성 후                     | 요청이 함수에 도달하기 전                 |
| **실패 시**                 | `ValidationError` 예외             | FastAPI가 422 자동 반환             |
| **필드 접근**                | `result.sender`                  | `request.message`              |
| **공통점**                  | **같은 BaseModel 문법**              | **같은 Field(description=…) 사용** |

**422 에러 구조 해부**

422 에러는 단순한 “잘못된 요청”이 아닙니다. 어느 필드에서, 어떤 규칙을 위반했는지 상세하게 알려주는 **개발자를 위한 자동 디버그 보고서**입니다.

```
{
  "detail": [
    {                                    ← 오류 목록 배열 (여러 필드 오류도 한 번에 전달)
      "loc": ["body", "message"],        ← 오류 위치: 요청 바디의 message 필드
      "msg": "String should have at least 1 character",  ← 사람이 읽는 오류 설명
      "type": "string_too_short"         ← 코드가 읽는 유형 키 (자동 분기 처리 가능)
    }
  ]
}

```

> `loc` 배열을 보면 정확히 어떤 필드가 문제인지 알 수 있습니다. `type` 값으로 코드 내에서 오류 유형별로 다르게 처리할 수도 있습니다. 400(“뭔가 잘못됐음”)보다 훨씬 친절하고 구조화된 에러 형식입니다.

> 💡 **핵심**: FastAPI + Pydantic은 공항 수하물 검사대처럼 작동합니다.
>  짐(요청 데이터)이 들어오는 순간 규정(스키마)에 맞는지 자동으로 검사하고,
>  규정에 어긋나면 내용물(비즈니스 로직)을 보지도 않고 즉시 돌려보냅니다.
>  `loc`·`type`·`msg` 세 가지 필드가 담긴 422는 어느 짐이 왜 반려됐는지
>  정확히 알려주는 자동 반려 안내문입니다.
>  단 FastAPI는 “왜 이상한 데이터를 보냈는지”는 판단하지 않습니다 —
>  비즈니스 규칙(재고 확인, 권한 검사 등)은 별도로 구현해야 합니다.

#### 스키마 정의 — v1 (최소) → v2 (검증 추가)

```
# ────────────────────────────────────────────────────────────
# app/schemas/chat.py — v1: 가장 단순한 형태
# ────────────────────────────────────────────────────────────

# ① Pydantic의 핵심 클래스 불러오기
from pydantic import BaseModel   # 검증 기능이 내장된 데이터 클래스의 부모

class ChatRequestV1(BaseModel):
    # 타입 힌트만으로도 기본 검증이 동작합니다
    message: str               # str 아닌 타입(예: 숫자 42) 오면 → 422 자동 반환
    session_id: str = "default"    # 기본값 → 클라이언트가 보내지 않으면 "default" 사용

# ✅ v1이 막는 것: message 누락, 잘못된 타입 (예: 숫자·리스트)
# ❌ v1의 한계:
#    - 빈 문자열("")은 str이므로 통과 → LLM에게 빈 프롬프트가 전달됨
#    - 10만자 메시지도 통과 → 토큰 비용 폭탄 위험
#    → Field로 제약 조건을 추가하는 v2가 필요한 이유

```

```
# ────────────────────────────────────────────────────────────
# app/schemas/chat.py — v2: Field로 세밀한 제약 추가 (실제 서비스 수준)
# ────────────────────────────────────────────────────────────

# ① BaseModel에 Field를 추가로 임포트 — 제약 조건과 메타데이터를 함께 정의하는 함수
from pydantic import BaseModel, Field
# ※ Pydantic v2부터는 Optional[str] 대신 str | None 사용을 권장합니다
#   더 파이썬답고, Pydantic v2 내부 처리에도 최적화된 방식입니다

class ChatRequest(BaseModel):
    """클라이언트가 POST /chat/ 로 보내는 요청 형식.

    이 클래스가 8/7 설계서 3번(입출력 정의)의 코드 구현체입니다.
    설계 변경 시 이 클래스도 함께 수정해야 루브릭 '설계서 정합성' 20점을 지킬 수 있습니다.
    """

    # ② message 필드 — 가장 중요한 필수 입력값
    message: str = Field(
        min_length=1,                          # 빈 문자열("") 차단 — 빈 프롬프트 방지
        max_length=2000,                       # 과도한 입력 차단 — 토큰 비용 폭탄 방지
        description="사용자 입력 메시지",        # /docs Swagger UI에 표시되는 필드 설명
        examples=["오늘 회의 내용을 요약해줘"],   # /docs Try it out 기능의 예시 값
    )

    # ③ session_id 필드 — 대화 이력 추적용 (선택 입력)
    session_id: str = Field(
        default="default",                     # 클라이언트가 보내지 않으면 "default" 사용
        description="대화 세션 구분자 (LangSmith 트레이스 필터에 활용 가능)",
    )

    # ④ temperature 필드 — LLM 창의성 조절 (선택 입력)
    temperature: float = Field(
        default=0.7,                           # 기본값: 적당히 창의적인 중간값
        ge=0.0,   # ge = greater than or equal → 0.0 미만 값 차단 (음수 방지)
        le=2.0,   # le = less than or equal   → 2.0 초과 값 차단 (OpenAI 허용 범위 상한)
        description="LLM 창의성 조절 (0=매번 같은 답변, 2=매번 다른 창의적 답변)",
    )

class ChatResponse(BaseModel):
    """서버가 반환하는 응답 형식.

    response_model=ChatResponse 로 엔드포인트에 등록하면:
    - 내부 전용 필드(예: 원가 정보)가 자동으로 제거됩니다 (보안)
    - /docs에 응답 스키마가 자동 문서화됩니다
    """

    message: str          = Field(description="AI 응답 내용")
    session_id: str       = Field(description="요청과 동일한 세션 ID (대화 추적용)")
    model: str            = Field(description="사용된 LLM 모델명 (예: gpt-4o-mini)")
    tokens_used: int | None = Field(
        default=None,
        description="사용된 토큰 수 — 현재는 None 반환, 향후 비용 추적에 활용 예정"
    )

```

> 💡 **핵심**: `Field(min_length=1, max_length=2000, ge=0.0, le=2.0)` 한 줄이
>  “빈 문자열 거부 → 토큰 비용 폭탄 방지 → 음수 온도 차단”을 모두 처리합니다.
>  인간 개발자가 직접 `if not message: return 422` 조건을 쓸 필요가 없습니다.
>  단 Field는 **형식** 검증만 담당합니다 — “이 메시지가 실제로 의미 있는 요청인지”는
>  LLM이 판단해야 할 몫입니다.

#### 자동 검증 동작 확인

📓 **노트북 참조**: — Step 1 “POST /chat 정상 요청 확인”, Step 2 “422 검증 실패 재현”

아래 4가지 시나리오를 `/docs`에서 직접 실행해 422 응답 구조를 눈으로 확인하세요.

```
# ① ✅ 정상 요청 → 200 OK
# FastAPI가 받는 것: ChatRequest(message="안녕하세요", session_id="user-123", temperature=0.7)
POST /chat/
{"message": "안녕하세요", "session_id": "user-123"}
→ 200 OK

# ② ❌ message 빈 문자열 → min_length=1 위반
{"message": "", "session_id": "user-123"}
→ 422 Unprocessable Entity
{
  "detail": [
    {
      "loc": ["body", "message"],             # body 안의 message 필드
      "msg": "String should have at least 1 character",
      "type": "string_too_short"              # 코드에서 오류 유형별 분기 처리 가능
    }
  ]
}

# ③ ❌ temperature 범위 초과 → le=2.0 위반
{"message": "안녕", "temperature": 5.0}
→ 422
# detail[0].type: "less_than_equal"
# detail[0].msg:  "Input should be less than or equal to 2"

# ④ ❌ message 필드 자체 누락 → 필수 필드 없음
{}
→ 422
# detail[0].type: "missing"
# detail[0].msg:  "Field required"

```

> ⚠️ **Field(description=…)은 AI와 사람 두 독자를 위한 문서입니다**
>  Day 3에서 `Field(description=...)`이 LLM에게 “이 칸에 무엇을 넣어야 하는지” 알려주는 지시문이었다면, FastAPI에서는 `/docs` Swagger UI에서 사람 개발자가 읽는 API 설명서가 됩니다. 같은 코드 한 줄이 두 독자에게 동시에 봉사합니다.

> 💡 **핵심**: 위 4가지 시나리오가 보여주는 것처럼,
>  ①·②·③·④의 결과가 모두 **다른** **`type`** **값**(`string_too_short` / `less_than_equal` / `missing`)을 가집니다.
>  클라이언트는 이 `type`을 읽어 “빈 메시지입니다” / “온도 범위를 초과했습니다”처럼
>  사용자 친화적인 메시지로 번역할 수 있습니다.
>  단 FastAPI는 **동시에 여러 필드가 틀려도 모든 오류를 한 번에** 배열로 반환합니다 —
>  두 번 요청하지 않아도 됩니다.

---

### 💡 **핵심 요약**

- **Pydantic = 자동 문지기**: 타입 힌트 하나로 HTTP 요청 데이터를 자동 검증 — 코드 추가 없이 422 반환
- **422 = 개발자용 디버그 보고서**: `loc`(위치)·`type`(유형)·`msg`(설명)으로 어느 필드가 어떤 규칙을 위반했는지 정확히 알려줌
- **같은 문법, 다른 역할**: Day 3(LLM 출력 구조화)와 오늘(HTTP 입력 검증)에서 동일한 `BaseModel` + `Field(description=...)` 문법 재사용
- **설계서 3번 = 이 코드**: `ChatRequest`는 8/7 설계서의 입출력 정의를 코드로 구현한 것 — 설계 변경 시 이 파일도 함께 수정해야 루브릭 “설계서 정합성 20점” 달성 가능

---

### 🔥 **더 알아보기**

**Pydantic v2의 성능 혁신**: Pydantic v2(2023년 출시)는 핵심 검증 로직을 Rust로 재작성해 v1 대비 **5\~50배** 빠릅니다. 대용량 API에서 요청 처리 시간의 상당 부분을 차지하던 검증 오버헤드가 사실상 사라졌습니다. `pip install pydantic` 시 `pydantic-core` (Rust 바이너리)가 함께 설치되는 이유입니다.

**`model_config`****로 동작 세부 조정**: `ConfigDict`를 사용하면 스키마 동작을 더 세밀하게 제어할 수 있습니다.

```
from pydantic import ConfigDict

class StrictChatRequest(ChatRequest):
    model_config = ConfigDict(
        strict=True,      # 엄격 모드: int 필드에 "1" 문자열 허용 안 함 (기본은 자동 변환)
        frozen=True,      # 불변 객체: 인스턴스 생성 후 필드 변경 불가
        extra="forbid",   # 정의되지 않은 필드 포함 시 422 (보안 강화)
    )

```

**JSON Schema 자동 생성**: `ChatRequest.model_json_schema()`를 호출하면 OpenAPI 명세가 바로 생성됩니다. FastAPI가 `/docs` Swagger UI를 자동으로 만들어주는 원리가 바로 이것입니다. 팀 서비스의 API 문서를 외부에 공유할 때 이 스키마를 기반으로 하면 됩니다.

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  `app/schemas/chat.py` 파일에 `ChatRequest` / `ChatResponse`를 정의한다
- [ ]  빈 문자열을 보냈을 때 422가 반환됨을 /docs에서 확인한다

#### 🔰 기본 실습 — 단계별 가이드

**Step 1: schemas 폴더와 파일 생성**

```
mkdir -p app/schemas
touch app/schemas/__init__.py
touch app/schemas/chat.py

```

예상 결과: `app/schemas/chat.py` 파일이 생성됨

**Step 2: v2 스키마 코드 작성**
 위의 `ChatRequest`·`ChatResponse` 코드를 `chat.py`에 붙여넣기

**Step 3: 임시 테스트 (스키마만 독립 실행)**

```
# 터미널에서 빠른 확인
python -c "
from app.schemas.chat import ChatRequest
from pydantic import ValidationError
try:
    r = ChatRequest(message='')      # 빈 문자열 테스트
except ValidationError as e:
    print('검증 실패:', e.error_count(), '개 오류')
    print(e.errors()[0]['msg'])
# 예상 출력: 검증 실패: 1 개 오류
# 예상 출력: String should have at least 1 character
"

```

#### ⭐ 심화 실습

```
# 심화 ①: model_validator로 복합 검증
from pydantic import BaseModel, Field, model_validator

class AdvancedChatRequest(ChatRequest):
    """온도와 메시지 길이의 관계 검증"""
    @model_validator(mode="after")
    def check_temp_and_length(self):
        if self.temperature > 1.5 and len(self.message) < 10:
            raise ValueError("창의적 응답(temperature > 1.5)은 짧은 메시지에 비효율적입니다")
        return self

# 심화 ②: 중첩 모델
class ActionItem(BaseModel):
    assignee: str
    task: str
    deadline: str | None = None

class MeetingChatRequest(BaseModel):
    """회의록 분석 전용 요청 스키마"""
    content: str = Field(min_length=50, description="회의 내용 (최소 50자)")
    attendees: list[str] = Field(default=[], description="참석자 목록")
    extract_action_items: bool = Field(default=True)

```

---

---

# 📦 모듈 8-2 · 의존성 주입 Depends

| 항목 내용     |                                                                         |
| --------- | ----------------------------------------------------------------------- |
| **모듈 목표** | `Depends`로 LLM 클라이언트를 엔드포인트에 주입하고, async def 안에서 ainvoke로 호출한다          |
| **선수 지식** | Day 6 asyncio·ainvoke 문법, Day 7 APIRouter, 8-1 ChatRequest/ChatResponse |
| **난이도**   | 🔰⭐ 기본+심화                                                               |

---

### 📚 강의 교안

#### 핵심 개념

`Depends`는 **“FastAPI가 필요한 자원을 알아서 준비해주는 시스템”** 입니다. 엔드포인트 함수가 “나는 LLM이 필요해”라고 선언하면, FastAPI가 초기화·캐싱·에러 처리를 대신 담당합니다. 개발자는 LLM을 ’어떻게 만드는지’가 아니라 ’무엇을 쓸지’에만 집중할 수 있습니다.

이 패턴의 핵심은 **선언형(Declarative) 방식**입니다. “LLM 클라이언트를 이 함수 파라미터에 넣어주세요”라고 선언만 하면 FastAPI가 알아서 실행합니다. `@lru_cache()`와 결합하면 여러 엔드포인트가 하나의 인스턴스를 공유하는 **싱글턴 패턴**까지 완성됩니다.

#### 왜 배우는가

`ChatOpenAI()` 객체를 만들 때 내부적으로 OpenAI 서버에 연결을 준비하고 API 키를 로드합니다. 이것을 **모든 엔드포인트 함수 안에서 매 요청마다** 생성하면 어떻게 될까요? 동시 요청 100개가 들어오면 `ChatOpenAI()` 인스턴스를 100개 만듭니다. 불필요한 연결 생성, 메모리 낭비, 미묘한 설정 불일치가 생깁니다.

`Depends`는 이 문제를 두 가지로 해결합니다. 첫째, LLM 클라이언트를 **한 번만 만들어 전체가 공유**합니다(`@lru_cache`와 함께). 둘째, 엔드포인트가 “나는 LLM이 필요해”라고 선언만 하면 FastAPI가 알아서 가져다줍니다. 코드 재사용과 테스트 용이성(mock 교체)이 덤으로 따라옵니다.

#### 상세 설명

**Depends 없이 vs Depends 있이 — 두 패턴 비교**

| 관점 Depends 없이 (나쁜 예) Depends 있이 (좋은 예)  |                        |                                 |
| --------------------------------------- | ---------------------- | ------------------------------- |
| **LLM 초기화**                             | 요청마다 `ChatOpenAI()` 호출 | 최초 1회만, 이후 캐시 반환                |
| **인스턴스 수**                              | 동시 요청 100개 → 100개 생성   | 동시 요청 100개 → 1개 공유              |
| **설정 관리**                               | 각 함수마다 설정 반복           | `get_llm()` 한 곳에서 집중 관리         |
| **테스트**                                 | LLM 호출 없이 테스트 불가       | `dependency_overrides`로 mock 교체 |
| **코드 중복**                               | 엔드포인트마다 초기화 코드 복붙      | 한 번 선언, 어디서든 재사용                |

> 💡 **핵심**: `Depends(get_llm)`은 회사 공용 커피머신과 같습니다.
>  라떼·에스프레소·아메리카노(각 엔드포인트)가 모두 같은 머신(`ChatOpenAI` 인스턴스)을 쓰고,
>  머신을 교체할 때는 `get_llm()` 한 곳만 수정하면 됩니다.
>  `@lru_cache()`가 없으면 요청마다 새 머신을 사는 셈이 됩니다 —
>  단 커피머신과 달리 테스트 시에는 `dependency_overrides`로 목업(모조) 머신으로 바꿀 수 있습니다.

**`@lru_cache()`****가 하는 일**

`@lru_cache()`는 Python 표준 라이브러리의 메모이제이션 데코레이터입니다. 함수가 처음 호출되면 결과를 캐시에 저장하고, 이후 같은 인수로 호출되면 캐시에서 바로 반환합니다.

```
# lru_cache 동작 원리 (의사 코드)
호출 1: get_llm()  →  ChatOpenAI() 생성 → 캐시 저장 → 반환
호출 2: get_llm()  →  캐시 확인 → 캐시 HIT → 저장된 인스턴스 반환 (생성 없음)
호출 3: get_llm()  →  캐시 확인 → 캐시 HIT → 저장된 인스턴스 반환 (생성 없음)
# 결과: 얼마나 많은 요청이 와도 ChatOpenAI()는 딱 한 번만 만들어짐

```

> 💡 **핵심**: `@lru_cache()`는 함수 결과를 금고에 보관하는 것과 같습니다.
>  첫 방문자가 `get_llm()`을 호출할 때만 `ChatOpenAI()`를 생성해 금고에 넣고,
>  이후 방문자는 금고에서 꺼내 줍니다 — 다시 만들지 않습니다.
>  단 금고(캐시)는 프로세스 재시작 전까지 유지되므로,
>  API 키가 교체되면 `get_llm.cache_clear()`로 금고를 비워야 새 키가 반영됩니다.

**Depends 체인 — 의존성 안에 의존성**

Depends는 중첩이 가능합니다. `get_llm()`이 다른 의존성(`get_config()`)을 갖는 방식으로 체인을 구성할 수 있습니다. FastAPI가 전체 의존성 트리를 분석해 순서대로 실행합니다. *(코드 예시는 아래 🔥 더 알아보기 참조)*

#### Depends 구현

📓 **노트북 참조**: — Step 1 “POST /chat 정상 요청 확인” (`session_id` 변경으로 Depends 동작 확인)

```
# ────────────────────────────────────────────────────────────
# app/dependencies.py — LLM 클라이언트 의존성 정의
# ────────────────────────────────────────────────────────────

# ① 환경 변수 로드 — 반드시 ChatOpenAI 임포트보다 먼저!
from dotenv import load_dotenv
load_dotenv()   # .env에서 OPENAI_API_KEY 등 환경변수 로드
                # 이 줄이 없으면 ChatOpenAI() 초기화 시 401 Unauthorized 에러 발생

# ② 싱글턴 패턴을 위한 표준 라이브러리 데코레이터
from functools import lru_cache   # 함수 결과를 캐시 → 같은 인수면 재계산 없이 반환

# ③ LangChain OpenAI 연동 클라이언트
from langchain_openai import ChatOpenAI   # OPENAI_API_KEY 환경변수에서 자동 로드

@lru_cache()       # ← 이 데코레이터가 싱글턴을 만듭니다
def get_llm() -> ChatOpenAI:
    """LLM 클라이언트 팩토리 — 최초 1회 생성, 이후 캐시 반환.

    @lru_cache() 없이: 요청마다 ChatOpenAI() 생성 → 연결 낭비
    @lru_cache() 있으면: 최초 1회만 생성, 모든 요청이 같은 인스턴스 공유
    """
    return ChatOpenAI(
        model="gpt-4o-mini",   # 과정 표준 모델 — 빠른 응답, 저비용
        temperature=0,          # 일관된 출력 (기본값 0.7보다 낮춰 재현성 확보)
        # ✅ api_key는 환경변수(OPENAI_API_KEY)에서 자동 로드
        # ❌ 절대 금지: ChatOpenAI(api_key="sk-...")  ← 코드에 키 노출
    )

```

#### 라우터에서 Depends 사용

```
# ────────────────────────────────────────────────────────────
# app/routers/chat.py — Pydantic 검증 + Depends 주입 + ainvoke 호출
# ────────────────────────────────────────────────────────────

# ① FastAPI 라우터와 의존성 주입 도구
from fastapi import APIRouter, Depends

# ② LangChain 체인 구성 요소
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ③ 이 모듈에서 정의한 의존성과 스키마 임포트
from app.dependencies import get_llm
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()

@router.post("/", response_model=ChatResponse)   # response_model: 응답 스키마 강제 + 자동 문서화
async def chat_endpoint(
    request: ChatRequest,                          # ← Pydantic이 자동 검증 (8-1에서 배운 것)
    llm: ChatOpenAI = Depends(get_llm),            # ← Depends가 자동 주입 (오늘 배우는 것)
):
    """AI 채팅 엔드포인트 — 검증된 요청을 받아 LLM으로 처리 후 반환."""

    # ④ LCEL 체인 조립 — Prompt → LLM → Parser
    prompt = ChatPromptTemplate.from_messages([
        ("system", "유용한 AI 어시스턴트입니다."),  #TODO: 팀 설계서 프롬프트로 교체 (필수 요건 2번)
        ("human", "{message}"),
    ])
    chain = prompt | llm | StrOutputParser()
    # Day 7까지는 prompt | llm 이었고 result.content로 접근했으나,
    # 오늘부터 StrOutputParser()를 추가해 result가 바로 str로 반환됩니다.

    # ⑤ 비동기 호출 — async def 안에서는 반드시 ainvoke!
    result = await chain.ainvoke({"message": request.message})
    # result 타입: str (StrOutputParser 통과 후)
    # 예상 값: "안녕하세요! 무엇을 도와드릴까요?"

    # ⑥ 응답 객체 생성 — ChatResponse 스키마에 맞춰 반환
    return ChatResponse(
        message=result,
        session_id=request.session_id,   # 클라이언트가 보낸 session_id를 그대로 돌려줌
        model="gpt-4o-mini",
    )
    # 예상 JSON: {"message": "...", "session_id": "default", "model": "gpt-4o-mini", "tokens_used": null}

```

> 💡 **핵심**: `request: ChatRequest`와 `llm: ChatOpenAI = Depends(get_llm)` 두 파라미터가
>  오늘의 전부입니다. 전자는 Pydantic이 검증을, 후자는 Depends가 주입을 담당합니다.
>  함수 본문은 “검증된 데이터”와 “준비된 LLM”을 받아 비즈니스 로직만 처리합니다 —
>  초기화·검증·에러 처리를 직접 쓰지 않아도 됩니다.
>  단 `chain.ainvoke()`가 아닌 `chain.invoke()`를 쓰면 이벤트 루프를 점령해
>  이 장점이 모두 무너집니다.

#### ⚠️ 절대 규칙 재확인 — async def 안 동기 호출 금지

```
# ❌ 나쁜 예 — async def 안에서 동기 invoke → 이벤트 루프 전체 차단 → 서버 멈춤!
# 요청 1이 invoke()로 5초 기다리는 동안, 요청 2~100이 모두 응답 불가
@router.post("/bad")
async def bad_endpoint(request: ChatRequest, llm = Depends(get_llm)):
    result = llm.invoke(request.message)   # ← 동기 invoke — 이벤트 루프 점령!
    return {"message": result.content}

# ✅ 좋은 예 — ainvoke는 기다리는 동안 이벤트 루프를 다른 요청에 양보
# 요청 1이 ainvoke()로 5초 기다리는 동안, 요청 2~100도 동시에 처리됨
@router.post("/good")
async def good_endpoint(request: ChatRequest, llm = Depends(get_llm)):
    result = await llm.ainvoke(request.message)   # ← 비동기 ainvoke
    return {"message": result.content}

```

> ℹ️ **왜 이게 그렇게 중요한가?** FastAPI의 이벤트 루프는 단일 스레드입니다. `invoke()`처럼 LLM 응답을 기다리는 동기 작업이 루프를 점령하면, 그 3\~10초 동안 모든 다른 요청이 응답 불가 상태가 됩니다. 접속자 10명 중 1명이 동기 호출을 쓰면 나머지 9명도 피해를 봅니다.

---

### 💡 **핵심 요약**

- **Depends = 선언형 의존성**: “나는 LLM이 필요해”라고 선언만 하면 FastAPI가 초기화·주입·에러 처리를 대신 담당
- **`@lru_cache()`** **= 싱글턴 패턴**: 최초 1회만 `ChatOpenAI()` 생성, 이후 모든 요청이 같은 인스턴스 공유 — 연결 낭비 없음
- **async def → ainvoke 필수**: 동기 `invoke()`는 이벤트 루프를 점령해 서버 전체를 멈춤 — Day 6 규칙의 실전 적용
- **테스트 용이성**: `app.dependency_overrides[get_llm] = get_mock_llm`으로 실제 LLM 없이 테스트 가능

---

### 🔥 **더 알아보기**

**Depends 중첩 — 의존성 체인**: Depends 함수 안에 또 다른 Depends를 넣을 수 있습니다. FastAPI가 전체 의존성 트리를 분석해 올바른 순서로 실행합니다.

```
def get_config() -> dict:
    return {"max_tokens": 512, "language": "ko"}

def get_llm(config: dict = Depends(get_config)) -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", max_tokens=config["max_tokens"])

@router.post("/")
async def endpoint(llm = Depends(get_llm)):   # FastAPI: get_config() → get_llm() → endpoint() 순 실행
    ...

```

**pytest에서 dependency\_overrides 활용**: Depends의 진짜 강점은 테스트에서 드러납니다. 실제 API 키 없이도 LLM 동작을 흉내낸 mock으로 전체 엔드포인트를 테스트할 수 있습니다.

```
from unittest.mock import AsyncMock

def get_mock_llm():
    mock = AsyncMock()
    mock.ainvoke.return_value.content = "테스트 응답"   # StrOutputParser가 .content를 호출하므로 속성으로 설정
    return mock

# 테스트 파일에서
app.dependency_overrides[get_llm] = get_mock_llm
# 이제 POST /chat/ 호출 시 실제 OpenAI API 없이 "테스트 응답" 반환

```

**`lru_cache`** **초기화 문제**: 테스트 사이에 캐시를 비워야 할 때는 `get_llm.cache_clear()`를 호출합니다. 프로덕션에서 API 키를 교체한 뒤 재시작 없이 반영하려면 이 메서드가 필요합니다.

---

### 🏋️ 실습 자료

#### 🔰 기본 실습

**Step 1:** **`app/dependencies.py`** **생성**
 위 `get_llm()` 코드를 작성합니다.

**Step 2:** **`app/routers/chat.py`** **생성**
 위 `chat_endpoint` 코드를 작성합니다.

**Step 3:** **`app/main.py`****에 라우터 등록**

```
# app/main.py (Day 7에서 이어받기)
from app.routers import chat

app.include_router(chat.router, prefix="/chat", tags=["Chat"])

```

**Step 4: 서버 재시작 & 첫 호출**

```
uvicorn app.main:app --reload
curl -X POST <http://localhost:8000/chat/> \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요!"}'
# 예상 응답: {"message": "안녕하세요!...", "session_id": "default", "model": "gpt-4o-mini", "tokens_used": null}

```

#### ⭐ 심화 실습

```
# 심화 ①: 다중 의존성 — LLM + 사용자 설정 동시 주입
from fastapi import Depends, Header
from typing import Annotated

def get_user_context(x_user_id: Annotated[str | None, Header()] = None) -> dict:
    """요청 헤더에서 사용자 컨텍스트 추출"""
    return {"user_id": x_user_id or "anonymous"}

@router.post("/v2")
async def chat_v2(
    request: ChatRequest,
    llm: ChatOpenAI = Depends(get_llm),
    context: dict = Depends(get_user_context),   # 두 번째 의존성
):
    result = await llm.ainvoke(request.message)
    return {"message": result.content, "user": context["user_id"]}

# 심화 ②: 테스트용 mock 교체
# pytest에서 Depends를 override해 실제 LLM 없이 테스트
from unittest.mock import AsyncMock

def get_mock_llm():
    mock = AsyncMock()
    mock.ainvoke.return_value.content = "테스트 응답"
    return mock

# app.dependency_overrides[get_llm] = get_mock_llm

```

---

---

# 📦 모듈 8-3 · API 문서화 & 엔드포인트 완성

| 항목 내용         |                                                       |
| ------------- | ----------------------------------------------------- |
| **모듈 목표**     | FastAPI의 자동 문서화(Swagger UI)를 풍부하게 만들고, 전역 예외 핸들러를 추가해 |
| 안전한 API를 완성한다 |                                                       |
| **선수 지식**     | 8-1 ChatRequest·ChatResponse, 8-2 Depends·ainvoke     |
| **난이도**       | 🔰⭐ 기본+심화                                             |

---

### 📚 강의 교안

#### 핵심 개념

FastAPI의 자동 문서화는 **“이미 작성한 코드에서 무료로 얻는 선물”** 입니다. `summary`, `description`, `responses`, docstring을 제대로 채우면 `/docs`가 팀원·클라이언트·미래의 자신을 위한 사용 설명서가 됩니다. 별도의 문서 작업 없이 코드가 문서가 됩니다.

반면 **전역 예외 핸들러**는 “API의 안전망”입니다. 아무리 잘 만든 API도 LLM 장애, 타임아웃, 네트워크 에러는 피할 수 없습니다. 핸들러 없이는 Python 스택 트레이스가 클라이언트에 그대로 노출되어 내부 구조가 유출됩니다. 두 가지 모두 **프로덕션 레벨 API의 기본 요건**입니다.

#### 왜 배우는가

여러분이 만든 API를 팀원·클라이언트·미래의 자신이 사용합니다. 문서가 없으면 “이 필드에 뭘 넣어야 하지?”를 매번 코드를 뒤져야 합니다. FastAPI는 여러분이 이미 쓴 타입 힌트와 `Field(description=...)`에서 Swagger UI 문서를 **자동으로** 생성합니다. 오늘 잘 써둔 description 한 줄이 팀 협업 비용을 아낍니다.

그리고 아무리 잘 만든 API도 LLM 서버 장애, 타임아웃, 예상치 못한 에러가 납니다. 전역 예외 핸들러 없이는 클라이언트에 Python 스택 트레이스가 그대로 노출될 수 있습니다. 이를 안전하게 처리하는 것이 프로덕션 레벨 API의 기본입니다.

#### 상세 설명

**FastAPI 자동 문서화 파이프라인**

FastAPI는 코드를 읽어 OpenAPI 규격의 JSON을 생성하고, 그것을 Swagger UI로 렌더링합니다. 개발자가 작성한 코드 → JSON Schema → OpenAPI Spec → Swagger UI로 이어지는 완전 자동 파이프라인입니다.

```
코드 (타입 힌트·Field·docstring·@router 데코레이터)
    ↓ FastAPI가 분석
OpenAPI JSON  ← GET /openapi.json 으로 직접 확인 가능
    ↓ Swagger UI가 렌더링
/docs  ← 개발자용 인터랙티브 문서
/redoc ← 클라이언트·외부 배포용 읽기 전용 문서

```

> 💡 **핵심**: FastAPI 자동 문서는 코드에 센서를 달아둔 사용 설명서입니다.
>  `summary` / `description` / docstring / `Field(description=...)` 네 곳이 센서 역할을 해
>  코드를 수정하면 `/docs`가 자동으로 업데이트됩니다.
>  단 “좋은 `description`을 쓰는 것”은 자동이 아닙니다 —
>  `description="string"` 수준으로 채우면 자동 생성된 설명서도 쓸모없습니다.

**문서화 요소별 역할**

| 코드 요소 /docs에서 위치 역할      |                      |                |
| ------------------------ | -------------------- | -------------- |
| `summary="AI 채팅 응답"`     | 엔드포인트 제목 (굵게)        | 한 줄 요약         |
| `description="..."`      | 제목 아래 설명             | 상세 동작 설명       |
| `responses={422: {...}}` | “Responses” 섹션       | 실패 케이스 문서화     |
| 함수 docstring             | “Description” 섹션     | 마크다운 렌더링       |
| `Field(examples=[...])`  | “Schema” > “Example” | Try it out 기본값 |
| `Field(description=...)` | 각 필드 옆 `?` 아이콘       | 필드별 설명         |

**전역 예외 핸들러가 필요한 이유**

핸들러 없이 예외가 발생하면 FastAPI의 기본 동작은 500 에러 + Python 스택 트레이스입니다. 스택 트레이스에는 파일 경로, 코드 구조, 라이브러리 버전 등 내부 정보가 포함되어 **공격자에게 힌트**가 됩니다.

```
# ❌ 핸들러 없을 때 클라이언트에 노출되는 것 (보안 위험!)
Internal Server Error
  File "/app/routers/chat.py", line 47, in chat_endpoint
    result = await chain.ainvoke(...)
  File "/usr/local/lib/python3.11/langchain_core/...", line 123
    raise OpenAIError("API key expired")

# ✅ 핸들러 있을 때 클라이언트에 전달되는 것 (안전)
{"detail": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}

```

> 💡 **핵심**: 전역 예외 핸들러는 건물 외벽의 방화벽과 같습니다.
>  내부에서 불이 나도(LLM 타임아웃·API 키 만료·네트워크 에러)
>  외부 방문자에게는 “현재 점검 중”이라는 안내문만 보입니다.
>  스택 트레이스(파일 경로·라이브러리 버전)가 노출되면 공격자에게 지도가 생깁니다.
>  단 “현재 점검 중” 메시지만으로는 개발자가 원인을 알 수 없으므로
>  핸들러 안에서 반드시 서버 로그(`logging.error`)에 상세 오류를 기록해야 합니다.

#### API 문서 자동 생성 — docstring과 필드 설명이 /docs로

8-2에서 작성한 `chat_endpoint`에 아래 **세 가지를 추가**하면 문서화된 엔드포인트가 완성됩니다.

- `summary` · `description` · `responses={}` → 엔드포인트 수준 문서 (데코레이터에 추가)
- 함수 docstring → `/docs` “Description” 섹션에 마크다운으로 렌더링
- `TODO` 주석 → 팀 프롬프트 교체 포인트 명시 (필수 요건 2번과 직결)

📓 **노트북 참조**: — Step 1 “POST /chat 정상 요청 확인” (`/docs`에서 스키마·응답 구조 확인)

```
# ────────────────────────────────────────────────────────────
# app/routers/chat.py — 문서화가 풍부한 엔드포인트
# ────────────────────────────────────────────────────────────
from fastapi import APIRouter, Depends
from app.dependencies import get_llm
from app.schemas.chat import ChatRequest, ChatResponse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

router = APIRouter()

# ① @router.post() 데코레이터에 문서화 메타데이터 추가
@router.post(
    "/",
    response_model=ChatResponse,            # 응답 스키마 강제 + /docs 응답 예시 자동 생성
    summary="AI 채팅 응답",                  # /docs 엔드포인트 목록의 굵은 제목
    description="사용자 메시지에 대한 AI 응답을 반환합니다. LangSmith에 자동 기록됩니다.",
    responses={                              # 정상(200) 외의 응답 케이스 문서화
        422: {"description": "입력 검증 실패 (메시지 길이, 온도 범위 등)"},
        500: {"description": "LLM 호출 실패"},
    },
)
async def chat_endpoint(
    request: ChatRequest,
    llm = Depends(get_llm),
):
    # ② 함수 docstring → /docs "Description" 섹션에 마크다운으로 렌더링
    """
    ## 사용 예시
    - "이 이메일의 핵심 요청을 요약해줘"
    - "이 민원을 유형별로 분류해줘"
    - "다음 텍스트를 영어로 번역해줘"

    ## 응답 구조
    - **message**: AI의 답변 텍스트
    - **session_id**: 요청과 동일한 세션 ID (대화 추적용)
    - **model**: 사용된 모델명 (gpt-4o-mini)
    """
    # ③TODO: 팀 설계서 프롬프트로 교체 (하드코딩 금지 — 필수 요건 2번)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "유용한 AI 어시스턴트입니다."),   # ← 팀 시스템 프롬프트로 교체
        ("human", "{message}"),
    ])
    chain = prompt | llm | StrOutputParser()

    # ④ 반드시 ainvoke — async def 안 동기 invoke 금지 (8-2 핵심 규칙)
    result = await chain.ainvoke({"message": request.message})

    return ChatResponse(
        message=result,
        session_id=request.session_id,
        model="gpt-4o-mini",
    )

```

> ⚠️ **프롬프트 하드코딩 금지**: 위 예시의 `"유용한 AI 어시스턴트입니다."`는 임시 예시입니다. 팀 설계서의 시스템 프롬프트를 `ChatPromptTemplate`으로 작성해 교체하세요. 하드코딩 금지는 **필수 요건 2번**이며 Day 10 루브릭 “구조·설계 25점”에서 점검합니다.

#### 전역 예외 핸들러

```
# ────────────────────────────────────────────────────────────
# app/main.py — 전역 예외 핸들러 추가
# ────────────────────────────────────────────────────────────

# ① 예외 핸들러에 필요한 추가 임포트
from fastapi import FastAPI, Request         # Request: 핸들러에 요청 정보 전달
from fastapi.responses import JSONResponse   # 에러 응답을 JSON 형식으로 반환

app = FastAPI(title="팀 LLM 서비스", version="0.1.0")

# ② 전역 예외 핸들러 — Exception을 잡으면 모든 예상치 못한 에러를 처리
# ※ @app.exception_handler는 include_router() 전후 어디에 놓아도 동일하게 동작합니다
#   (미들웨어(@app.middleware)는 등록 순서가 중요하지만, 예외 핸들러는 무관합니다)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """LLM 타임아웃·API 키 만료·연결 오류 등 모든 예외를 500으로 통일.

    클라이언트에는 안전한 메시지만, 상세 오류는 서버 로그에만 기록합니다.
    """
    # ③ 실제 서비스에서는 여기에 로깅 추가 (Sentry, CloudWatch 등)
    # import logging
    # logging.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={"detail": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."},
        # ❌ 절대 금지: content={"detail": str(exc)}  ← 내부 구조·스택 트레이스 노출
        # ✅ 사용자에게는 안전한 메시지, 로그에만 상세 기록
    )

# ④ 라우터는 핸들러 등록 이후에 include해도 동일하게 동작합니다
from app.routers import health, chat
app.include_router(health.router)
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

```

> 💡 **핵심**: `@app.exception_handler(Exception)`은 모든 예외를 한 곳에서 잡는 그물입니다.
>  예외가 발생하면 이 핸들러가 항상 `{"detail": "서버 오류..."}` 형식을 반환하므로
>  클라이언트는 항상 같은 형식의 에러 응답을 기대할 수 있습니다.
>  단 너무 넓게 잡으면(모든 Exception) 404·422처럼 정상적인 에러도 잡힐 수 있습니다 —
>  HTTPException은 별도로 처리하거나 핸들러 안에서 유형을 분기하세요.

---

### 💡 **핵심 요약**

- **자동 문서화 파이프라인**: 타입 힌트·`Field(description=...)`·docstring → OpenAPI JSON → `/docs` Swagger UI — 코드가 곧 문서
- **description 품질 = 문서 품질**: 자동 생성되지만 내용은 개발자가 책임 — “이 API가 무엇을 하는지”를 팀원에게 설명한다는 마음으로 작성
- **`responses={}`** **= 실패 케이스 문서화**: 200뿐 아니라 422(검증 실패)·500(서버 오류)를 명시해야 완전한 계약서
- **전역 예외 핸들러 = 보안 + UX**: 스택 트레이스 노출 차단(보안) + 클라이언트에 일관된 에러 형식 제공(UX)
- **/docs 데모 = Day 10 발표의 핵심 도구**: curl이나 별도 클라이언트 없이 발표 당일 /docs에서 라이브 데모 가능

---

### 🔥 **더 알아보기**

**`/docs`** **vs** **`/redoc`** **vs** **`/openapi.json`**: FastAPI는 세 가지 문서 인터페이스를 기본 제공합니다. `/docs`는 Swagger UI로 직접 실행 가능, `/redoc`은 ReDoc으로 외부 공유용 읽기 전용, `/openapi.json`은 OpenAPI 규격의 raw JSON입니다. Postman이나 Insomnia에 이 JSON을 가져와 클라이언트 SDK를 자동 생성할 수 있습니다.

**커스텀 예외 클래스로 세분화**: 전역 핸들러는 모든 예외를 잡지만, 예외 유형별로 다른 응답을 보내고 싶을 때 `HTTPException`과 커스텀 핸들러를 조합합니다.

```
from openai import RateLimitError, AuthenticationError

@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    return JSONResponse(status_code=429,
        content={"detail": "API 요청 한도 초과. 잠시 후 재시도해주세요."})

@app.exception_handler(AuthenticationError)
async def auth_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(status_code=500,
        content={"detail": "서버 인증 오류. 관리자에게 문의해주세요."})
    # ※ 클라이언트에는 500으로 숨김 — API 키 문제를 외부에 알리지 않음

```

**`/docs`** **비활성화 (프로덕션)**: 실제 배포 환경에서는 `/docs`를 비활성화해 내부 API 구조를 숨깁니다.

```
# 프로덕션: docs_url=None, redoc_url=None
app = FastAPI(docs_url=None, redoc_url=None)
# 개발: 기본값(docs_url="/docs") 그대로 사용

```

---

### 🏋️ 실습 자료

#### 🔰 기본 실습

1. 8-2의 `chat_endpoint`에 `summary`, `description`, `responses={}` 파라미터 추가
2. docstring에 “## 사용 예시” 2가지 작성
3. `app/main.py`에 `global_exception_handler` 추가
4. 서버 재시작 후 `/docs`에서 문서가 풍부해진 것 확인

#### ⭐ 심화 실습

```
# 심화 ①: 요청 로깅 미들웨어
import time
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """모든 요청의 메서드·경로·처리 시간을 기록"""
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    print(f"[{request.method}]{request.url.path} →{response.status_code} ({elapsed:.3f}s)")
    return response
# 예상 출력: [POST] /chat/ → 200 (1.234s)

# 심화 ②: LLM 전용 예외 핸들러 (세분화)
from openai import RateLimitError, AuthenticationError

@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    return JSONResponse(
        status_code=429,
        content={"detail": "API 요청 한도 초과. 잠시 후 다시 시도해주세요."},
    )

```

---

---

# 📦 모듈 8-4 · 가이드 실습 (개인·기본 미션)

| 항목 내용     |                                                                      |
| --------- | -------------------------------------------------------------------- |
| **모듈 목표** | 검증·주입·비동기 호출이 모두 포함된 `POST /chat` 1개를 완성하고 /docs에서 200과 422를 모두 확인한다 |
| **선수 지식** | 8-1 스키마, 8-2 Depends, 8-3 문서화 코드                                     |
| **난이도**   | 🔰 기본 / ⭐ 심화                                                         |

---

### 🏋️ 실습 자료

> **이 시간의 목적**: 오늘 8시간에서 배운 Pydantic(8-1)·Depends(8-2)·문서화(8-3)를
>  **혼자서** 하나의 엔드포인트에 합쳐 완성하는 시간입니다.
>  Step 1\~4를 순서대로 통과하면 기본 미션 완료입니다.
>
> **성공 기준**: `/docs`에서 정상 요청(200 OK)과 검증 실패(422 Unprocessable Entity)를
>  직접 실행해 두 응답을 모두 눈으로 확인했습니까?

#### 🔰 기본 미션 — 단계별 가이드

> AI 코파일럿(Claude Code / Cursor) 사용 권장.
>  코드 암기가 아니라 **세 패턴이 하나의 엔드포인트에 합쳐지는 구조**를 이해하는 것이 목표입니다.

**완성 목표**

```
① ChatRequest / ChatResponse Pydantic 스키마 작성   ← 8-1 적용
② get_llm() Depends 함수 작성                       ← 8-2 적용
③ POST /chat 엔드포인트 (검증 + 주입 + ainvoke)     ← 8-1·8-2·8-3 통합
④ /docs에서 200과 422 모두 확인
⑤ LangSmith 트레이스 링크 제출

```

---

**Step 1: 파일 구조 확인**

```
# Day 7에서 만든 표준 구조에 오늘 파일 추가
tree app/
# 예상 출력:
# app/
# ├── __init__.py
# ├── main.py
# ├── dependencies.py    ← 오늘 추가 (get_llm)
# ├── routers/
# │   ├── __init__.py
# │   ├── health.py      ← Day 7에서 있음
# │   └── chat.py        ← 오늘 추가 (POST /chat)
# └── schemas/
#     ├── __init__.py
#     └── chat.py        ← 오늘 추가 (ChatRequest·ChatResponse)

```

> 💡 **파일이 없다면**: 8-1·8-2·8-3의 코드 예시를 참고해 하나씩 만드세요.
>  `schemas/chat.py` → `dependencies.py` → `routers/chat.py` → `main.py` 순서가 의존성상 가장 안전합니다.

---

**Step 2: 서버 실행 & 정상 요청 테스트**

```
# ① 서버 실행 (변경 시 자동 재시작)
uvicorn app.main:app --reload

# ② ✅ 정상 요청 — 200 기대
curl -X POST <http://localhost:8000/chat/> \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요!", "session_id": "test-1"}'

# 예상 응답 (AI 답변은 달라질 수 있음):
# {"message": "안녕하세요! 무엇을 도와드릴까요?",
#  "session_id": "test-1",
#  "model": "gpt-4o-mini",
#  "tokens_used": null}

```

> 💡 **자주 나오는 문제**
>
> | 증상 원인 해결                    |           |                                            |
> | --------------------------- | --------- | ------------------------------------------ |
> | `Connection refused`        | 서버 미실행    | `uvicorn app.main:app --reload` 실행         |
> | `404 Not Found`             | URL 경로 오타 | `/chat/` 끝 슬래시 확인, `main.py`에 라우터 등록 여부 확인 |
> | `401 Unauthorized`          | API 키 누락  | `.env` 파일에 `OPENAI_API_KEY` 있는지 확인         |
> | `500 Internal Server Error` | LLM 호출 실패 | 터미널 로그에서 Python 에러 확인                      |

---

**Step 3: 검증 실패(422) 테스트**

```
# ❌ 빈 메시지 — min_length=1 위반 → 422 기대
curl -X POST <http://localhost:8000/chat/> \
  -H "Content-Type: application/json" \
  -d '{"message": ""}'
# 예상 응답:
# {"detail": [{"loc": ["body", "message"],
#              "msg": "String should have at least 1 character",
#              "type": "string_too_short"}]}

# ❌ message 필드 누락 — Field required → 422 기대
curl -X POST <http://localhost:8000/chat/> \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test"}'
# 예상 응답:
# {"detail": [{"loc": ["body", "message"],
#              "msg": "Field required",
#              "type": "missing"}]}

```

> 💡 **422 응답을 읽는 법**`detail` 배열의 첫 번째 항목을 보세요.

- `"loc": ["body", "message"]` → 요청 바디의 message 필드에서 오류 발생
- `"type": "string_too_short"` → min\_length 규칙 위반
- `"msg"` → 사람이 읽는 설명 (클라이언트에게 그대로 보여줄 수 있음)

>

---

**Step 4: LangSmith 트레이스 확인 & 제출**

```
smith.langchain.com
  → 좌측 프로젝트 목록에서 lgcns-agentic-ai 선택
  → "Traces" 탭 → 오늘 날짜 호출 목록
  → 방금 보낸 요청 클릭
  → 우측 상단 링크 아이콘 클릭 → URL 복사
  → 슬랙 #day8-제출 채널에 링크 붙여넣기

```

> 💡 **트레이스에서 확인할 것들**

- **Input**: 내가 보낸 message가 정확히 들어갔는가?
- **Output**: AI가 반환한 전체 텍스트
- **Latency**: 응답까지 걸린 시간 (보통 1\~3초)
- **Tokens**: 입력·출력 토큰 수 (비용 계산 기준)
- **Chain 단계**: Prompt → ChatOpenAI → StrOutputParser 3단계가 보이는가?

>

#### ✅ 제출 기준

| 구분 제출물 확인 방법  |                                |                  |
| ------------- | ------------------------------ | ---------------- |
| 🔰 기본         | LangSmith 트레이스 링크              | 클릭 시 오늘 날짜 호출 확인 |
| 🔰 기본         | /docs 화면 스크린샷 (200 + 422 각 1장) | 스크린샷에 응답 body 포함 |

#### ⭐ 심화 실습

```
# 심화 ①: 전역 예외 핸들러 실전 확인
# app/main.py에 global_exception_handler 추가 후,
# 의도적으로 잘못된 API 키를 .env에 넣어 LLM 호출
# → 500 응답 JSON이 {"detail": "서버 오류..."} 형식인지 확인
# → 테스트 후 반드시 원래 키로 복원!

# 심화 ②: 요청 로깅 미들웨어 (8-3 심화 적용)
# @app.middleware("http") 로 log_requests 추가
# uvicorn 터미널에서 [POST] /chat/ → 200 (X.XXXs) 로그 확인

# 심화 ③: 팀 시스템 프롬프트 교체
# 임시 프롬프트 "유용한 AI 어시스턴트입니다." →
# 8/7 설계서의 시스템 프롬프트로 교체
# LangSmith에서 두 버전의 Input·Output 비교해 품질 차이 확인

```

---

> 🔥 **더 알아보기**
>
> **curl 대신 쓸 수 있는 도구들**: curl은 강력하지만 JSON 응답이 한 줄로 붙어 나와 읽기 어렵습니다. 아래 도구를 쓰면 더 편합니다.
>
> ```
> # httpie: curl보다 간결하고 색상 강조
> pip install httpie
> http POST :8000/chat/ message="안녕하세요" session_id="test-1"
>
> # curl에 jq 파이프: JSON 예쁘게 출력
> curl -s -X POST <http://localhost:8000/chat/> \
>   -H "Content-Type: application/json" \
>   -d '{"message": "안녕"}' | jq .
>
> ```
>
> **`/docs`****에서 두 번째 엔드포인트 추가하기**: 팀 서비스가 `/health`와 `/chat/` 외에 엔드포인트가 더 필요하다면, `routers/` 에 새 파일을 만들고 `main.py`에 `include_router()`만 추가하면 됩니다. 기존 코드는 건드리지 않아도 됩니다. 이것이 모듈식 구조의 핵심입니다.
>
> **LangSmith 필터로 내 호출만 보기**: 여러 팀원이 같은 프로젝트를 쓰면 트레이스가 섞입니다. `session_id`를 내 이름으로 설정하면 LangSmith 검색창에서 `session_id:내이름`으로 필터링할 수 있습니다.

---

---

### ✅ Day 8 최종 체크포인트

- [ ]  빈 message가 422로 거절된다
- [ ]  정상 요청이 LLM 응답 JSON을 반환한다
- [ ]  LLM 클라이언트를 Depends로 주입한다
- [ ]  `async def` 안에서 `ainvoke`만 사용한다