import re
from difflib import SequenceMatcher

from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask
from app.services.attachment_requirement_mining import (
    extract_attachment_requirement_registry,
    format_requirement_registry_memory,
    summary_bullets_by_category,
)

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
15. 첨부 파일 분석 완료 안내는 같은 첨부 Batch에서 한 번만 말합니다. 이후 턴에서는 첨부 분석 요약을 내부 Context로만 사용하고 같은 안내문을 반복하지 않습니다.
16. 사용자의 최신 답변이 새로운 요구사항이면 먼저 그 요구사항을 짧게 반영한 뒤, 이미 물어본 질문이 아닌 다음 미확정 항목 하나만 질문합니다.
17. 최근 Assistant 응답과 거의 동일한 문장을 반복하지 않습니다.
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
        'files',
        ('.txt', '.md', '.py', '.pdf', '.docx', '.xlsx', '.csv', '.ipynb', '파일 형식', '확장자'),
        '다음으로 이 Agent가 반드시 지원해야 하는 입력 파일 형식은 무엇인가요? 예: PDF, Word, Excel, CSV, 코드 파일, Jupyter Notebook',
        ('파일 형식', '입력 파일', '확장자', '지원해야 하는 파일'),
    ),
    (
        'output',
        ('json', '리포트', '보고서', '다운로드', '저장 형식', '결과 형식', '응답 형식'),
        '다음으로 최종 결과는 화면 응답만 제공하면 되나요, 아니면 JSON·파일·리포트 저장도 필요하나요?',
        ('최종 결과', '결과 형식', '응답 형식', '리포트 저장'),
    ),
    (
        'llm',
        ('llm', 'openai', 'ollama', 'gpt', 'qwen', 'gemini', 'claude'),
        '다음으로 사용할 LLM은 무엇인가요? 예: OpenAI, Ollama 로컬 모델, 또는 둘 다 지원',
        ('사용할 llm', 'llm은', 'openai', 'ollama'),
    ),
    (
        'ui',
        ('react', 'streamlit', '웹 ui', '웹ui', 'gui', '화면', 'frontend', '프론트엔드'),
        '다음으로 사용자 화면은 어떤 형태로 만들까요? 예: React 웹앱, Streamlit, 또는 API 전용',
        ('사용자 화면', 'ui는', 'react', 'streamlit', 'api 전용'),
    ),
    (
        'backend',
        ('fastapi', 'uvicorn', 'backend', '백엔드', 'flask', 'django', 'nestjs'),
        '다음으로 Backend가 필요한가요? 필요하다면 FastAPI 같은 API 서버를 사용할까요?',
        ('backend', '백엔드', 'api 서버'),
    ),
    (
        'mcp',
        ('mcp', 'tool', '도구', 'stdio', 'streamable http', 'transport'),
        '다음으로 외부 MCP Server나 Tool 연동이 필요한가요? 없다면 없다고 말씀해 주세요.',
        ('mcp', 'tool 연동', '외부 도구'),
    ),
    (
        'database',
        ('db', '데이터베이스', 'postgresql', 'redis', 'pgvector', 'sqlite', 'mssql', 'oracle'),
        '다음으로 저장소가 필요한가요? 사용하려는 DB·Cache·Vector DB가 정해져 있다면 말씀해 주세요.',
        ('저장소', 'db', '데이터베이스', 'cache', 'vector db'),
    ),
    (
        'permission',
        ('로그인', '인증', 'rbac', '권한', 'project root', '프로젝트 root', 'root 내부', '파일 접근'),
        '다음으로 사용자 인증·역할 권한이나 프로젝트 파일 접근 제한이 필요한가요?',
        ('인증', '권한', '파일 접근', '프로젝트 root'),
    ),
    (
        'runtime',
        ('windows', 'linux', 'docker', '온프레미스', '클라우드', '배포', '로컬 pc', 'aws', 'azure', 'gcp'),
        '다음으로 이 Agent는 어디에서 실행할 예정인가요? 예: Windows 로컬 PC, Docker 서버, 클라우드',
        ('실행할 예정', '실행 환경', '배포 환경', 'windows', 'docker'),
    ),
    (
        'limits',
        ('10mb', 'mb', 'gb', '120초', 'timeout', '타임아웃', 'chunk', '청크', '처리 제한', '최대 크기', '최대', '조회 제한', '건만', '건까지'),
        '마지막으로 파일 크기·처리 시간·동시 작업 수처럼 반드시 지켜야 할 처리 제한이 있나요? 없다면 없다고 말씀해 주세요.',
        ('처리 제한', '파일 크기', '타임아웃', '동시 작업'),
    ),
)



def _conversation_text(user_text: str, history: list[dict], extra_context: str = "") -> str:
    parts = []
    for item in history or []:
        if str(item.get('role') or '') == 'user':
            parts.append(str(item.get('content') or ''))
    parts.append(str(user_text or ''))
    if str(extra_context or '').strip():
        parts.append(str(extra_context or ''))
    return '\n'.join(parts).casefold()


def _question_count(content: str) -> int:
    text = str(content or '')
    return text.count('?') + text.count('？')


def _contains_technical_delegation(content: str) -> bool:
    lowered = str(content or '').casefold()
    return any(pattern.casefold() in lowered for pattern in TECHNICAL_DELEGATION_PATTERNS)


def _asked_question_slots(history: list[dict]) -> set[str]:
    asked: set[str] = set()
    for item in history or []:
        if str(item.get('role') or '') != 'assistant':
            continue
        content = str(item.get('content') or '').casefold()
        if not content or ('?' not in content and '？' not in content):
            continue
        for slot, _known_markers, _question, ask_markers in QUESTION_SLOT_DEFINITIONS:
            if any(marker.casefold() in content for marker in ask_markers):
                asked.add(slot)
    return asked


def _assistant_question_slot(content: str) -> str:
    text = str(content or '').casefold()
    if not text or ('?' not in text and '？' not in text):
        return ''
    for slot, _markers, _question, ask_markers in QUESTION_SLOT_DEFINITIONS:
        if any(marker.casefold() in text for marker in ask_markers):
            return slot
    return ''


def _is_explicit_none_answer(value: str) -> bool:
    text = re.sub(r'\s+', ' ', str(value or '').casefold()).strip(' .!?？!')
    if not text:
        return False
    exact = {
        '없다', '없음', '없습니다', '필요 없다', '필요없다', '필요 없습니다',
        '사용하지 않는다', '사용 안 한다', '안 쓴다', '해당 없음', '없어도 된다',
        '제한 없다', '추가 제한 없다', '별도 제한 없다',
    }
    if text in exact:
        return True
    return any(token in text for token in (
        '필요 없다', '필요없', '사용하지 않', '별도 제한은 없', '추가 제한은 없',
        '권한은 필요 없', '인증은 필요 없', '파일은 없',
    ))


def _answered_question_slots(user_text: str, history: list[dict], extra_context: str = '') -> set[str]:
    """Resolve slot completion from facts *and* the question/answer sequence.

    A user saying "없다" is a valid completed answer, not an empty value.  Because
    the interview asks exactly one question at a time, the next substantive user
    turn also closes that pending slot even when the answer does not repeat the
    slot keyword verbatim.
    """
    answered: set[str] = set()
    known = _conversation_text(user_text, history, extra_context)
    for slot, markers, _question, _ask_markers in QUESTION_SLOT_DEFINITIONS:
        if any(marker.casefold() in known for marker in markers):
            answered.add(slot)

    pending = ''
    for item in history or []:
        role = str(item.get('role') or '')
        content = str(item.get('content') or '').strip()
        if role == 'assistant':
            detected = _assistant_question_slot(content)
            if detected:
                pending = detected
            continue
        if role != 'user' or not content or not pending:
            continue
        # Meta questions can postpone the pending answer; ordinary answers close
        # the slot. Explicit NONE is always a legitimate completed value.
        lowered = content.casefold()
        meta_only = any(token in lowered for token in ('추가로 필요한', '더 필요한', '다음 질문')) and len(content) < 80
        if not meta_only:
            answered.add(pending)
            pending = ''

    # The current user_text is not yet part of history at API call time.
    if pending and str(user_text or '').strip():
        lowered = str(user_text or '').casefold()
        meta_only = any(token in lowered for token in ('추가로 필요한', '더 필요한', '다음 질문')) and len(str(user_text)) < 80
        if _is_explicit_none_answer(user_text) or not meta_only:
            answered.add(pending)

    return answered


def _unknown_question_slots(user_text: str, history: list[dict], extra_context: str = "") -> list[tuple]:
    answered = _answered_question_slots(user_text, history, extra_context)
    return [row for row in QUESTION_SLOT_DEFINITIONS if row[0] not in answered]

def _next_user_decision_question(user_text: str, history: list[dict], extra_context: str = "") -> str:
    unknown = _unknown_question_slots(user_text, history, extra_context)
    if not unknown:
        return ''
    asked = _asked_question_slots(history)
    for slot, _markers, question, _ask_markers in unknown:
        if slot not in asked:
            return question
    # 이미 물어본 미확정 Slot을 자동으로 반복하지 않습니다. One-question-at-a-time
    # 인터뷰에서는 답변 State가 비어 보여도 같은 질문을 계속 보내는 것보다 검토 단계로
    # 넘기고 사용자가 수정할 수 있게 하는 편이 안전합니다.
    return ''


def _quality_gate_next_question(user_text: str, history: list[dict]) -> str:
    """v5.342의 기술 위임 방지 Gate 우선순위를 유지합니다."""
    known = _conversation_text(user_text, history)
    legacy = (
        (('react', 'streamlit', '웹 ui', '웹ui', 'gui', '화면', 'frontend', '프론트엔드'), '다음으로 사용자 화면은 어떤 형태로 만들까요? 예: React 웹앱, Streamlit, 또는 API 전용'),
        (('로그인', '인증', 'rbac', '권한 관리', '회원', '사용자 계정'), '다음으로 사용자 로그인이나 역할별 권한 관리가 필요한가요?'),
        (('tavily', 'gmail', 'slack', '외부 api', '외부 서비스', 'mcp server', 'mcp tool', '결제 api'), '다음으로 반드시 연결해야 하는 외부 API나 MCP Tool이 있나요? 없다면 없다고 말씀해 주세요.'),
        (('windows', 'linux', 'docker', '온프레미스', '클라우드', '배포', '로컬 pc', 'aws', 'azure', 'gcp'), '다음으로 이 Agent는 어디에서 실행할 예정인가요? 예: Windows 로컬 PC, Docker 서버, 클라우드'),
        (('승인 후', '확인 후', '주문 확인', '관리자 승인', '자동 주문', '업무 규칙'), '다음으로 실제 업무를 실행하기 전에 사용자 확인이나 승인이 반드시 필요한 작업이 있나요?'),
        (('json', '리포트', '보고서', '다운로드', '저장 형식', '결과 형식', '응답 형식'), '다음으로 최종 결과는 화면 응답만 제공하면 되나요, 아니면 JSON·파일·리포트 저장도 필요하나요?'),
    )
    for markers, question in legacy:
        if not any(marker.casefold() in known for marker in markers):
            return question
    return '마지막으로 이 Agent에서 사용자가 반드시 직접 결정해야 하는 업무 정책이나 제한사항이 있나요? 없다면 없다고 말씀해 주세요.'


def _latest_requirement_confirmation(user_text: str) -> str:
    latest = str(user_text or '').strip()
    lowered = latest.casefold()
    if not latest:
        return '확인했습니다.'
    if any(token in lowered for token in ('추가로 필요한', '더 필요한', '또 필요한', '추가 사항')):
        return '네. 아직 확인하지 않은 요구사항이 있으면 하나씩 이어서 확인하겠습니다.'
    if ('상품' in lowered and '검색' in lowered) and any(token in lowered for token in ('벡터', 'vector', '문장', '자연어', '의미')):
        return '상품 검색을 자연어 문장 기반 의미·벡터 검색으로 처리하는 요구사항을 반영했습니다.'
    max_result = re.search(r'(?:최대\s*)?(\d{1,6})\s*건', lowered)
    if max_result and ('조회' in lowered or '검색' in lowered or '데이터' in lowered):
        file_none = '파일은 없' in lowered or '파일 없다' in lowered
        prefix = '별도 입력 파일은 없는 것으로, ' if file_none else ''
        return f"{prefix}조회 결과를 최대 {max_result.group(1)}건으로 제한하는 요구사항을 반영했습니다."
    if '리포트' in lowered and any(token in lowered for token in ('저장', '적용', '필요')):
        return '화면 결과와 함께 리포트를 저장하는 요구사항을 반영했습니다.'
    if any(token in lowered for token in ('postgresql', 'redis', 'pgvector', 'db', '데이터베이스')):
        return '말씀하신 DB·저장소 요구사항을 반영했습니다.'
    if any(token in lowered for token in ('pdf', 'word', 'excel', 'csv', 'ipynb', 'jupyter', '파일')):
        return '말씀하신 입력 파일 요구사항을 반영했습니다.'
    if any(token in lowered for token in ('openai', 'ollama', 'llm', 'gpt', 'qwen')):
        return '말씀하신 LLM 사용 요구사항을 반영했습니다.'
    return '말씀하신 내용을 요구사항에 반영했습니다.'


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
        return _latest_requirement_confirmation(user_text)
    return '말씀하신 ' + ' · '.join(facts[:7]) + ' 요구사항을 반영했습니다.'


def _normalized_reply(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').casefold()).strip()


def _is_duplicate_assistant_reply(content: str, history: list[dict], threshold: float = 0.88) -> bool:
    current = _normalized_reply(content)
    if len(current) < 20:
        return False
    recent = [
        _normalized_reply(item.get('content') or '')
        for item in (history or [])[-10:]
        if str(item.get('role') or '') == 'assistant'
    ][-4:]
    for previous in recent:
        if not previous:
            continue
        if current == previous:
            return True
        if min(len(current), len(previous)) >= 40:
            ratio = SequenceMatcher(None, current[:1600], previous[:1600]).ratio()
            if ratio >= threshold:
                return True
    return False


def _attachment_ack_already_sent(history: list[dict]) -> bool:
    markers = (
        '첨부 파일의 구조와 주요 내용을 분석',
        '첨부 파일 분석 내용을',
        '첨부 context에 반영',
        '첨부 파일에서 파악한',
    )
    for item in history or []:
        if str(item.get('role') or '') != 'assistant':
            continue
        text = str(item.get('content') or '').casefold()
        if any(marker.casefold() in text for marker in markers):
            return True
    return False


def _fast_interview_message(user_text: str, history: list[dict], requirement_context: str = "") -> str:
    next_question = _next_user_decision_question(user_text, history, requirement_context)
    if not next_question:
        return (
            _latest_requirement_confirmation(user_text)
            + '\n\n요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다.'
        )
    return _latest_requirement_confirmation(user_text) + '\n\n' + next_question


def _is_fast_interview_turn(user_text: str, history: list[dict], fresh_attachment_context: str = "") -> bool:
    text = str(user_text or '').strip()
    if fresh_attachment_context.strip():
        return False
    if not text or len(text) > 420:
        return False
    lowered = text.casefold()
    meta_interview_question = any(token in lowered for token in (
        '추가로 필요한', '더 필요한', '다음 질문', '다음으로', '또 필요한', '추가 사항'
    ))
    if not meta_interview_question:
        if '?' in text or '？' in text:
            return False
        if any(token in lowered for token in (
            '왜 ', '어떻게 ', '차이가', '비교해', '추천해', '무엇이 좋', '어떤 것이 좋',
            '적합한가', '설명해', '가능한가', '장단점'
        )):
            return False
    user_turns = sum(1 for item in history or [] if str(item.get('role') or '') == 'user')
    assistant_turns = sum(1 for item in history or [] if str(item.get('role') or '') == 'assistant')
    # 최초 목적 설명은 모델 분석을 허용하고, 이후의 짧은 인터뷰 턴부터
    # 결정적 Fast Path를 사용합니다.
    return user_turns >= 1 and assistant_turns >= 1


def apply_question_quality_gate(
    content: str,
    user_text: str,
    history: list[dict],
    requirement_context: str = "",
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
    if _is_duplicate_assistant_reply(answer, history):
        reasons.append('duplicate_assistant_reply')

    # A non-completion interview turn must contain one clear question.
    if _question_count(answer) == 0:
        reasons.append('missing_question')

    if not reasons:
        return answer, {'passed': True, 'replaced': False, 'reasons': []}

    next_question = _next_user_decision_question(user_text, history, requirement_context)
    if next_question:
        replacement = _technical_confirmation(user_text, history) + '\n\n' + next_question
    else:
        replacement = (
            _technical_confirmation(user_text, history)
            + '\n\n요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다.'
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


def _safe_attachment_fallback(user_text: str, history: list[dict], requirement_context: str = "") -> str:
    acknowledgement = (
        '첨부 파일 분석 내용을 요구사항 Context에 반영했습니다.'
        if not _attachment_ack_already_sent(history)
        else _latest_requirement_confirmation(user_text)
    )
    next_question = _next_user_decision_question(user_text, history, requirement_context)
    if not next_question:
        return acknowledgement + '\n\n요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다.'
    return acknowledgement + '\n\n' + next_question


async def next_interview_message(
    user_text: str,
    history: list[dict],
    provider: str | None = None,
    attachment_context: str = "",
    attachment_memory: str = "",
    agent_specialization: str = "",
) -> str:
    fresh_attachment_block = str(attachment_context or "").strip()
    cached_requirement_context = str(attachment_memory or "").strip()
    specialization = str(agent_specialization or "").strip().upper()
    specialization_context = ""
    if specialization == "BLENDER_3D":
        specialization_context = (
            "[선택된 Agent 전문 유형: BLENDER_3D]\n"
            "사용자는 Blender MCP 기반 3D 제작 Agent를 만들고 있습니다. Blender MCP의 구체 Tool 호출 순서, "
            "LangGraph 분기, Scene State 내부 구현은 AgentStudio가 설계하며 사용자에게 기술 선택을 떠넘기지 않습니다. "
            "다만 3D Agent가 반드시 지원해야 할 제작 범위(모델링/재질/조명/카메라/애니메이션), 입력 참고자료, "
            "최종 산출물(.blend/GLB/FBX/OBJ/Render/Animation)처럼 사용자 의사결정이 필요한 내용이 불명확하면 "
            "한 번에 하나씩 우선 질문합니다. Viewport/Render Vision QA와 bounded repair는 기본 안전 계약으로 간주합니다."
        )
    combined_requirement_context = '\n\n'.join(
        part for part in (specialization_context, cached_requirement_context, fresh_attachment_block) if part
    )[-18_000:]

    # v5.359 Fast Interview Path: 첨부 원문을 새로 분석하는 턴이 아니고,
    # 이미 인터뷰가 시작된 짧은 사용자 답변은 LLM을 다시 호출하지 않습니다.
    # 이 경로는 요구사항 State/요약만 사용하므로 Ollama 단일 모델 환경에서도
    # 짧은 확인 대화가 수십 초씩 기다리는 현상을 피합니다.
    if _is_fast_interview_turn(user_text, history, fresh_attachment_block):
        return _fast_interview_message(user_text, history, combined_requirement_context)

    llm = model_for_task(LLMTask.REQUIREMENTS_ANALYSIS, provider)
    compact = "\n".join(f"{x['role']}: {x['content']}" for x in history[-20:])
    context_parts = []
    if specialization_context:
        context_parts.append(specialization_context)
    if cached_requirement_context:
        context_parts.append(
            '[기존 첨부 분석/요구사항 메모리]\n'
            + cached_requirement_context
            + '\n이 내용은 이미 분석된 요약입니다. 사용자에게 첨부 분석 완료 안내를 반복하지 마세요.'
        )
    if fresh_attachment_block:
        context_parts.append(
            '[이번 턴에 새로 첨부된 참고자료]\n'
            + fresh_attachment_block
            + '\n첨부 파일의 내용도 요구사항 근거로 분석하세요. 파일에 없는 내용을 임의로 만들지 마세요.'
        )
    context_block = '\n\n'.join(context_parts)
    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(
            content=(
                f"이전 대화:\n{compact}\n\n"
                f"사용자 최신 답변:\n{user_text}"
                + (f"\n\n{context_block}" if context_block else "")
            )
        )
    ]
    result = await llm.ainvoke(messages)
    content = str(result.content).strip()

    # Raw/새 첨부 Context에 대한 원문 echo만 검사합니다. 이미 정리된
    # attachment_memory를 echo detector 근거로 사용하면 매 턴 동일 fallback이
    # 발생할 수 있으므로 명확히 분리합니다.
    if fresh_attachment_block and _looks_like_attachment_echo(content, fresh_attachment_block):
        retry_messages = [
            SystemMessage(
                content=SYSTEM
                + "\n추가 보호 규칙: 방금 생성된 응답이 첨부 원문을 과도하게 복사했습니다. "
                  "코드 블록과 파일 원문은 출력하지 말고, 700자 이내 한국어로 확인 내용과 질문 하나만 답하세요."
            ),
            HumanMessage(
                content=(
                    f"이전 대화:\n{compact}\n\n"
                    f"사용자 최신 답변:\n{user_text}\n\n"
                    f"{fresh_attachment_block}\n\n"
                    "첨부 원문을 절대 재출력하지 말고 요구사항만 추론하세요."
                )
            ),
        ]
        retry = await llm.ainvoke(retry_messages)
        retry_content = str(retry.content).strip()
        content = (
            _safe_attachment_fallback(user_text, history, combined_requirement_context)
            if _looks_like_attachment_echo(retry_content, fresh_attachment_block)
            else retry_content
        )

    content, _quality_gate = apply_question_quality_gate(
        content,
        user_text,
        history,
        requirement_context=combined_requirement_context,
    )

    if _is_duplicate_assistant_reply(content, history):
        content = _fast_interview_message(user_text, history, combined_requirement_context)

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
    registry = extract_attachment_requirement_registry(text)
    coverage = registry.get('coverage') or {}
    rows = list(registry.get('requirements') or [])
    names = []
    for row in rows:
        source = str(row.get('source') or '').strip()
        if source and source not in names:
            names.append(source)
    if not names:
        names = re.findall(r'^###\s+(?:참고 파일 분석본|첨부 파일):\s*(.+)$', text, flags=re.MULTILINE)

    purpose = summary_bullets_by_category(registry, ('FUNCTIONAL', 'ORDER', 'ANALYTICS'), 4)
    functions = summary_bullets_by_category(registry, ('SEARCH', 'ORDER', 'ANALYTICS', 'FUNCTIONAL'), 7)
    data = summary_bullets_by_category(registry, ('DATA', 'DATABASE', 'CACHE'), 7)
    tech = summary_bullets_by_category(registry, ('UI', 'BACKEND', 'LLM', 'MCP_TOOL', 'DATABASE', 'CACHE', 'SEARCH'), 8)
    constraints = summary_bullets_by_category(registry, ('CONSTRAINT', 'SECURITY', 'OUTPUT', 'RUNTIME'), 8)

    def bullets(values: list[str], fallback: str) -> str:
        items = values or [fallback]
        return '\n'.join(f'- {item}' for item in items)

    source_label = ', '.join(names[:6]) if names else '선택한 참고 파일'
    requirement_count = int(coverage.get('requirement_count') or len(rows))
    return (
        '## 만들고자 하는 내용\n'
        f'- {source_label}에서 개발 요구사항 {requirement_count}개 후보를 구조적으로 추출했습니다.\n'
        + bullets(purpose[:2], '첨부 자료의 명시적 문제/목표를 기준으로 프로그램을 구성합니다.')
        + '\n\n## 핵심 기능\n'
        + bullets(functions, '핵심 기능은 추출 요구사항 목록에서 확인할 수 있습니다.')
        + '\n\n## 입력 / 데이터\n'
        + bullets(data, '첨부 자료에서 확인된 데이터/저장소 요구사항을 사용합니다.')
        + '\n\n## 기술 / 연동\n'
        + bullets(tech, '첨부 자료에서 확인된 기술/연동 단서를 사용합니다.')
        + '\n\n## 추가 확인이 필요한 항목\n'
        + bullets(constraints, '문서에 명시되지 않은 사용자 의사결정 항목만 인터뷰에서 추가 확인합니다.')
    )[:6000]

def build_attachment_requirements_display_summary(attachment_context: str) -> str:
    """Build a safe, user-visible structured summary without a second LLM call.

    The normal interview route already spends its latency budget on the next
    conversational turn.  This fast summary lets the UI show what AgentStudio
    understood from the newly attached files immediately, while the explicit
    "첨부만 먼저 분석" action can still run the richer LLM summarizer.
    """
    evidence = str(attachment_context or '').strip()
    if not evidence:
        return ''
    return _deterministic_attachment_requirements_summary(evidence)


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
    registry = extract_attachment_requirement_registry(evidence)
    registry_memory = format_requirement_registry_memory(registry, limit=12_000)
    prompt = (
        (f'기존 첨부 분석 요약:\n{previous}\n\n' if previous else '')
        + (f'AgentStudio가 구조적으로 추출한 Requirement Registry:\n{registry_memory}\n\n' if registry_memory else '')
        + '새로 첨부한 파일의 안전한 압축 분석 Context:\n'
        + evidence
        + '\n\nRequirement Registry의 명시적 항목을 누락하지 말고, 위 자료를 통합해서 사용자가 만들고자 하는 내용을 정리하세요.'
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
