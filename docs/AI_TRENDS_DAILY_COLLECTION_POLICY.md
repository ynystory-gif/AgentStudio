# AI Trends 일 단위 수집 정책

기준 시간대: `Asia/Seoul`

## 기본 동작

메인페이지 진입 시 오늘 날짜의 AI Trends Cache를 먼저 확인한다.

- 오늘 Cache 있음 → 외부 Hugging Face API를 호출하지 않고 저장된 결과를 즉시 표시
- 오늘 Cache 없음 → 최근 7일 데이터를 수집하고 오늘 날짜 Cache로 저장한 뒤 표시
- AgentStudio 재실행 / 메인페이지 재진입 → 같은 날이면 기존 오늘 데이터 사용
- 날짜가 바뀜 → 새 날짜 Cache가 없으므로 그날 최초 한 번 수집

최근 7일은 오늘을 포함한 7개 날짜이므로 `from = today - 6 days`, `to = today`로 계산한다.

## 새로고침

메인 화면의 `새로고침`은 오늘 Cache를 다시 읽어 화면을 갱신한다.
일반 새로고침으로 외부 Hugging Face를 반복 호출하지 않는다.
강제 재수집은 향후 관리자 기능으로 분리한다.

## 부분 실패

Models / Papers / News / Spaces / Datasets는 독립 상태를 가진다.
한 카테고리 오류가 전체 메인페이지를 실패시키지 않는다.
오늘 수집 결과 자체는 저장한다.
