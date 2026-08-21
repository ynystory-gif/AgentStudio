# v5.294 Terminal Stop + Redis Live TTL + Firestore Compact Field Fix

## 1. Terminal / Streamlit 정상 종료 상태 보강

기존에는 실행 중 명령에 `Ctrl+C`를 보내면 Backend의 `interrupted` ACK를 받은 즉시 Frontend가 명령을 idle 상태로 바꿨습니다. 실제 Streamlit/Python process가 아직 종료 중이어도 다음 `Ctrl+C`가 로컬 입력 취소로만 처리될 수 있었습니다.

이 버전은 다음처럼 동작합니다.

1. 실행 중 명령에서 `Ctrl+C` 또는 `■ 실행 정지`를 누릅니다.
2. Backend는 PowerShell 자체를 죽이지 않고 PowerShell의 foreground child process tree를 종료합니다.
3. 종료 직후 direct child를 다시 확인하고 남아 있으면 한 번 더 정리합니다.
4. Frontend의 ACK는 **종료 완료**가 아니라 **중단 신호 전달 완료**로 취급합니다.
5. 실제 `__THEANOVA_PROMPT__` marker가 돌아올 때까지 `busy + interrupting` 상태를 유지합니다.
6. 종료가 늦으면 사용자가 `Ctrl+C`/실행 정지를 다시 보낼 수 있습니다.
7. prompt가 돌아오면 그때 정상 idle 상태로 전환합니다.

## 2. Redis TTL 실시간 카운트다운

Redis Key 목록과 선택 Key 상세의 TTL은 API 조회 당시 TTL을 기준으로 클라이언트에서 매초 감소합니다.

- `No limit(-1)`은 그대로 표시
- 존재하지 않음/조회 불가(-2)는 `-` 표시
- 양수 TTL은 `58s`, `4m 12s`, `1h 3m`처럼 실시간 감소
- Key마다 `setInterval`을 만들지 않고 전체 TTL 컴포넌트가 하나의 shared clock을 구독
- 실제 Redis 값/TTL을 다시 동기화하고 싶을 때만 기존 새로고침 버튼 사용

## 3. Firestore Field 행 높이

Chromium table layout에서 Detail pane의 여유 높이가 소수의 Field row에 분배되어 각 행이 지나치게 길어질 수 있었습니다.

Field/Type/Value 표시를 content-sized CSS Grid로 변경해 각 행의 높이가 Field 값 내용만큼만 차지합니다. Map/Array 등 긴 값은 Value 셀 내부에서 최대 높이 180px 후 스크롤합니다.

## 회귀 방지

- v5.293 TypeScript 전환 기반 유지
- 기존 `App.jsx` 구조를 대규모 TSX 변환하지 않음
- Terminal persistent PowerShell session 유지
- Redis/Firestore API 계약 변경 없음
- Notebook, DB Browser, Supabase, PPT/PPTX Viewer, LLM, MCP 동작 경로 유지
