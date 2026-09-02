# PII Masking Notebook → AgentStudio coding-style interpretation

Source: `2-1. 개인정보_보호_1_PII_마스킹_정답완성.ipynb`

- Notebook structure: 47 cells (25 code, 22 markdown).
- Demonstrates regex-based detection for email, phone, resident number and account-like patterns with separate mask tokens.
- Sanitizes both `Document.page_content` and sensitive metadata keys; removed metadata field names are kept without copying the original sensitive values.
- `validate_document_safe()` re-checks sanitized documents and `prepare_documents_for_index()` blocks indexing when PII remains.
- Quality cases explicitly show false negatives for format variants and a false positive where an order-like identifier matches an account pattern.
- Audit/report examples return source, removed field names, index readiness and remaining PII types without returning the original PII values.

AgentStudio interpretation:
- Do not copy the exact regex patterns as a universal privacy policy.
- Promote the pipeline principles: privacy boundary before external processing, content+metadata sanitization, post-sanitization validation, fail-closed, raw/sanitized lifecycle separation, PII-safe observability, policy versioning/data minimization, and false-positive/false-negative regression tests.
