# THEANOVA AgentStudio v5.497 — PII Privacy Coding Style

## 변경 내용

업로드된 `2-1. 개인정보_보호_1_PII_마스킹_정답완성.ipynb`의 개인정보 탐지·마스킹·검증 흐름을 분석해 운영형 Agent 생성에 필요한 Privacy 규칙만 Coding Style Registry에 반영했습니다.

- 기존 사용자 코딩 스타일 33개 유지 + 개인정보 전용 7개 추가 = 40개 기본 ON
- Registry `2.1 → 2.2`, `CS-178 ~ CS-184` 추가
- PII Processing Boundary
- Content + Metadata Dual Sanitization
- Fail-closed Sensitive Data Processing
- Raw / Sanitized Data Lifecycle Separation
- PII-safe Logging & Audit
- PII Policy Versioning & Data Minimization
- PII Detection False Negative / False Positive Regression Test
- CS-159 Metadata 보존의 Privacy 우선순위 강화
- CS-176 Retrieval Observability의 PII/Secret 원문 로그 금지 강화

## 적용 범위

Agent 생성, 기존 Agent 수정, 테스트 실패 Repair, 실패 지점 재개발 Prompt의 `design_bundle.user_coding_style`에 동일하게 적용됩니다. 개인정보/PII/마스킹/비식별화/Sanitization 관련 요청에서는 Coding Rule Selector가 CS-178~CS-184를 자동 선택합니다.
