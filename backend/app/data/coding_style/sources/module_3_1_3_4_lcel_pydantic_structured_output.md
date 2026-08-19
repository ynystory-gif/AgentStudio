# LCEL과 Pydantic을 활용한 LLM 구조화 출력

# 📋 오리엔테이션

---

## 핵심 메시지

### LLM 출력을 코드가 다룰 수 있는 구조화된 데이터로 받습니다

| 항목          |                                                                                             |
| ----------- | ------------------------------------------------------------------------------------------- |
| **학습 목표**   | LCEL 파이프라인을 조립하고, TypedDict와 Pydantic BaseModel의 차이를 이해하며, Pydantic으로 LLM 출력을 구조화해 필드로 접근한다 |
| **실습 단위**   | **개인** — 마이 서비스 조각에 적용                                                                      |
| **오늘의 산출물** | 내 서비스 조각의 구조화 출력 Pydantic 모델 + LangSmith 링크                                                 |

---

## 모듈 구성

| 모듈명  |                                |
| ---- | ------------------------------ |
| 3-1  | Runnable & LCEL 파이프라인          |
| 3-2  | TypedDict & Pydantic BaseModel |
| 3-3  | with\_structured\_output       |
| 3-4  | 마이 서비스 조각 적용 실습                |

---

---

# 📦 모듈 3-1 · Runnable & LCEL 파이프라인

| 항목 내용     |                                               |
| --------- | --------------------------------------------- |
| **모듈 목표** | LCEL \`                                       |
| **선수 지식** | Day 2 ChatPromptTemplate, ChatOpenAI 기본 호출 경험 |
| **난이도**   | 🔰⭐ 기본+심화                                     |

---

### 📚 강의 교안

#### 왜 LCEL이 필요한가?

단계를 연결하는 문제를 보면 필요성이 명확해집니다. LLM 서비스는 보통 프롬프트 → 모델 → 출력 파싱의 3단계로 구성되는데, 이 단계를 직접 연결하면 반복 코드가 폭발적으로 늘어납니다.

```
# LCEL 없이 — 단계마다 변수를 직접 연결
prompt_result = template.format_messages(text=user_input)
model_result  = llm.invoke(prompt_result)
final_output  = parser.parse(model_result.content)

# 3단계 × 10개 체인 = 30줄의 반복 코드

```



```
# LCEL 있으면 — 파이프(|)로 한 번에 연결
chain  = template | llm | parser
result = chain.invoke({"text": user_input})
# 1줄로 완성!

```

**LCEL이 해결하는 문제 — 3가지 방식 비교**

| 방식 코드 형태 특징  |                                                     |                                    |
| ------------ | --------------------------------------------------- | ---------------------------------- |
| 중첩 호출        | `parser.invoke(llm.invoke(prompt.invoke(x)))`       | 오른쪽→왼쪽으로 읽어야 함, 디버깅 어려움            |
| 함수 정의        | `def run(x): return parser.invoke(llm.invoke(...))` | 재사용성 낮음, `stream`/`batch` 별도 구현 필요 |
| **LCEL**     | \`chain = prompt                                    | llm                                |

---

#### LCEL 비유

> 💡 **비유 ①: LCEL 파이프(****`|`****)는 “공장 컨베이어 벨트”입니다**
>
> 차체 → 도색 → 조립 처럼
>
> `prompt | model | parser`의 앞 단계 출력이 다음 단계 입력이 됩니다.
>
> **이 비유의 한계**: 컨베이어는 일렬이지만
>
> LCEL은 병렬(`RunnableParallel`)·분기(`RunnableBranch`)도 지원합니다.

> 💡 **비유 ②: Unix 파이프 명령어입니다** (개발자 대상)
>
> `cat file.txt | grep "키워드" | sort | uniq`
>
> 처럼 앞의 출력이 뒤의 입력이 됩니다.
>
> **이 비유의 한계**: Unix 파이프는 텍스트만,
>
> LCEL은 딕셔너리·객체·메시지 등 다양한 타입을 전달합니다.

---

#### 데이터가 어떻게 흐르는가?

### 3단계 변환 흐름

```
입력 dict → PromptTemplate → list[Message] → ChatOpenAI → AIMessage → StrOutputParser → str
                           ↑                           ↑                             ↑
                       (변환 1)                     (변환 2)                     (변환 3)

```

```
# type_flow.py — 각 단계에서 타입이 어떻게 바뀌는지 직접 확인
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()
llm    = ChatOpenAI(model="gpt-4o-mini", temperature=0)  # 추가
parser = StrOutputParser()                                # 추가

template = ChatPromptTemplate.from_messages([
    ("system", "요약 전문가입니다."),
    ("human", "다음을{length}줄로 요약:\n{text}")
])

# 단계별 타입 확인
input_dict = {"length": "3", "text": "긴 텍스트..."}
messages   = template.invoke(input_dict)   # -> list[Message]
ai_msg     = llm.invoke(messages)          # -> AIMessage
text_out   = parser.invoke(ai_msg)         # -> str

print(type(input_dict), "→", type(messages), "→", type(ai_msg), "→", type(text_out))
# 예상 출력: <class 'dict'> → <class 'list'> → <class 'langchain_core.messages.ai.AIMessage'> → <class 'str'>

```

---

#### LCEL 기본 체인 구현 (v1 → v2)

**v1 — 가장 단순한 형태: 단건 호출**

```
# lcel_v1.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()
llm    = ChatOpenAI(model="gpt-4o-mini", temperature=0)
parser = StrOutputParser()   # AIMessage → str 변환기

prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 요약 전문가입니다."),
    ("human", "다음 텍스트를{length}줄로 요약해:\n\n{text}")
])

# 파이프로 연결 — 이게 전부입니다!
chain = prompt | llm | parser

# 단건 호출
result = chain.invoke({"length": "3", "text": "긴 텍스트를 여기에..."})
print(type(result))   # <class 'str'>
print(result)         # 예상 출력: "1. 핵심 내용 ...\n2. ...\n3. ..."

```

> ⚠️ **흔한 실수**

1. `chain.batch()`에 딕셔너리 리스트 대신 문자열 리스트를 넣으면 `TypeError`가 발생합니다.
    올바른 형식: `chain.batch([{"length": "2", "text": "A"}, ...])`
2. `StrOutputParser()` 없이 `prompt | llm`만 연결하면 `result`가 str이 아닌
    `AIMessage` 객체로 반환됩니다. `result.content`로 접근하거나 parser를 추가하세요.

**v2 — 기능 추가: 배치 처리**

```
# lcel_v2.py — v1에 batch 추가
texts = [
    "회의 내용 A: AI 프로젝트 일정 조율 논의",
    "회의 내용 B: 예산 확정 및 팀 구성 완료",
    "회의 내용 C: 다음 달 데모 발표 준비",
]

results = chain.batch([
    {"length": "2", "text": texts[0]},
    {"length": "3", "text": texts[1]},
    {"length": "1", "text": texts[2]},
])

# 예상 출력: 3개 str로 이루어진 list
for i, r in enumerate(results):
    print(f"=== 텍스트{i+1} 요약 ===")
    print(r)
    # 예상: "1. AI 프로젝트 ...\n2. 일정 ..."

```

> ℹ️ **LCEL 실행 방식 한눈에 보기**
>
> | 메서드 동작 주요 용도                     |                     |                              |
> | -------------------------------- | ------------------- | ---------------------------- |
> | `invoke`                         | 완성될 때까지 기다린 후 결과 반환 | 단건 처리, 후속 처리가 필요한 경우         |
> | `stream`                         | 토큰이 생성되는 즉시 출력      | 챗봇 UI 타이핑 효과 (Day 9에서 본격 활용) |
> | `batch`                          | 여러 입력을 한 번에 병렬 처리   | 대량 데이터 전처리·일괄 분류             |
> | `ainvoke` / `astream` / `abatch` | 위 3종의 비동기 버전        | FastAPI·웹 서버 (Day 6\~8)      |
>
> ```
> # stream — 오늘은 구조만 확인 (Day 9에서 본격 활용)
> for chunk in chain.stream({"length": "3", "text": "긴 텍스트..."}):
>     print(chunk, end='', flush=True)   # 토큰 단위로 즉시 출력
> print()  # 마지막 줄바꿈
>
> # batch — max_concurrency로 동시 요청 수 제어 가능
> results = chain.batch(
>     [{"length": "2", "text": "A"}, {"length": "3", "text": "B"}],
>     config={"max_concurrency": 5},   # 기본값 5, Rate Limit 초과 방어 시 조절
> )
>
> ```

---

#### ⭐ 심화: RunnableParallel

```
# ⭐ 병렬 처리 — 요약과 분류를 동시에!
from langchain_core.runnables import RunnableParallel

prompt_summary = ChatPromptTemplate.from_messages([
    ("system", "요약 전문가입니다."),
    ("human", "다음 텍스트를 2줄로 요약:\n{text}"),
])

prompt_classify = ChatPromptTemplate.from_messages([
    ("system", "분류 전문가입니다."),
    ("human", "다음 텍스트의 주제를 [업무/개인/기술/기타] 중 하나로 분류:\n{text}"),
])

summary_chain    = prompt_summary  | llm | parser
classify_chain   = prompt_classify | llm | parser

parallel = RunnableParallel(
    summary  = summary_chain,
    category = classify_chain,
)

result = parallel.invoke({"text": "AI 프로젝트 킥오프 회의에서 팀 구성과 일정을 확정했습니다."})
print(result["summary"])    # 예상: "AI 프로젝트 킥오프에서 팀과 일정을 확정했다."
print(result["category"])   # 예상: "업무"
# LangSmith에서 두 호출이 동시에 실행된 것을 확인!

```

---

#### ⭐ 심화: Runnable 4종 완전 정복

체인의 **데이터 흐름을 정밀하게 제어**하기 위한 특수 Runnable 4종입니다.

| 종류 역할 주요 사용 시점        |                       |                                      |
| --------------------- | --------------------- | ------------------------------------ |
| `RunnablePassthrough` | 입력을 변환 없이 그대로 통과      | `chain.invoke("문자열")` 직접 입력 가능하게 할 때 |
| `RunnableLambda`      | 파이썬 함수를 Runnable로 감싸기 | 체인 중간에 커스텀 전처리·후처리가 필요할 때            |
| `RunnableParallel`    | 동일 입력을 여러 체인에 동시 실행   | context + question 동시 준비 (RAG 패턴)    |
| `RunnableSequence`    | 순차 파이프라인 명시적 정의       | \`                                   |

```
# runnable_4종.py
from langchain_core.runnables import (
    RunnablePassthrough, RunnableLambda,
    RunnableParallel, RunnableSequence,
)
from operator import itemgetter

# ① RunnablePassthrough — 문자열 직접 입력 패턴
# chain.invoke("질문") 시 {"question": "질문"} 으로 자동 변환
prompt_q  = ChatPromptTemplate.from_template("이 질문에 간단히 답해줘: {question}")
chain_rpt = {"question": RunnablePassthrough()} | prompt_q | llm | StrOutputParser()
print(chain_rpt.invoke("내일 해는 어디서 뜨지?"))   # 문자열 직접 입력 가능

# ② RunnableLambda — 파이썬 함수를 체인 중간에 삽입
preprocess = RunnableLambda(lambda x: x.strip().upper())   # 전처리: 공백 제거 + 대문자
greeting   = RunnableLambda(lambda name: f"안녕하세요, {name}님!")

chain_rl = preprocess | greeting
print(chain_rl.invoke("  alice  "))   # "안녕하세요, ALICE님!"

# ③ itemgetter — 딕셔너리 State에서 특정 키만 추출 (10월 LangGraph State 패턴 복선)
prompt_ig = ChatPromptTemplate.from_template(
    "{고객번호} 고객님, {창구번호}번 창구로 오십시오."
)
chain_ig = (
    {
        "고객번호": itemgetter("customer_number"),   # dict["customer_number"] 추출
        "창구번호": itemgetter("counter_number"),
    }
    | prompt_ig | llm | StrOutputParser()
)
print(chain_ig.invoke({"customer_number": "132", "counter_number": "4"}))

# ④ RunnableSequence — | 연산자와 완전히 동일 (명시적 표현)
double    = RunnableLambda(lambda x: x + x)
say_hello = RunnableLambda(lambda name: f"Hello, {name}!")
seq       = RunnableSequence(first=double, last=say_hello)
print(seq.invoke("Minjae"))              # "Hello, MinjaeMinjae!"
print((double | say_hello).invoke("Minjae"))  # 동일 출력 — | 방식

```

> ℹ️ **RAG 연결 미리보기 (9월 심화)**: `RunnableParallel` + `RunnablePassthrough`는 RAG 체인의 핵심 패턴입니다.
>
> ```
> # RAG 핵심 패턴 — context 검색과 question 통과를 동시에 준비
> rag_chain = (
>     RunnableParallel({
>         "context":  retriever,              # 질문으로 관련 문서를 검색
>         "question": RunnablePassthrough(),  # 질문 원문 그대로 통과
>     })
>     | prompt | llm | StrOutputParser()
> )
>
> ```
>
> 9월 RAG 세션에서 이 구조를 전체 파이프라인으로 확장합니다.

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  LCEL `prompt | llm | parser` 파이프를 직접 조립해 실행한다
- [ ]  `invoke`(단건) / `batch`(다건) 차이를 직접 확인한다
- [ ]  LangSmith에서 3단계 트레이스를 확인한다

#### 🔰 기본 실습 — 단계별 가이드

> AI 코파일럿(Claude Code / Cursor) 사용 권장. 코드 암기가 아니라 흐름 이해가 목표.

**Step 1**: `lcel_v1.py` 작성 후 실행 → `result`가 `str` 타입인지 확인

**Step 2**: `chain.batch([...])` 3건 이상 동시 처리 → 결과 list 출력

**Step 3**: LangSmith에서 `prompt-model-parser` 3단계 트레이스가 표시되는지 확인

**Step 4**: 스크린샷 캡처: `day3_m1_01_lcel_trace.png`

> ℹ️ **내 서비스 조각에 적용**: Day 2에서 만든 `ChatPromptTemplate`을 오늘 LCEL 체인에 바로 연결해보세요.
>
> ```
> # 내 서비스 체인 만들기
> chain = my_service_prompt | llm | StrOutputParser()
> result = chain.invoke({"내_변수": "테스트 입력"})
>
> ```

#### ⭐ 심화 실습

`RunnableParallel`로 요약 체인 + 분류 체인을 동시 실행한 뒤, 결과를 병합해 단일 `dict`로 출력. LangSmith에서 병렬 실행 트레이스를 확인.

#### 예상 결과물 & 제출 기준

| 구분 내용 확인 방법  |                                    |                          |
| ------------ | ---------------------------------- | ------------------------ |
| 🔰 기본        | invoke 결과(str) + batch 결과(list 3건) | `print(type(result))` 확인 |
| ⭐ 심화         | RunnableParallel dict 출력           | LangSmith 병렬 트레이스        |
| 제출           | LangSmith 링크 / 슬랙 `#day3-제출`       | —                        |

---

#### ✅ 모듈 3-1 체크포인트

```
chain = prompt | llm | parser
result = chain.invoke({"length": "3", "text": "..."})
print(type(result))  # <class 'str'>

```

✅ `prompt | model | parser` 파이프를 손으로 조립한다

✅ `invoke`와 `batch`의 차이를 설명한다

✅ LangSmith에서 3단계(prompt-model-parser) 트레이스를 확인한다

---

---

# 📦 모듈 3-2 · TypedDict & Pydantic BaseModel

| 항목 내용     |                                                                                              |
| --------- | -------------------------------------------------------------------------------------------- |
| **모듈 목표** | TypedDict(라벨만)와 Pydantic BaseModel(검증까지)의 차이를 이해하고, 각각의 사용처를 구분하며 LLM 출력 구조화에 Pydantic을 적용한다 |
| **선수 지식** | 모듈 3-1 LCEL 완료, Python 딕셔너리·클래스 기본 개념                                                        |
| **난이도**   | 🔰⭐ 기본+심화                                                                                    |

---

### 📚 강의 교안

#### 왜 배우는가?

방금 3-1에서 체인에 `{"length": "3", "text": "..."}` 같은 **딕셔너리**를 넣었습니다. 코드만 봐서는 이 딕셔너리에 무슨 키가 들어가야 하는지 알 수 없습니다. 데이터의 “모양”에 이름을 붙이는 도구가 두 가지 있습니다 — 라벨만 붙이는 **TypedDict**, 검사까지 하는 **Pydantic**. 이 둘은 이후 과정의 두 축이 됩니다.

또한 LLM은 항상 **자유로운 문자열**을 반환합니다. 서비스 코드는 특정 필드에 접근해야 하는데, 문자열에서 값을 추출하는 것은 매우 취약합니다.

```
# LLM이 반환하는 것
result = llm.invoke("이메일의 발신자와 요청을 추출해줘")
print(result.content)
# "발신자는 홍길동이고, 요청 사항은 미팅 일정 조율입니다."

# 이 문자열에서 '홍길동'만 추출하려면?
sender = result.content  # 파싱 불가! 문자열 전체
# 정규식? split("발신자는 ", 1)[1].split("이고")[0] → 너무 취약

```

```
# Pydantic 구조화 출력이 있으면
result = structured_llm.invoke("이메일을 분석해줘")
print(result.sender)        # "홍길동"  ← 바로 접근!
print(result.purpose)       # "미팅 일정 조율"
print(result.model_dump())  # {'sender': '홍길동', 'purpose': '미팅 일정 조율', ...}

```

---

#### 핵심 개념 ①: TypedDict — 딕셔너리에 이름표만 붙이기

> 💡 **비유 ①: TypedDict는 “안내판”, Pydantic은 “검문소”입니다**
>  안내판(TypedDict)은 “이 딕셔너리엔 이런 키가 있어야 합니다”라고 알려줄 뿐,
>  어겨도 실제로 막지 않습니다. 검문소(Pydantic)는 규칙에 안 맞으면 실제로
>  돌려보냅니다(`ValidationError`).
>  **이 비유의 한계**: 안내판도 완전히 무력하진 않습니다 — VS Code(Pylance)나
>  mypy 같은 타입 체커가 어긴 곳에 노란 밑줄 경고를 띄워줍니다.

> 💡 **비유 ②: 딕셔너리용 TypeScript interface입니다** (개발자 대상)
>  정적 분석 시점의 힌트일 뿐, 런타임에는 그냥 dict입니다.
>  `isinstance(x, MyTypedDict)` 검사도 불가합니다.
>  **이 비유의 한계**: TS는 컴파일러가 강제하지만, Python은 실행만 하면 그냥 통과합니다.
>  타입 체커를 따로 돌려야 경고가 보입니다.

```
# typeddict_example.py
from typing import TypedDict

class ChatState(TypedDict):        # 딕셔너리의 "모양"을 선언
    question:    str
    answer:      str
    tokens_used: int

# 생성·사용은 그냥 딕셔너리와 동일
state: ChatState = {"question": "안녕?", "answer": "", "tokens_used": 0}
state["answer"] = "안녕하세요!"     # 에디터가 키 이름을 자동 완성해줌

state["tokens"] = 10               # 오타! 실행은 되지만 에디터가 경고 표시
print(type(state))                 # <class 'dict'> — 런타임엔 그냥 dict, 검증 없음

```

> ⚠️ **흔한 오해**: “TypedDict로 선언했으니 잘못된 값은 자동으로 걸러지겠지” — 아닙니다.
>  실행하면 그냥 통과합니다. 검증이 필요하면 Pydantic을 쓰세요.

---

#### 핵심 개념 ②: Pydantic BaseModel — 검사까지 하는 이름표

> 💡 **비유 ①: BaseModel은 “주문서 양식”입니다**
>  수량 칸에 글씨를 쓰면 자동으로 거부되듯,
>  필드와 타입을 미리 정의합니다.
>  **이 비유의 한계**: 주문서는 사람이 채우지만
>  이것은 AI가 채웁니다. `Field(description=...)`의 품질이 결과를 좌우합니다.

> 💡 **비유 ②: TypeScript 인터페이스** (개발자 대상)
>
> ```
> interface EmailSummary {
>   sender: string;
>   purpose: string;
>   priority: number;  // 1~5
> }
>
> ```
>
> 와 동일한 개념을 Python에서 런타임 검증으로 합니다.
>  **이 비유의 한계**: TypeScript는 컴파일 타임, Pydantic은 런타임 검사입니다.
>  오류는 실행 시에 발견되므로, 테스트로 보완하는 습관이 필요합니다.

```
# pydantic_basics.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

class TaskClassification(BaseModel):
    """업무 분류 모델 — AI가 이 필드들을 채웁니다"""

    category: Literal["기술지원", "구매요청", "일정조율", "기타"] = Field(
        description="업무 유형 4가지 중 하나. 반드시 이 4가지 중에서 선택."
    )
    priority: int = Field(
        description="우선순위 1(낮음)~5(높음)",
        ge=1,   # greater than or equal: 1 이상
        le=5,   # less than or equal: 5 이하
    )
    summary: str = Field(
        description="핵심 요약 20자 이내",
        max_length=20,
    )
    urgent: bool = Field(
        description="24시간 이내 처리가 필요하면 True"
    )
    assignee: Optional[str] = Field(
        default=None,
        description="담당 부서명. 불명확하면 None"
    )

```

---

#### Field(description=…)이 왜 중요한가?

### AI를 위한 지시이자 코드 문서

```
# ❌ description 없음 — AI가 어떻게 채울지 모름
class Bad(BaseModel):
    category: str
    priority: int

# ✅ description 있음 — AI가 정확하게 채울 수 있음
class Good(BaseModel):
    category: str = Field(
        description="고객 문의 유형: '배송문의', '제품불량', '환불', '기타' 중 하나"
    )
    priority: int = Field(
        description="처리 시급도: 1(여유) ~ 5(즉시 처리). "
                    "배송 지연 3일 이상=5, 단순 문의=1"
    )

```

> ⚠️ **핵심 원칙**: `Field(description=...)`는 AI에게 주는 지시입니다.
>  모호하면 엉뚱한 값이 들어옵니다.
>  명확하면 AI가 정확하게 채웁니다.

---

#### Pydantic 검증 동작 확인

```
# pydantic_validation.py — 검증이 어떻게 동작하는지 확인

# ✅ 올바른 데이터 생성
task = TaskClassification(
    category="기술지원",
    priority=4,
    summary="VPN 연결 불가",
    urgent=True,
)
print(task.category)      # "기술지원"
print(task.priority)      # 4
print(task.model_dump())  # dict 변환 (JSON 전송용)
# 예상: {'category': '기술지원', 'priority': 4, 'summary': 'VPN 연결 불가', 'urgent': True, 'assignee': None}

# ❌ 잘못된 타입 → 즉시 ValidationError
try:
    bad_task = TaskClassification(
        category="없는카테고리",   # Literal에 없는 값
        priority=10,              # 5 초과 → ge/le 위반
        summary="a" * 30,         # max_length 초과
        urgent="maybe",           # bool이 아닌 값
    )
except Exception as e:
    print("검증 오류:", e)
    # 예상: pydantic_core._pydantic_core.ValidationError: 4 validation errors for TaskClassification
    #        category: Input should be '기술지원' or '구매요청' or '일정조율' or '기타' ...

```

---

#### TypedDict vs Pydantic: 사용처 구분 (이 과정 전체의 기준)

| TypedDict Pydantic BaseModel  |                         |                                        |
| ----------------------------- | ----------------------- | -------------------------------------- |
| **정체**                        | dict + 타입 라벨            | 검증 기능이 있는 클래스                          |
| **런타임 검증**                    | ❌ 없음 (에디터·타입체커 경고만)     | ✅ 있음 (ValidationError)                 |
| **접근 방식**                     | `state["key"]`          | `obj.field`                            |
| **비용**                        | 0 (그냥 dict)             | 검증·변환 비용 있음                            |
| **언제 쓰나**                     | **내 코드 안에서만 도는 상태**     | **밖에서 들어오는 못 믿을 데이터** (사용자 입력, LLM 출력) |
| **이 과정에서**                    | 10월 **LangGraph State** | 오늘 구조화 출력 → 8/12 FastAPI → 10월 MCP 스키마 |

> ℹ️ LangGraph는 에이전트의 상태(State)를 TypedDict로 정의합니다.
>  그래프 내부에서만 도는 데이터라 매 노드마다 검증할 필요가 없기 때문입니다.
>  오늘 이 구분을 기억하면 후에 “왜 State는 BaseModel이 아니지?”라는 질문에 스스로 답할 수 있습니다.

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  `TypedDict`로 딕셔너리 모양을 선언하고, 에디터 자동 완성이 작동하는지 확인한다
- [ ]  `BaseModel`을 상속해 필드 3개 이상의 클래스를 만든다
- [ ]  `Field(description=..., ge=..., max_length=...)` 제약을 사용한다
- [ ]  올바른 데이터와 잘못된 데이터를 직접 생성해 ValidationError를 확인한다

#### 🔰 기본 실습 — 단계별 가이드

> AI 코파일럿(Claude Code / Cursor) 사용 권장. 코드 암기가 아니라 흐름 이해가 목표.

**Step 1**: `ChatState` TypedDict 작성 → `state["question"]` 접근 확인, 오타 키 입력 시 에디터 경고 확인 (5분)

**Step 2**: `pydantic_basics.py` 파일 작성, `TaskClassification` 인스턴스 생성

**Step 3**: `.category`, `.priority`, `.model_dump()` 접근 확인

**Step 4**: 잘못된 값(`priority=10`)으로 `ValidationError` 의도적 발생 → 에러 메시지 읽기

> ℹ️ **내 서비스 조각에 적용**: 내 서비스가 반환해야 할 정보를 BaseModel로 스케치해보세요.
>  아직 LLM과 연결하지 않아도 됩니다 — 필드 이름과 타입만 정의하는 것이 오늘 목표입니다.

#### ⭐ 심화 실습

커스텀 검증자(`field_validator`)를 추가해 필드 값을 조건에 따라 변환·검증합니다.

```
# ⭐ pydantic_advanced.py — 커스텀 검증자
from pydantic import BaseModel, Field, field_validator, model_validator

class SmartTaskClassification(BaseModel):
    category: str = Field(description="업무 유형")
    priority: int = Field(description="우선순위 1~5", ge=1, le=5)
    summary:  str = Field(description="20자 이내 요약")

    @field_validator('summary')
    @classmethod
    def summary_must_be_concise(cls, v: str) -> str:
        """요약 앞뒤 공백 제거 후 길이 재확인"""
        v = v.strip()
        if len(v) > 20:
            raise ValueError(f"요약은 20자 이내여야 합니다 (현재:{len(v)}자)")
        return v

    @model_validator(mode='after')
    def urgent_category_check(self):
        """우선순위 5(긴급)는 '기타' 카테고리로 분류 불가"""
        if self.priority == 5 and self.category == "기타":
            raise ValueError("우선순위 5(긴급)는 '기타' 카테고리로 분류할 수 없습니다")
        return self

# 테스트
try:
    t = SmartTaskClassification(category="기타", priority=5, summary="긴급 처리")
except Exception as e:
    print(e)  # 예상: "우선순위 5(긴급)는 '기타' 카테고리로 분류할 수 없습니다"

```

#### 예상 결과물 & 제출 기준

| 구분 내용 확인 방법  |                                                              |               |
| ------------ | ------------------------------------------------------------ | ------------- |
| 🔰 기본        | TypedDict 에디터 자동 완성 확인 + BaseModel 인스턴스 + ValidationError 출력 | 터미널 출력 확인     |
| ⭐ 심화         | `field_validator` 또는 `model_validator` 동작 확인                 | 유효·무효 데이터 테스트 |
| 제출           | 오늘 제출 없음 (3-4에서 통합 제출)                                       | —             |

---

#### ✅ 모듈 3-2 체크포인트

✅ `TypedDict`와 `Pydantic BaseModel`의 차이를 한 문장으로 설명한다 (“TypedDict는 라벨만, Pydantic은 검증까지”)

✅ `BaseModel`을 상속해 필드 3개 이상의 클래스를 만든다

✅ `Field(description=..., ge=..., max_length=...)` 제약을 사용한다

✅ `Literal` 타입으로 허용값을 제한한다

✅ `model.field_name`으로 필드에 직접 접근한다

✅ TypedDict가 10월 LangGraph State로 재등장함을 이해한다

---

---

# 📦 모듈 3-3 · with\_structured\_output

| 항목 내용     |                                                                     |
| --------- | ------------------------------------------------------------------- |
| **모듈 목표** | `with_structured_output`으로 LLM 출력을 Pydantic 인스턴스로 받아 `.field`로 접근한다 |
| **선수 지식** | 모듈 3-2 TypedDict·BaseModel·Field 작성 완료, TypedDict vs Pydantic 구분 이해 |
| **난이도**   | 🔰⭐ 기본+심화                                                           |

---

### 📚 강의 교안

#### 왜 필요한가?

앞 모듈(3-2)에서 Pydantic BaseModel을 정의하는 방법을 배웠습니다. 이제 LLM이 이 형식에 맞게 출력하도록 연결해야 합니다. `with_structured_output`은 바로 이 연결 다리 역할을 합니다.

이것 없이는 LLM이 여전히 자유로운 문자열을 반환합니다. 아무리 정교한 Pydantic 스키마를 만들어도 LLM과 연결하지 않으면 무용지물입니다. `with_structured_output(스키마)`은 LLM에게 “반드시 이 형식으로만 답해라”는 계약을 맺는 것입니다.

---

#### 두 가지 구조화 방법 — 비교 먼저

LLM 출력을 Pydantic으로 받는 방법은 두 가지입니다.

| `PydanticOutputParser` `with_structured_output`  |                          |                                           |
| ------------------------------------------------ | ------------------------ | ----------------------------------------- |
| **방식**                                           | 프롬프트에 형식 지시문을 삽입해 파싱     | 모델 수준에서 형식 강제 (내부적으로 Function Calling 활용) |
| **안정성**                                          | 가끔 형식 이탈 가능              | 더 안정적 (JSON 강제 출력)                        |
| **호환성**                                          | 모든 LLM                   | Function Calling 지원 모델만 (gpt-4o-mini ✅)   |
| **프롬프트**                                         | `{format}` 자리에 지시문 삽입 필요 | 프롬프트 변경 불필요                               |
| **권장**                                           | 레거시 코드·호환성 필요 시          | **이 과정의 기본 (오늘 메인)**                      |

#### 방법 ①: PydanticOutputParser (참고용)

```
# pydantic_output_parser.py
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class EmailSummaryParser(BaseModel):
    person:  str = Field(description="메일을 보낸 사람의 이름")
    subject: str = Field(description="메일 제목")
    summary: str = Field(description="본문을 3문장 이내로 요약")
    date:    str = Field(description="본문에 언급된 미팅 날짜와 시간")

# 1단계: 파서 생성 → 형식 지시문 자동 생성
parser              = PydanticOutputParser(pydantic_object=EmailSummaryParser)
format_instructions = parser.get_format_instructions()
# get_format_instructions()가 스키마를 보고
# 'JSON으로 이렇게 출력해라'는 지시문을 자동 생성해줌

# 2단계: 프롬프트에 {format} 자리를 만들고 지시문을 미리 고정
prompt = ChatPromptTemplate.from_messages([
    ("system", "이메일에서 핵심 정보를 추출해. 모르면 빈 문자열로 두고 추측하지 마."),
    ("human", "아래 형식만 지켜 JSON으로 출력해.\n{format}\n\n이메일:\n{email_raw}"),
]).partial(format=format_instructions)   # {format}을 지시문으로 미리 고정

# 3단계: 체인 — parser가 JSON 문자열을 Pydantic 객체로 변환
chain  = prompt | llm | parser
result = chain.invoke({"email_raw": "안녕하세요, 홍길동 팀장님. 8/12 오전 10시 킥오프 미팅 참석 부탁드립니다."})

print(type(result))    # <class 'EmailSummaryParser'>
print(result.person)   # 홍길동
print(result.date)     # 8월 12일 오전 10시

```

> ⚠️ **PydanticOutputParser의 단점**: LLM이 형식을 이탈하면 파싱 오류가 발생합니다. 이를 보완하는 `OutputFixingParser`는 ⭐ 심화에서 다룹니다.

#### 방법 ②: with\_structured\_output (이 과정 표준)

---

#### with\_structured\_output 비유

> 💡 **비유 ①: with\_structured\_output은 “입사지원서 자동 분류 시스템”입니다**
>
> 지원자(LLM)의 자유로운 자기소개서를 받아 HR 시스템이 이름·학력·경력을 각 칸에 자동으로 채워넣듯,
>
> LLM의 자유 텍스트 응답을 Pydantic 필드에 자동으로 매핑합니다.
>
> 덕분에 지원서를 다시 읽어 파싱할 필요가 없습니다.
>
> **이 비유의 한계**: HR 시스템은 정해진 형식만 처리하지만,
>
> `with_structured_output`은 자연어를 이해해 유동적으로 필드를 채울 수 있습니다.
>
> 단, 스키마가 복잡할수록 실패 확률이 높아지므로 try-except가 필요합니다.

> 💡 **비유 ②: “JSON API 응답 계약서”입니다** (개발자 대상)
>
> REST API를 설계할 때 `OpenAPI 스키마`로 응답 형식을 미리 정의하듯,
>
> LLM에게 “반드시 이 JSON 구조로만 답해라”는 계약을 맺는 것입니다.
>
> LangChain이 내부적으로 function calling 또는 tool use를 통해 구조를 강제합니다.
>
> **이 비유의 한계**: REST API는 개발자가 응답 코드를 직접 작성하지만,
>
> `with_structured_output`은 LLM이 자율적으로 필드를 채우므로
>
> `Field(description=...)`의 품질이 응답 정확도를 좌우합니다.

---

#### Pydantic + LLM 연결하기

### 핵심: `llm.with_structured_output(모델클래스)`

```
# structured_output.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser  # 폴백용 추가
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 1. 출력 스키마 정의
class EmailSummary(BaseModel):
    sender:       str             = Field(description="발신자 이름")
    purpose:      str             = Field(description="이메일 목적 한 문장")
    action_items: list[str]       = Field(description="처리 필요 항목 목록")
    deadline:     Optional[str]   = Field(default=None, description="기한. 없으면 None")
    priority:     int             = Field(description="중요도 1~5", ge=1, le=5)

# 2. LLM에 스키마 등록
structured_llm = llm.with_structured_output(EmailSummary)

```

---

#### 완전한 체인 구성

```
# ↓↓↓ 수정: 프롬프트를 별도 변수로 추출 (버그 3 수정 — 폴백에서 재사용) ↓↓↓
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "이메일 분석 전문가입니다. 요청된 필드를 정확하게 추출하세요."),
    ("human", "다음 이메일을 분석해주세요:\n\n{email}"),
])
# ↑↑↑ 수정 끝 ↑↑↑

# 3. 프롬프트 + structured_llm으로 체인 구성
#    (StrOutputParser가 필요 없음! Pydantic이 이미 파서 역할)
chain = prompt_template | structured_llm

# 4. 호출
email_text = """
안녕하세요, 이팀장님.

8/12(수) 오전 10시 MCP 프로젝트 킥오프 미팅 참석 부탁드립니다.
준비 자료: 팀 소개 슬라이드 3~5장
확인 후 회신 부탁드립니다.

홍길동 드림
"""

result = chain.invoke({"email": email_text})

# 5. 결과는 EmailSummary 인스턴스!
print(type(result))               # <class '__main__.EmailSummary'>  ← 문자열이 아님!
print(result.sender)              # "홍길동"
print(result.purpose)             # "킥오프 미팅 참석 요청"
print(result.action_items)        # ["8/12 10시 미팅 참석", "팀 소개 슬라이드 준비"]
print(result.deadline)            # "8월 11일 (전날까지 확인 필요)"
print(result.priority)            # 4
print(result.model_dump())        # JSON 직렬화 가능한 dict

```

---

#### 텍스트 vs 구조화 출력 비교

| 구분 StrOutputParser with\_structured\_output  |            |                       |
| -------------------------------------------- | ---------- | --------------------- |
| **출력 타입**                                    | `str`      | Pydantic 인스턴스         |
| **필드 접근**                                    | 불가 (파싱 필요) | `result.sender` 직접 접근 |
| **타입 안전**                                    | ❌          | ✅ (검증됨)               |
| **JSON 변환**                                  | 직접 파싱      | `result.model_dump()` |
| **실패 위험**                                    | 낮음         | 복잡한 구조에서 가끔 실패        |

---

#### 오류 처리

```
# 중요한 호출은 try-except로 감싸기
try:
    result = chain.invoke({"email": email_text})
    return result.model_dump()

except Exception as e:
    print(f"구조화 출력 실패:{e}")
    # ↓↓↓ 수정: prompt_template 재사용 (버그 3 수정), StrOutputParser 임포트 필요 ↓↓↓
    fallback_chain = prompt_template | llm | StrOutputParser()   # prompt_template으로 수정
    raw_text = fallback_chain.invoke({"email": email_text})
    # ↑↑↑ 수정 끝 ↑↑↑
    return {"raw_output": raw_text, "parse_error": str(e)}

```

> ⚠️ **주의사항**: 복잡한 중첩 구조나 작은 모델에서 가끔 실패합니다.
>
> 프로덕션 코드에서는 항상 try-except + 폴백을 구현하세요.

---

#### ⭐ 심화: 중첩 모델

```
# ⭐ 심화 — 모델 안에 모델 리스트
class ActionItem(BaseModel):
    assignee: str = Field(description="담당자 이름")
    task:     str = Field(description="업무 내용")
    deadline: str = Field(description="기한 (YYYY-MM-DD 형식)")

class MeetingMinutes(BaseModel):
    title:        str              = Field(description="회의 제목")
    decisions:    list[str]        = Field(description="결정 사항 목록")
    action_items: list[ActionItem] = Field(description="액션 아이템 목록")  # 중첩!
    next_agenda:  list[str]        = Field(description="다음 회의 안건")

structured_llm = llm.with_structured_output(MeetingMinutes)

```

---

#### ⭐ 심화: OutputFixingParser — 파싱 실패 자동 복구

`PydanticOutputParser` 사용 시 LLM 출력이 형식을 이탈해 파싱에 실패하면, `OutputFixingParser`가 **LLM을 한 번 더 호출해 깨진 형식을 자동으로 수정**합니다. 기존 파서를 감싸는 래퍼 구조입니다.

> 💡 **비유: 교정 편집자 시스템입니다**
>  기자(LLM)가 형식을 어긴 원고를 제출하면 데스크(OutputFixingParser)가 형식에 맞게 고쳐 재발행합니다.
>  **이 비유의 한계**: 교정 편집자는 내용도 다듬지만, OutputFixingParser는 형식만 교정합니다. 내용의 정확성은 보장하지 않습니다.

**언제 쓰는가?**

- LLM 출력에 불필요한 설명이 섞여 JSON 파싱이 깨지는 경우
- 한국어·특수문자로 인해 인코딩 문제가 발생하는 경우
- 레거시 코드에 빠른 안전망이 필요한 경우

> ⚠️ 파싱 실패 시 LLM을 재호출하므로 **추가 토큰 비용과 응답 지연**이 발생합니다. 실패율이 높다면 `Field(description=...)`를 먼저 개선하는 것이 경제적입니다.

```
# output_fixing_parser.py
from langchain.output_parsers import OutputFixingParser

# PydanticOutputParser를 감싸는 방식으로 생성
# parser: 위에서 만든 PydanticOutputParser(pydantic_object=EmailSummaryParser)
fixing_parser = OutputFixingParser.from_llm(llm=llm, parser=parser)

# 기존 체인의 마지막 파서만 교체 — 나머지 구조는 동일
chain_with_fix = prompt | llm | fixing_parser
result = chain_with_fix.invoke({"email_raw": "홍길동 드림..."})

# 동작 순서:
#   1) LLM 출력 → parser로 파싱 시도
#   2) 성공 → 바로 반환
#   3) 실패 → llm에게 '형식에 맞게 수정해' 재요청
#   4) 수정된 출력 → parser로 재파싱 → 반환

```

> ℹ️ **실무 우선순위**: `with_structured_output` → 실패 시 `try-except + 폴백` → `OutputFixingParser`. 마지막 방법은 비용 때문에 마지막 수단으로 사용합니다.

---

### 🏋️ 실습 자료

#### 실습 목표

- [ ]  `with_structured_output`으로 LLM 응답을 Pydantic 인스턴스로 받는다
- [ ]  `.field_name`으로 특정 필드에 직접 접근한다
- [ ]  try-except 폴백 패턴을 구현한다

#### 🔰 기본 실습 — 단계별 가이드

**Step 1**: `EmailSummary` 모델 정의

**Step 2**: `chain = prompt_template | structured_llm` 조립

**Step 3**: 이메일 텍스트 3개를 invoke로 호출

**Step 4**: `type(result)`, `result.sender`, `result.model_dump()` 출력 확인

**Step 5**: LangSmith 링크 확인

> ℹ️ **내 서비스 조각에 적용**: 3-2에서 스케치한 내 서비스 출력 스키마를 `with_structured_output`과 연결해보세요.
>
> 3-4 실습의 예행 연습입니다.

#### ⭐ 심화 실습

`MeetingMinutes` 중첩 모델로 회의록 텍스트를 분석. `result.action_items[0].assignee`처럼 중첩 필드 접근.

#### 예상 결과물 & 제출 기준

| 구분 내용 확인 방법  |                                                 |        |
| ------------ | ----------------------------------------------- | ------ |
| 🔰 기본        | `type(result)` = Pydantic 클래스, `.field` 접근      | 터미널 출력 |
| ⭐ 심화         | 중첩 모델 필드 접근 (`result.action_items[0].assignee`) | 출력 확인  |
| 제출           | 오늘 제출 없음 (3-4에서 통합 제출)                          | —      |

---

#### ✅ 모듈 3-3 체크포인트

```
result = chain.invoke({"email": "..."})
print(type(result))      # <class 'EmailSummary'>  ← str이 아님!
print(result.sender)     # 필드 직접 접근

```

✅ `with_structured_output`으로 LLM 출력을 Pydantic 인스턴스로 받는다

✅ `.field_name`으로 특정 필드에 직접 접근한다

✅ `model_dump()`로 dict/JSON 형태로 변환한다

✅ `Field(description=...)`의 품질이 결과에 영향을 줌을 확인했다

---

---

# 📦 모듈 3-4 · 마이 서비스 조각 적용 실습

| 항목 내용     |                                                                                  |
| --------- | -------------------------------------------------------------------------------- |
| **모듈 목표** | 내 서비스 조각의 출력 구조를 Pydantic으로 정의하고 `with_structured_output` 체인을 만들어 테스트 3케이스를 실행한다 |
| **선수 지식** | 모듈 3-1 LCEL, 모듈 3-2 BaseModel, 모듈 3-3 with\_structured\_output 완료                |
| **난이도**   | 🔰⭐ 기본+심화                                                                        |

---

### 🏋️ 실습 자료

#### 오늘의 목표

### 내 서비스 출력을 Pydantic으로 구조화

**만들어야 하는 것:**

```
① 내 서비스 출력 스키마 (Pydantic BaseModel)
   → 내 서비스가 반환해야 할 필드들을 모두 정의
   → Field(description=...)로 각 필드 설명

② LCEL 체인 구성
   → ChatPromptTemplate | llm.with_structured_output(내 모델)

③ 3개 테스트 케이스 실행
   → 다양한 입력으로 구조화 출력 확인
   → .field 접근 확인

④ LangSmith 링크 제출

```

---

#### 서비스 유형별 출력 스키마 예시

**회의록 요약기**

```
class MeetingSummary(BaseModel):
    title: str = Field(description="회의 제목 또는 주제")
    date:  str = Field(description="회의 날짜 (언급된 경우)")
    key_decisions: list[str] = Field(
        description="회의에서 결정된 사항 목록 (결정만, 논의 제외)"
    )
    action_items: list[str] = Field(
        description="처리해야 할 액션 아이템 (담당자 + 업무 + 기한 포함)"
    )
    next_agenda: list[str] = Field(
        description="다음 회의 안건 목록",
        default=[],
    )
    summary_3lines: str = Field(
        description="회의 전체를 3줄 이내로 요약"
    )

```

**이메일 초안 도우미**

```
class EmailDraft(BaseModel):
    subject: str = Field(description="이메일 제목")
    greeting: str = Field(description="인사말 (예: '안녕하세요, 홍길동 부장님')")
    body: str = Field(description="본문 내용")
    closing: str = Field(description="마무리 인사")
    tone_score: int = Field(
        description="어조의 공손함 수준 1(캐주얼)~5(매우 격식체)",
        ge=1, le=5
    )

```

**민원 분류기**

```
from typing import Literal

class ComplaintClassification(BaseModel):
    category: Literal[
        "배송문의", "제품불량", "환불교환", "계정결제", "기타"
    ] = Field(description="민원 유형")
    priority: Literal["높음", "보통", "낮음"] = Field(
        description="처리 우선순위. '높음'=당일처리필요"
    )
    summary: str = Field(
        description="민원 핵심 내용 20자 이내",
        max_length=20
    )
    suggested_response: str = Field(
        description="고객에게 전달할 1줄 답변 초안"
    )
    escalation_needed: bool = Field(
        description="상위 부서 에스컬레이션 필요 여부"
    )

```

---

#### 🔰 기본 실습 — 단계별 가이드

```
# my_service_structured.py  ← Day 2의 my_service_v2.py 프롬프트를 Pydantic 출력으로 확장
# Day 2에서 작성한 ChatPromptTemplate과 시스템 프롬프트를 이 파일에 그대로 활용하세요.

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
# ↓↓↓ 수정: from typing import ... list 제거 (버그 5 수정 — ImportError) ↓↓↓
from typing import Literal, Optional   # list는 Python 3.9+ 빌트인, 임포트 불필요
# ↑↑↑ 수정 끝 ↑↑↑

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Step 1: 내 서비스 출력 스키마 정의
class MyServiceOutput(BaseModel):
    # 여기에 내 서비스에 필요한 필드를 정의하세요
    field1: str         = Field(description="...")
    field2: int         = Field(description="...", ge=1, le=5)
    field3: list[str]   = Field(description="...")   # list는 빌트인 타입 직접 사용
    field4: Optional[str] = Field(default=None, description="...")

# Step 2: 구조화 LLM 생성
structured_llm = llm.with_structured_output(MyServiceOutput)

# Step 3: 체인 구성 (프롬프트를 변수로 분리 — 폴백 재사용 가능)
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "내 시스템 프롬프트 (Day 2에서 만든 것 활용)"),
    ("human", "{user_input}"),
])
chain = prompt_template | structured_llm

# Step 4: 3개 테스트 케이스 실행
test_cases = [
    "테스트 입력 1 (정상 케이스)",
    "테스트 입력 2 (엣지 케이스)",
    "테스트 입력 3 (특수 상황)",
]

for i, test in enumerate(test_cases, 1):
    try:
        result = chain.invoke({"user_input": test})
        print(f"\n=== 테스트{i} ===")
        print(f"타입:{type(result).__name__}")
        print(f"결과:{result.model_dump()}")
    except Exception as e:
        print(f"\n=== 테스트{i} 실패 ===")
        print(f"오류:{e}")

```

---

#### ⭐ 심화 실습

**심화 ①: 중첩 모델** (모듈 3-3 MeetingMinutes 패턴을 내 서비스에 적용)

내 서비스 출력 스키마에서 단일 필드를 중첩 모델(`list[ItemModel]`)로 확장해보세요.

예: 회의록 → `action_items: list[ActionItem]`처럼 각 항목을 독립 모델로 분리.

**심화 ②: RunnableBranch 분기 체인**

입력 조건에 따라 다른 체인을 실행합니다. 예: 입력 길이가 짧으면 단순 분류, 길면 상세 분석.

```
# ⭐ RunnableBranch — 조건 분기 체인
from langchain_core.runnables import RunnableBranch

# 조건 함수 정의
is_long_text  = lambda x: len(x["user_input"]) > 200
is_short_text = lambda x: len(x["user_input"]) < 30

# 각 분기별 체인 (각자 적합한 스키마 사용)
long_chain    = prompt_template_detail  | llm.with_structured_output(DetailedOutput)
short_chain   = prompt_template_brief   | llm.with_structured_output(BriefOutput)
default_chain = prompt_template         | llm.with_structured_output(MyServiceOutput)

branch_chain = RunnableBranch(
    (is_long_text,  long_chain),    # 200자 초과 → 상세 분석
    (is_short_text, short_chain),   # 30자 미만 → 간단 분류
    default_chain,                  # 그 외 → 기본 체인
)

result = branch_chain.invoke({"user_input": "짧은 입력"})
print(result.model_dump())

```

---

**심화 ③: Literal + list[str] 타입 실전 — 고객 요청 자동 구조화**

`Literal`로 카테고리를 제한하고 `list[str]`로 태그·키워드를 추출하는 실전 패턴입니다. Day 4 Function Calling의 `@tool` 파라미터 설계에 같은 방식이 재등장합니다.

```
# customer_ticket_classifier.py
from pydantic import BaseModel, Field
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import json

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class TicketSummary(BaseModel):
    핵심문제: str = Field(..., description="고객이 겪는 핵심 문제 (명사형 어미로)")
    요청사항: str = Field(..., description="고객이 원하는 조치/해결 (명사형 어미로)")

    # Literal: 정해진 값 중 하나만 허용 — LLM이 다른 카테고리를 임의 생성 불가
    분류: Literal["문제해결", "기능요청", "결제/계정", "성능", "문의/가이드", "기타"] = Field(
        description="6개 유형 중 하나만 선택"
    )

    # list[str] + min_length/max_length: 태그 3~5개 강제
    태그: list[str] = Field(
        description="소문자, 언더바(_) 사용. 예: ['로그인_실패', 'ios']",
        min_length=3, max_length=5,
    )
    에스컬레이션: bool = Field(description="상위 부서 에스컬레이션 필요 여부")

structured_llm = llm.with_structured_output(TicketSummary)

SYSTEM = (
    "너는 고객 요청 요약 전문가다. 한국어로 답하고 아래 기준을 지켜라.\n"
    "- 분류: 6개 중 하나만 선택\n"
    "- 태그: 3~5개, 소문자, 언더바(_) 사용\n"
    "- 정보 부족 시 '미상' 사용, 개인정보 미포함"
)
prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", "다음 고객 요청을 구조화해줘:\n{request}"),
])
chain = prompt_template | structured_llm

ticket = "어제부터 앱 로그인에 계속 실패합니다. 비밀번호를 새로 바꿨는데도 안되네요. 아이폰입니다."
result = chain.invoke({"request": ticket})
print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
# 출력 예시:
# {
#   "핵심문제": "앱 로그인 반복 실패",
#   "요청사항": "로그인 문제 즉시 해결 요청",
#   "분류": "문제해결",
#   "태그": ["로그인_실패", "비밀번호_오류", "ios"],
#   "에스컬레이션": false
# }

# 여러 티켓을 한 번에 처리 — batch 활용
tickets = ["결제가 두 번 됐어요. 환불해주세요.", "5G인데 자꾸 LTE로 바뀝니다."]
results = chain.batch([{"request": t} for t in tickets])
for r in results:
    print(r.분류, "|", r.핵심문제)

```

> ⚠️ **Literal 설계 원칙**: 분류 불가 상황을 위한 `"기타"` 항목을 반드시 포함하세요. 없으면 LLM이 가장 가까운 범주를 억지로 선택하거나 오류가 발생합니다.

---

**심화 ④: partial\_variables + stream — 재사용 가능한 번역기**

`partial()`로 기본 언어 방향을 고정해두되, 호출 시 동적으로 덮어씌울 수 있는 유연한 체인 패턴입니다. `stream`으로 긴 번역 결과를 실시간 출력합니다.

```
# translator.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "너는 번역기야. {input_language}를 {output_language}로 번역해줘. "
        "자연스럽게, 비즈니스 어조로. 이모티콘 등 비즈니스에 맞지 않는 요소는 제거해."
    )),
    ("human", "다음 문장을 번역해줘: {text}"),
])

# partial: 기본 언어 방향을 미리 고정 — invoke 시 같은 키로 override 가능
prompt = prompt.partial(input_language="한국어", output_language="영어")

# RunnablePassthrough: chain.invoke("문자열") 직접 입력 패턴
chain = {"text": RunnablePassthrough()} | prompt | llm | StrOutputParser()

# 기본 방향(한국어→영어)으로 번역
ko_text = "안녕하세요. 내일 미팅이 취소됐습니다. 다시 일정을 잡아 주세요."
print(chain.invoke(ko_text))
# 출력: "Hello. The meeting scheduled for tomorrow has been cancelled. Please reschedule."

# stream으로 실시간 출력 + 언어 방향 override
en_casual = "today was fun — meeting moved to 3pm, let me know if that works!"
for chunk in chain.stream({
    "text":            en_casual,
    "input_language":  "영어",    # partial 기본값 override
    "output_language": "한국어",
}):
    print(chunk, end='', flush=True)
print()
# 출력: "오늘 즐거웠습니다. 미팅이 오후 3시로 변경됐습니다..."

```

> ℹ️ **partial override 원칙**: `partial()`로 고정한 변수는 `invoke()` 시 같은 키로 값을 넣으면 덮어씌워집니다. 기본값을 설정해두면서도 필요할 때 유연하게 바꾸는 강력한 패턴입니다.

---

#### 예상 결과물 & 제출 기준

| 구분 내용 확인 방법  |                                  |                |
| ------------ | -------------------------------- | -------------- |
| 🔰 기본        | 내 서비스 Pydantic 스키마 + 테스트 3케이스 실행 | `.field` 접근 출력 |
| ⭐ 심화         | 중첩 모델 또는 RunnableBranch 구현       | LangSmith 트레이스 |
| 제출           | LangSmith 트레이스 링크 슬랙 `#day3-제출`  | —              |

---

#### ✅ Day 3 최종 체크포인트

✅ `prompt | model | parser` 파이프를 직접 조립한다

✅ LLM 응답을 Pydantic 인스턴스로 받아 `.field`로 접근한다

✅ `Field(description=...)`이 왜 중요한지 설명할 수 있다

✅ TypedDict(라벨만)와 Pydantic(검증까지)의 차이를 한 문장으로 말할 수 있다

✅ 테스트 3케이스 LangSmith 링크를 슬랙에 제출했다