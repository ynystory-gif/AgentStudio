import re

from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask

SYSTEM = """당신은 AI Agent + MCP 프로그램 개발 요구사항을 분석하는 전문 인터뷰 에이전트입니다.

절대 규칙:
1. 한 메시지에서 질문은 정확히 하나만 합니다.
2. 사용자가 이미 알려준 내용을 다시 묻지 않습니다.
3. 답변을 짧게 확인한 뒤 가장 중요한 미확정 항목 하나만 질문합니다.
4. 불필요한 질문은 하지 않습니다.
5. 충분한 정보가 모이면 더 이상 질문하지 않고 요구사항을 요약합니다.
6. AI Agent, MCP Server/Client, Tool, 권한, 실행환경, LLM, DB, UI, 배포 요구를 고려합니다.
7. 요구사항 분석이 완료된 응답의 마지막 문장은 반드시 정확히 다음 문장으로 끝냅니다:
   "요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다."
8. 요구사항 분석 완료 후 "추가 요구사항이 필요하시면 말씀해 주세요", "더 필요한 내용이 있으면 알려주세요"처럼 사용자의 추가 입력을 유도하는 문장을 출력하지 않습니다.
9. 분석이 완료되지 않은 상태에서는 위 완료 문장을 사용하지 않습니다.
10. 첨부 파일은 내부 분석 근거입니다. 첨부 파일의 코드/문서 원문을 답변에 그대로 복사하거나 긴 코드 블록으로 출력하지 않습니다.
11. 첨부 파일을 사용한 경우에는 핵심 요구사항만 짧게 반영하고 인터뷰 질문을 계속합니다.
12. Hybrid Search 조합, Vector 검색 알고리즘, LangGraph 분기, DB PK/FK/Entity, Redis Key, Retry/Error Route처럼 AgentStudio가 스스로 설계해야 할 구현 세부사항을 사용자에게 결정하라고 묻지 않습니다.
13. 사용자가 이미 PostgreSQL/Redis/pgvector/검색/추천/주문 흐름처럼 구현 방향을 충분히 말한 경우, 같은 검색 알고리즘이나 결합 방식을 다시 묻지 않습니다.
14. 질문은 사용자 의사결정이 꼭 필요한 항목(UI 형태, 인증 정책, 외부 서비스/업무 규칙, 실행/배포 환경 등) 중 가장 중요한 미확정 항목 하나만 선택합니다.
"""



# v5.342 Question Quality Gate -------------------------------------------------
# The LLM proposes the next interview turn, but deterministic policy owns the
# final user-facing question. This prevents duplicate questions and stops the
# design agent from delegating its own architecture decisions back to users.
TECHNICAL_DELEGATION_PATTERNS = (
    '어떤 알고리즘', '알고리즘은 무엇', '알고리즘을 사용', '알고리즘과',
    '벡터화 및 검색', '벡터 검색을 어떻게', '벡터 검색 알고리즘',
    '어떻게 결합', '어떻게 조합', 'hybrid search를 어떻게',
    'langgraph 분기', 'langgraph를 어떻게', 'stategraph를 어떻게',
    'pk/fk', 'pk와 fk', 'entity 관계', '엔티티 관계', 'db 관계를 어떻게',
    '스키마를 어떻게 설계', 'redis key', 'redis 키를 어떻게',
    'retry route', 'error route', '재시도 경로를 어떻게',
)

DUPLICATE_TOPIC_DEFINITIONS = (
    ('ui', ('ui', '화면', '프론트엔드', 'react', 'streamlit'), ('react', 'streamlit', '웹 ui', '웹ui', 'gui', '화면', 'frontend', '프론트엔드')),
    ('auth', ('로그인', '인증', 'rbac', '권한'), ('로그인', '인증', 'rbac', '권한 관리', '사용자 계정')),
    ('database', ('db', '데이터베이스', 'postgresql', 'redis', 'pgvector'), ('db', '데이터베이스', 'postgresql', 'redis', 'pgvector')),
    ('llm', ('llm', 'openai', 'ollama', 'gpt'), ('llm', 'openai', 'ollama', 'gpt')),
    ('mcp', ('mcp', 'tool', '도구'), ('mcp', 'tool', '도구')),
    ('runtime', ('실행 환경', '실행할', '배포', 'windows', 'linux', 'docker'), ('windows', 'linux', 'docker', '온프레미스', '클라우드', '배포', '로컬 pc')),
    ('output', ('결과', '출력', 'json', '리포트', '보고서'), ('json', '리포트', '보고서', '결과 형식', '응답 형식')),
)


def _question_reasks_known_topic(content: str, user_text: str, history: list[dict]) -> bool:
    question = str(content or '').casefold()
    known = _conversation_text(user_text, history)
    for _slot, question_markers, known_markers in DUPLICATE_TOPIC_DEFINITIONS:
        if (
            any(marker.casefold() in question for marker in question_markers)
            and any(marker.casefold() in known for marker in known_markers)
        ):
            return True
    return False


QUESTION_SLOT_DEFINITIONS = (
    (
        'ui',
        ('react', 'streamlit', '웹 ui', '웹ui', 'gui', '화면', 'frontend', '프론트엔드'),
        '다음으로 사용자 화면은 어떤 형태로 만들까요? 예: React 웹앱, Streamlit, 또는 API 전용',
    ),
    (
        'auth',
        ('로그인', '인증', 'rbac', '권한 관리', '회원', '사용자 계정'),
        '다음으로 사용자 로그인이나 역할별 권한 관리가 필요한가요?',
    ),
    (
        'external',
        ('tavily', 'gmail', 'slack', '외부 api', '외부 서비스', 'mcp server', 'mcp tool', '결제 api'),
        '다음으로 반드시 연결해야 하는 외부 API나 MCP Tool이 있나요? 없다면 없다고 말씀해 주세요.',
    ),
    (
        'runtime',
        ('windows', 'linux', 'docker', '온프레미스', '클라우드', '배포', '로컬 pc', 'aws', 'azure', 'gcp'),
        '다음으로 이 Agent는 어디에서 실행할 예정인가요? 예: Windows 로컬 PC, Docker 서버, 클라우드',
    ),
    (
        'business_rule',
        ('승인 후', '확인 후', '주문 확인', '관리자 승인', '자동 주문', '업무 규칙'),
        '다음으로 실제 업무를 실행하기 전에 사용자 확인이나 승인이 반드시 필요한 작업이 있나요?',
    ),
    (
        'output',
        ('json', '리포트', '보고서', '다운로드', '저장 형식', '결과 형식', '응답 형식'),
        '다음으로 최종 결과는 화면 응답만 제공하면 되나요, 아니면 JSON·파일·리포트 저장도 필요하나요?',
    ),
)


def _conversation_text(user_text: str, history: list[dict]) -> str:
    parts = []
    for item in history or []:
        if str(item.get('role') or '') == 'user':
            parts.append(str(item.get('content') or ''))
    parts.append(str(user_text or ''))
    return '\n'.join(parts).casefold()


def _question_count(content: str) -> int:
    text = str(content or '')
    # Korean questions are normally terminated by ?; include the full-width mark.
    return text.count('?') + text.count('？')


def _contains_technical_delegation(content: str) -> bool:
    lowered = str(content or '').casefold()
    return any(pattern.casefold() in lowered for pattern in TECHNICAL_DELEGATION_PATTERNS)


def _next_user_decision_question(user_text: str, history: list[dict]) -> str:
    known = _conversation_text(user_text, history)
    for _slot, markers, question in QUESTION_SLOT_DEFINITIONS:
        if not any(marker.casefold() in known for marker in markers):
            return question
    return '마지막으로 이 Agent에서 사용자가 반드시 직접 결정해야 하는 업무 정책이나 제한사항이 있나요? 없다면 없다고 말씀해 주세요.'


def _technical_confirmation(user_text: str, history: list[dict]) -> str:
    known = _conversation_text(user_text, history)
    facts = []
    for label, markers in (
        ('PostgreSQL', ('postgresql',)),
        ('Redis', ('redis',)),
        ('pgvector 의미 검색', ('pgvector', 'vector 검색', '벡터 검색')),
        ('자연어 상품 검색', ('자연어', '상품 검색')),
        ('상품 추천', ('추천',)),
        ('재고 확인', ('재고',)),
        ('주문 생성', ('주문',)),
    ):
        if any(marker.casefold() in known for marker in markers):
            facts.append(label)
    if not facts:
        return '말씀하신 내용을 요구사항에 반영했습니다.'
    return '말씀하신 ' + ' · '.join(facts[:7]) + ' 요구사항을 반영했습니다.'


def apply_question_quality_gate(
    content: str,
    user_text: str,
    history: list[dict],
) -> tuple[str, dict]:
    """Validate the LLM's next question and deterministically repair it.

    Returns `(answer, diagnostics)` so API/validation code can explain why a
    generated question was replaced without exposing hidden model reasoning.
    """
    answer = str(content or '').strip()
    completion = (
        '요구사항 분석 완료' in answer
        or '요구사항 분석이 완료' in answer
    )
    if completion:
        return answer, {'passed': True, 'replaced': False, 'reasons': []}

    reasons = []
    if _question_count(answer) > 1:
        reasons.append('multiple_questions')
    if _contains_technical_delegation(answer):
        reasons.append('technical_design_delegation')
    if _question_reasks_known_topic(answer, user_text, history):
        reasons.append('duplicate_answered_topic')

    # A non-completion interview turn must contain one clear question.
    if _question_count(answer) == 0:
        reasons.append('missing_question')

    if not reasons:
        return answer, {'passed': True, 'replaced': False, 'reasons': []}

    replacement = (
        _technical_confirmation(user_text, history)
        + '\n\n'
        + _next_user_decision_question(user_text, history)
    )
    return replacement, {
        'passed': True,
        'replaced': True,
        'reasons': reasons,
    }

def _looks_like_attachment_echo(content: str, attachment_context: str) -> bool:
    """Detect accidental reference-file dumps in user-visible interview output."""
    answer = str(content or '').strip()
    evidence = str(attachment_context or '')
    if not answer or not evidence:
        return False

    answer_lines = [line.strip() for line in answer.splitlines() if line.strip()]
    code_like = 0
    for line in answer_lines:
        if (
            line.startswith(('import ', 'from ', 'def ', 'class ', '```', '# ', '## '))
            or ' = ' in line
            or line.startswith(('SELECT ', 'CREATE ', 'INSERT ', 'UPDATE '))
        ):
            code_like += 1
    if len(answer) >= 600 and ('```' in answer or answer.startswith(('import ', 'from ', '# '))) and code_like >= 4:
        return True
    if len(answer) >= 1800 and answer_lines and (code_like / len(answer_lines)) >= 0.22:
        return True

    matched_chars = 0
    matched_lines = 0
    for line in answer_lines:
        if len(line) < 60:
            continue
        if line in evidence:
            matched_lines += 1
            matched_chars += len(line)
            if matched_lines >= 3 or matched_chars >= 500:
                return True

    lowered = answer.casefold()
    if len(answer) >= 1200 and (lowered.count('import ') + lowered.count('from ')) >= 8:
        return True
    return False


def _safe_attachment_fallback() -> str:
    return (
        "첨부 파일의 구조와 주요 내용을 분석해 요구사항 Context에 반영했습니다. "
        "파일 원문이나 긴 코드는 대화창에 그대로 표시하지 않도록 보호했습니다.\n\n"
        "다음으로, 이 Agent가 입력으로 반드시 지원해야 할 파일 형식은 무엇인가요? "
        "예: PDF, Word, Excel, 코드 파일, Jupyter Notebook"
    )


async def next_interview_message(user_text: str, history: list[dict], provider: str | None = None, attachment_context: str = "") -> str:
    llm = model_for_task(LLMTask.REQUIREMENTS_ANALYSIS, provider)
    compact = "\n".join(f"{x['role']}: {x['content']}" for x in history[-20:])
    attachment_block = str(attachment_context or "").strip()
    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(
            content=(
                f"이전 대화:\n{compact}\n\n"
                f"사용자 최신 답변:\n{user_text}"
                + (f"\n\n{attachment_block}\n\n첨부 파일의 내용도 요구사항 근거로 분석하세요. 파일에 없는 내용을 임의로 만들지 마세요." if attachment_block else "")
            )
        )
    ]
    result = await llm.ainvoke(messages)
    content = str(result.content).strip()

    if _looks_like_attachment_echo(content, attachment_block):
        retry_messages = [
            SystemMessage(
                content=SYSTEM
                + "\n추가 보호 규칙: 방금 생성된 응답이 첨부 원문을 과도하게 복사했습니다. "
                  "코드 블록과 파일 원문은 출력하지 말고, 700자 이내 한국어로 확인 내용과 질문 하나만 답하세요."
            ),
            HumanMessage(
                content=(
                    f"이전 대화:\n{compact}\n\n"
                    f"사용자 최신 답변:\n{user_text}"
                    + (f"\n\n{attachment_block}" if attachment_block else "")
                    + "\n\n첨부 원문을 절대 재출력하지 말고 요구사항만 추론하세요."
                )
            ),
        ]
        retry = await llm.ainvoke(retry_messages)
        retry_content = str(retry.content).strip()
        content = (
            _safe_attachment_fallback()
            if _looks_like_attachment_echo(retry_content, attachment_block)
            else retry_content
        )

    content, _quality_gate = apply_question_quality_gate(
        content,
        user_text,
        history,
    )

    completion_markers = (
        "요구사항 분석 완료",
        "요구사항 분석이 완료",
    )
    if any(marker in content for marker in completion_markers):
        trailing_patterns = (
            r"\n*추가 요구사항이 필요하시면[^\n]*[.!！?？]?$",
            r"\n*추가적인 질문이나 요구사항이 생기면[^\n]*[.!！?？]?$",
            r"\n*더 필요한 내용이 있으면[^\n]*[.!！?？]?$",
            r"\n*추가로 필요한 사항이 있으면[^\n]*[.!！?？]?$",
        )
        for pattern in trailing_patterns:
            content = re.sub(
                pattern,
                "",
                content,
                flags=re.IGNORECASE,
            ).rstrip()

        final_message = (
            "요구사항 분석이 완료되었습니다. "
            "Workflow 설계 단계로 진행할 수 있습니다."
        )
        if not content.endswith(final_message):
            content = content.rstrip() + "\n\n" + final_message

    return content


ATTACHMENT_REQUIREMENTS_SUMMARY_SYSTEM = """당신은 사용자가 첨부한 참고 파일을 읽고, 사용자가 만들고자 하는 프로그램/AI Agent의 요구사항을 정리하는 분석가입니다.

규칙:
1. 파일 원문, 긴 코드, CSV 행, 환경변수 값, API Key/Token/Password를 그대로 출력하지 않습니다.
2. 여러 파일은 하나의 프로젝트 의도로 통합해서 해석합니다.
3. 파일에서 확인된 사실과 추정한 내용을 구분합니다.
4. 사용자가 만들고자 하는 핵심 목적을 먼저 1~2문장으로 정리합니다.
5. 출력은 반드시 아래 5개 제목을 사용합니다.
   - 만들고자 하는 내용
   - 핵심 기능
   - 입력 / 데이터
   - 기술 / 연동
   - 추가 확인이 필요한 항목
6. 각 항목은 짧은 한국어 bullet로 작성하고 전체는 1,500자 이내로 작성합니다.
7. 파일에서 알 수 없는 내용은 확정하지 말고 '추가 확인 필요'로 표시합니다.
"""


def _deterministic_attachment_requirements_summary(attachment_context: str) -> str:
    text = str(attachment_context or '')
    lowered = text.casefold()
    names = re.findall(r'^###\s+(?:참고 파일 분석본|첨부 파일):\s*(.+)$', text, flags=re.MULTILINE)
    technologies = []
    for label, needles in (
        ('Streamlit', ('streamlit', 'st.')),
        ('FastAPI', ('fastapi', 'uvicorn')),
        ('PostgreSQL', ('postgresql', 'psycopg', 'postgres')),
        ('pgvector', ('pgvector', 'embedding', 'vector')),
        ('Redis', ('redis',)),
        ('OpenAI', ('openai', 'gpt-')),
        ('Ollama', ('ollama',)),
        ('LangChain/LangGraph', ('langchain', 'langgraph')),
        ('MCP', ('mcp', 'stdio', 'streamable http')),
    ):
        if any(needle in lowered for needle in needles):
            technologies.append(label)

    file_label = ', '.join(names[:6]) if names else '선택한 참고 파일'
    tech_label = ', '.join(technologies) if technologies else '파일에서 확인된 기술 스택'
    return (
        '## 만들고자 하는 내용\n'
        f'- {file_label}의 구조와 데이터를 참고해 기존 실습/프로젝트 기능을 하나의 프로그램 또는 Agent로 구성하려는 것으로 파악했습니다.\n\n'
        '## 핵심 기능\n'
        '- 첨부 자료에 포함된 주요 처리 흐름을 재사용하고, 사용자 요구에 맞게 조회·분석·처리 기능을 연결합니다.\n'
        '- 세부 기능 우선순위는 인터뷰에서 추가 확인이 필요합니다.\n\n'
        '## 입력 / 데이터\n'
        '- 첨부된 코드·Notebook·데이터 파일을 요구사항 근거로 사용합니다.\n\n'
        '## 기술 / 연동\n'
        f'- 감지된 주요 기술: {tech_label}\n\n'
        '## 추가 확인이 필요한 항목\n'
        '- 최종 화면 형태, 반드시 제공해야 할 결과, 실행/배포 방식의 우선순위를 확인해야 합니다.'
    )


async def summarize_attachment_requirements(
    attachment_context: str,
    previous_summary: str = '',
    provider: str | None = None,
) -> str:
    """Summarize selected files into user-visible project intent, never raw bodies."""
    evidence = str(attachment_context or '').strip()
    previous = str(previous_summary or '').strip()[-6000:]
    if not evidence:
        return ''

    llm = model_for_task(LLMTask.REQUIREMENTS_ANALYSIS, provider)
    prompt = (
        (f'기존 첨부 분석 요약:\n{previous}\n\n' if previous else '')
        + '새로 첨부한 파일의 안전한 압축 분석 Context:\n'
        + evidence
        + '\n\n위 자료를 통합해서 사용자가 만들고자 하는 내용을 정리하세요.'
    )
    try:
        result = await llm.ainvoke([
            SystemMessage(content=ATTACHMENT_REQUIREMENTS_SUMMARY_SYSTEM),
            HumanMessage(content=prompt),
        ])
        content = str(result.content or '').strip()
        if (
            not content
            or len(content) > 2600
            or _looks_like_attachment_echo(content, evidence)
        ):
            return _deterministic_attachment_requirements_summary(evidence)
        required_headings = (
            '만들고자 하는 내용',
            '핵심 기능',
            '입력 / 데이터',
            '기술 / 연동',
            '추가 확인이 필요한 항목',
        )
        if not all(heading in content for heading in required_headings):
            return _deterministic_attachment_requirements_summary(evidence)
        return content
    except Exception:
        return _deterministic_attachment_requirements_summary(evidence)
