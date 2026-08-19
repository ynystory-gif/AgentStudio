# Coding Rule Governance

## 목적

새로운 교육자료/코딩스타일이 들어올 때 무조건 새 규칙 ID를 추가하지 않습니다.

각 후보 규칙을 기존 Registry와 비교하여 다음 중 하나로 판정합니다.

- `new` : 의미상 새로운 규칙
- `strengthen` : 기존 규칙을 더 구체화하거나 강하게 적용
- `merge` : 기존 규칙과 사실상 동일하므로 병합
- `conditional` : 특정 기술/상황에만 적용
- `exclude` : 교육 설명/예시이므로 규칙에서 제외

## 우선순위

기본 우선순위:

1. security
2. correctness
3. architecture
4. maintainability
5. testing
6. observability
7. performance
8. style
9. convenience

Level 우선순위:

- required
- recommended
- conditional

예:

보안 규칙:
`API Key를 코드에 직접 작성하지 않는다`

편의성 규칙:
`설정을 코드 상단에서 빠르게 수정할 수 있도록 한다`

두 규칙이 충돌하면 보안 규칙을 우선합니다.

## API

- `GET /api/coding-style/policy`
- `POST /api/coding-style/governance`

Analyzer 결과에는 이제 `governance` 판정 결과가 포함됩니다.
