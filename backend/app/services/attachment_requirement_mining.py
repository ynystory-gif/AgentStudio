from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("UI", ("streamlit", "react", "화면", "ui", "대시보드", "프론트", "페이지")),
    ("SEARCH", ("검색", "vector", "벡터", "유사", "semantic", "embedding", "임베딩", "retrieval", "rag")),
    ("DATABASE", ("postgresql", "postgres", "psycopg", "sql server", "mssql", "oracle", "sqlite", "db", "데이터베이스", "테이블", "erd", "pk", "fk")),
    ("CACHE", ("redis", "cache", "캐시", "ttl", "key prefix", "키 접두")),
    ("DATA", ("csv", "excel", "xlsx", "데이터", "dataset", "컬럼", "column", "online_retail")),
    ("LLM", ("openai", "ollama", "llm", "langchain", "langgraph", "gpt", "qwen", "자연어")),
    ("MCP_TOOL", ("mcp", "tool", "도구", "stdio", "streamable http", "transport")),
    ("BACKEND", ("fastapi", "uvicorn", "backend", "백엔드", "api", "endpoint", "router")),
    ("SECURITY", ("비밀번호", "password", "api key", "api 키", "apikey", "secret", "token", "권한", "인증", "로그인", "환경변수", ".env")),
    ("OUTPUT", ("리포트", "보고서", "download", "다운로드", "저장", "산출물", "output", "결과")),
    ("RUNTIME", ("docker", "windows", "linux", "실행 환경", "배포", "패키지", "설치", "환경 확인")),
    ("CONSTRAINT", ("최대", "제한", "timeout", "타임아웃", "동시", "반드시", "금지", "하지 않", "충돌", "접두사", "동일 모델", "동일 차원")),
    ("ORDER", ("주문", "재고", "invoice", "order", "cart", "상품")),
    ("ANALYTICS", ("매출", "집계", "차트", "통계", "summary", "분석")),
)

_REQUIREMENT_SIGNAL_RE = re.compile(
    r"(?i)(해야|한다|하도록|필수|반드시|금지|제한|사용|구현|제공|저장|조회|검색|처리|관리|구성|연결|"
    r"streamlit|fastapi|postgres|pgvector|redis|langchain|langgraph|openai|ollama|mcp|csv|report|리포트|"
    r"api key|password|환경변수|최대\s*\d+|\d+\s*건)"
)

_IGNORED_PREFIXES = (
    "[문서/코드 구조 및 핵심 단서]",
    "[대표 앞부분]",
    "[대표 끝부분]",
    "[명시적 요구사항 후보]",
    "[기술/구조 단서]",
)


def _clean_line(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^[-*+]\s+", "", text)
    text = re.sub(r"^\d+[.)]\s+", "", text)
    text = re.sub(r"^#{1,6}\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_sentences(value: str) -> list[str]:
    text = _clean_line(value)
    if not text:
        return []
    # Natural-language requirements are often packed into one Markdown paragraph.
    # Split only on strong sentence boundaries so identifiers/paths are preserved.
    parts = re.split(r"(?<=[.!?。])\s+|\s*[;；]\s*", text)
    result: list[str] = []
    for part in parts:
        item = part.strip(" -\t")
        if item:
            result.append(item)
    return result or [text]


def _category_for(text: str) -> str:
    lowered = str(text or "").casefold()
    scores: list[tuple[int, int, str]] = []
    for index, (category, markers) in enumerate(_CATEGORY_RULES):
        score = sum(1 for marker in markers if marker.casefold() in lowered)
        # Strong product/framework terms should not lose to incidental words like
        # "데이터" or "API" in the same requirement sentence.
        if category == "UI" and any(x in lowered for x in ("streamlit", "react")):
            score += 2
        if category == "SECURITY" and any(x in lowered for x in ("비밀번호", "password", "api 키", "api key", "secret", "token")):
            score += 2
        if score:
            scores.append((score, index, category))
    if not scores:
        return "FUNCTIONAL"
    scores.sort(key=lambda row: (-row[0], row[1]))
    return scores[0][2]


def _is_candidate(text: str, *, explicit_block: bool = False) -> bool:
    value = _clean_line(text)
    if not value or len(value) < 4:
        return False
    if value.startswith(_IGNORED_PREFIXES):
        return False
    if value.startswith(("### 참고 파일 분석본:", "- 경로:", "- 형식:", "- 원문 문자 수:", "- 용도:", "- 주의:")):
        return False
    if value in {"제공 자료", "산출물", "제약", "목표", "환경 확인", "기능", "데이터 구조", "요구사항"}:
        return False
    if value.startswith(("import ", "from ", "def ", "class ", "async def ", "SELECT ", "CREATE ", "INSERT ", "UPDATE ")):
        return False
    if value in {"```", "```python", "```py", "```sql", "```json"}:
        return False
    if explicit_block:
        return True
    return bool(_REQUIREMENT_SIGNAL_RE.search(value))


def _normalize_key(text: str) -> str:
    lowered = str(text or "").casefold()
    lowered = re.sub(r"[`*_#]", "", lowered)
    lowered = re.sub(r"[^0-9a-z가-힣_:+./-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def extract_attachment_requirement_registry(attachment_context: str, limit: int = 120) -> dict:
    """Extract a source-grounded requirement registry from the safe attachment digest.

    This is intentionally deterministic.  The LLM may summarize the registry, but
    it is not allowed to decide whether explicit Markdown requirements disappear.
    Every returned row contains its source file and, when available, notebook cell.
    """
    text = str(attachment_context or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return {
            "requirements": [],
            "coverage": {
                "mode": "DEEP_REQUIREMENT_MINING",
                "source_files": 0,
                "candidate_count": 0,
                "requirement_count": 0,
                "categories": {},
            },
        }

    requirements: list[dict] = []
    seen: set[str] = set()
    current_file = ""
    current_location = ""
    in_explicit_block = False
    source_files: set[str] = set()
    candidate_count = 0

    for raw in text.splitlines():
        stripped = str(raw or "").strip()
        file_match = re.match(r"^###\s+참고 파일 분석본:\s*(.+)$", stripped)
        if file_match:
            current_file = file_match.group(1).strip()
            source_files.add(current_file)
            current_location = ""
            in_explicit_block = False
            continue

        if stripped == "[명시적 요구사항 후보]":
            in_explicit_block = True
            continue
        if stripped.startswith("[") and stripped.endswith("]") and stripped != "[명시적 요구사항 후보]":
            in_explicit_block = False
            continue

        location_match = re.match(r"^-?\s*\[([^\]]*(?:Cell|Page|Sheet)[^\]]*)\]\s*(.*)$", stripped, re.IGNORECASE)
        if location_match:
            current_location = location_match.group(1).strip()
            stripped = location_match.group(2).strip()

        if not _is_candidate(stripped, explicit_block=in_explicit_block):
            continue

        for sentence in _split_sentences(stripped):
            if not _is_candidate(sentence, explicit_block=in_explicit_block):
                continue
            candidate_count += 1
            key = _normalize_key(sentence)
            if not key or key in seen:
                continue
            # Ignore headings that are only labels and carry no actual requirement.
            if len(sentence) <= 18 and not _REQUIREMENT_SIGNAL_RE.search(sentence):
                continue
            seen.add(key)
            requirements.append({
                "id": f"REQ-{len(requirements) + 1:03d}",
                "category": _category_for(sentence),
                "text": sentence[:700],
                "source": current_file or "첨부 파일",
                "location": current_location,
                "evidence_type": "EXPLICIT" if in_explicit_block else "STRUCTURAL",
                "confidence": 1.0 if in_explicit_block else 0.86,
                "status": "CONFIRMED" if in_explicit_block else "CANDIDATE",
            })
            if len(requirements) >= max(20, int(limit)):
                break
        if len(requirements) >= max(20, int(limit)):
            break

    category_counts = Counter(row["category"] for row in requirements)
    confirmed = sum(1 for row in requirements if row.get("status") == "CONFIRMED")
    return {
        "requirements": requirements,
        "coverage": {
            "mode": "DEEP_REQUIREMENT_MINING",
            "source_files": len(source_files),
            "candidate_count": candidate_count,
            "requirement_count": len(requirements),
            "confirmed_count": confirmed,
            "candidate_only_count": len(requirements) - confirmed,
            "categories": dict(sorted(category_counts.items())),
            "coverage_gate": "PASS" if requirements else "NO_REQUIREMENTS_FOUND",
        },
    }


def format_requirement_registry_memory(registry: dict, limit: int = 14_000) -> str:
    rows = list((registry or {}).get("requirements") or [])
    if not rows:
        return ""
    lines = ["[첨부 파일 Deep Requirement Registry]"]
    for row in rows:
        source = str(row.get("source") or "첨부 파일")
        location = str(row.get("location") or "").strip()
        where = f" / {location}" if location else ""
        lines.append(
            f"{row.get('id')} [{row.get('category')}] {row.get('text')} "
            f"(출처: {source}{where})"
        )
        if sum(len(x) + 1 for x in lines) >= limit:
            lines.append("... [Requirement Registry 메모리 예산으로 나머지 항목 생략]")
            break
    return "\n".join(lines)[:limit]


def summary_bullets_by_category(registry: dict, categories: Iterable[str], limit: int = 8) -> list[str]:
    wanted = {str(x) for x in categories}
    result: list[str] = []
    for row in (registry or {}).get("requirements") or []:
        if str(row.get("category") or "") not in wanted:
            continue
        text = str(row.get("text") or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result
