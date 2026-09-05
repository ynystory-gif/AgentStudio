from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.rag.constants import SENSITIVE_FILE_NAMES, SENSITIVE_PARTS


@dataclass(slots=True)
class SafetyScanResult:
    level: str
    warnings: list[str]
    redacted_text: str
    redaction_count: int
    prompt_injection_count: int
    instruction_like_count: int
    exfiltration_count: int
    risk_score: int
    risk_categories: list[str]
    quarantined: bool


_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ('Private Key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', re.IGNORECASE)),
    ('OpenAI/API Key', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b')),
    ('GitHub Token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b', re.IGNORECASE)),
    ('AWS Access Key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('Bearer/JWT Token', re.compile(r'(?i)\b(?:bearer\s+)?eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b')),
    ('Secret Assignment', re.compile(r'(?im)\b(?:api[_-]?key|password|passwd|secret|access[_-]?token|refresh[_-]?token|client[_-]?secret)\b\s*[:=]\s*["\']?[^\s"\']{8,}["\']?')),
    ('Korean Resident ID', re.compile(r'\b\d{6}-[1-4]\d{6}\b')),
]

_PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?i)ignore\s+(?:all\s+)?previous\s+instructions?'),
    re.compile(r'(?i)ignore\s+(?:the\s+)?system\s+prompt'),
    re.compile(r'(?i)reveal\s+(?:the\s+)?system\s+prompt'),
    re.compile(r'(?i)(?:show|print|expose|leak)\s+(?:the\s+)?(?:system|developer)\s+(?:prompt|message|instructions?)'),
    re.compile(r'(?i)you\s+are\s+now\s+(?:in\s+)?(?:developer|system|admin)\s+mode'),
    re.compile(r'이전\s*(?:모든\s*)?지시(?:사항)?를?\s*무시', re.IGNORECASE),
    re.compile(r'시스템\s*프롬프트(?:를|를\s*)?(?:출력|공개|무시|노출)', re.IGNORECASE),
    re.compile(r'개발자\s*(?:메시지|지시)(?:를|를\s*)?(?:출력|공개|무시|노출)', re.IGNORECASE),
]

_INSTRUCTION_LIKE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?im)^\s*(?:system|developer|assistant|tool)\s*:\s+'),
    re.compile(r'(?i)follow\s+these\s+instructions\s+exactly'),
    re.compile(r'(?i)do\s+not\s+tell\s+the\s+user'),
    re.compile(r'(?i)override\s+(?:all\s+)?(?:rules|policies|instructions)'),
    re.compile(r'(?i)jailbreak|DAN\s+mode'),
    re.compile(r'(?i)<\|(?:system|assistant|developer)\|>'),
    re.compile(r'(?i)\[INST\]|<<SYS>>|<system>'),
]

_EXFILTRATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?i)(?:send|upload|post|exfiltrate)\s+(?:the\s+)?(?:secret|token|password|credential|api\s*key)'),
    re.compile(r'(?i)(?:curl|wget|invoke-webrequest)\b[^\n]{0,160}(?:token|secret|password|credential)'),
    re.compile(r'(?i)외부로\s*(?:전송|업로드).*?(?:비밀번호|토큰|키|자격증명)'),
]


def _redact(pattern: re.Pattern[str], text: str, placeholder: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return placeholder

    return pattern.sub(repl, text), count


def scan_knowledge_text(path: Path, text: str) -> SafetyScanResult:
    warnings: list[str] = []
    categories: list[str] = []
    redacted = str(text or '')
    redaction_count = 0
    prompt_injection_count = 0
    instruction_like_count = 0
    exfiltration_count = 0

    name_lower = path.name.lower()
    parts_lower = {part.lower() for part in path.parts}
    sensitive_name = name_lower in SENSITIVE_FILE_NAMES or name_lower.startswith('.env')
    sensitive_path = bool(parts_lower & SENSITIVE_PARTS)
    if sensitive_name:
        warnings.append('민감 설정/인증 파일명입니다. 원문 값은 Indexing 전에 마스킹합니다.')
        categories.append('SENSITIVE_FILE')
    if sensitive_path:
        warnings.append('build/node_modules/.git/venv 등 RAG 비추천 경로가 포함되어 있습니다.')
        categories.append('EXCLUDED_PATH')

    for label, pattern in _SECRET_PATTERNS:
        redacted, count = _redact(pattern, redacted, f'[RAG_REDACTED:{label}]')
        if count:
            warnings.append(f'{label} 패턴 {count}건을 감지하여 마스킹했습니다.')
            redaction_count += count
            if 'SECRET' not in categories:
                categories.append('SECRET')

    for pattern in _PROMPT_INJECTION_PATTERNS:
        redacted, count = _redact(pattern, redacted, '[RAG_PROMPT_INJECTION_PATTERN_REDACTED]')
        prompt_injection_count += count
    if prompt_injection_count:
        warnings.append(f'Prompt Injection 직접 패턴 {prompt_injection_count}건을 감지하여 마스킹했습니다.')
        categories.append('PROMPT_INJECTION')

    for pattern in _INSTRUCTION_LIKE_PATTERNS:
        _, count = _redact(pattern, redacted, '[RAG_INSTRUCTION_LIKE_PATTERN]')
        instruction_like_count += count
    if instruction_like_count:
        warnings.append(f'문서가 LLM 지시문처럼 동작할 수 있는 패턴 {instruction_like_count}건을 감지했습니다. 검색 Context에서는 비신뢰 데이터로 취급합니다.')
        categories.append('INSTRUCTION_LIKE')

    for pattern in _EXFILTRATION_PATTERNS:
        redacted, count = _redact(pattern, redacted, '[RAG_EXFILTRATION_PATTERN_REDACTED]')
        exfiltration_count += count
    if exfiltration_count:
        warnings.append(f'Secret/자격증명 외부 전송을 유도하는 패턴 {exfiltration_count}건을 감지하여 마스킹했습니다.')
        categories.append('EXFILTRATION')

    # Risk scoring is intentionally conservative: normal security documentation may mention
    # one suspicious sentence. Quarantine only when multiple independent malicious signals
    # exist, or when prompt-injection and exfiltration signals appear together.
    risk_score = min(100, redaction_count * 18 + prompt_injection_count * 24 + instruction_like_count * 12 + exfiltration_count * 32 + (25 if sensitive_name else 0) + (8 if sensitive_path else 0))
    quarantined = bool(
        (prompt_injection_count >= 2 and instruction_like_count >= 1)
        or (prompt_injection_count >= 1 and exfiltration_count >= 1)
        or exfiltration_count >= 2
        or risk_score >= 80
    )
    if quarantined:
        warnings.append('Knowledge Safety 위험도가 높아 자동 Indexing 대상에서 격리(Quarantine)합니다. 검토 후 원본을 정리하거나 별도 승인 정책을 적용하세요.')
        categories.append('QUARANTINE')

    if quarantined or redaction_count or sensitive_name:
        level = 'HIGH'
    elif prompt_injection_count or instruction_like_count or exfiltration_count or warnings:
        level = 'MEDIUM'
    else:
        level = 'LOW'

    return SafetyScanResult(
        level=level,
        warnings=warnings,
        redacted_text=redacted,
        redaction_count=redaction_count,
        prompt_injection_count=prompt_injection_count,
        instruction_like_count=instruction_like_count,
        exfiltration_count=exfiltration_count,
        risk_score=risk_score,
        risk_categories=list(dict.fromkeys(categories)),
        quarantined=quarantined,
    )
