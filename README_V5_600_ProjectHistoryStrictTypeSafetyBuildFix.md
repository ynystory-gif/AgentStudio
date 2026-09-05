# THEANOVA AgentStudio v5.600 — Project History Strict Type Safety Build Fix

v5.599의 계정별 DB Profile, 프로젝트별 설정 저장, RAG/Agent 설정 이력 정보 기능을 그대로 유지하면서 Windows SYSTEM_ADMIN 전체 Frontend Build에서 확인된 TypeScript strict 오류를 수정한다.

## 실행 실패 원인

사용자 Windows 환경의 `npm run build`는 Frontend Contract를 모두 통과한 뒤 `tsc -b`에서 다음 오류로 중단됐다.

```text
src/features/history/ProjectHistoryPanel.tsx(49,49):
TS2532: Object is possibly 'undefined'.
```

원인은 `noUncheckedIndexedAccess: true` 설정에서 다음 코드가 배열 첫 항목의 존재를 타입 수준에서 보장하지 못했기 때문이다.

```tsx
if (next.length && !selectedId) setSelectedId(next[0].id)
```

## 수정

```tsx
const firstItem = next[0]
if (firstItem && !selectedId) setSelectedId(firstItem.id)
```

이 방식은 배열 첫 항목을 먼저 변수로 받고 존재 여부를 확인한 뒤 접근하므로 TypeScript strict 설정에서 안전하다.

## 유지 기능

- 계정 공통 DB 연결 Profile
- 프로젝트별 DB/Runtime/UI/Tool/Prompt/RAG 설정 저장
- RAG Studio 오른쪽 `이력 정보` 탭
- 변경 전/후 JSON 상세 Diff
- 모든 신규 DB 테이블의 `{logical_table_name}_id` PK 정책
- Secret/Password/Token 평문 DB 저장 금지

## 회귀 방지

검증 스크립트는 ProjectHistoryPanel에서 `next[0].id` 같은 unsafe 배열 인덱스 직접 속성 접근이 다시 들어오지 않는지 검사한다.
