# v5.121 Agent 설계 인터뷰 스크롤/입력창 고정

Agent 설계 인터뷰 화면의 가운데 열을 독립된 3단 구조로 고정합니다.

```text
[상단 인터뷰 헤더]
        고정
----------------
[대화 메시지 영역]
      내부 스크롤
----------------
[답변 입력창]
        고정
```

변경 사항:
- `builder-shell`이 viewport 높이를 넘지 않도록 `overflow:hidden`
- `builder-chat`에 `minmax(0,1fr)` 적용
- `builder-messages`만 `overflow-y:auto`
- `builder-input`은 항상 하단에 유지
- 대화/응답이 추가되면 가장 최근 메시지로 자동 스크롤
- 좌측 단계와 우측 프로젝트 구성은 각각 독립 스크롤
- 낮은 화면에서도 입력창을 보존하도록 반응형 높이 조정
