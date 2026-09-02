## v5.483 · Coding Style Polish / Live Transcript Provisional Replacement

- 기준 버전: v5.482. 기존 Agent Creator/Editor, DB Resource, 메모, Codex, Notebook, faster-whisper 기능을 증분 유지합니다.
- 코딩 스타일 설정을 화면 우측 고정 오버레이 카드로 정리해 좁은 제작 패널에서 세로 글자/압축 표시가 발생하지 않도록 했습니다.
- 실시간 Transcript 헤더에 `요약정리` 버튼을 배치하고 현재까지 수집된 Transcript를 LLM으로 정리합니다.
- faster-whisper `partial` 이벤트를 임시 Segment(시작/종료 시간 포함)로 즉시 UI에 반영합니다.
- 확정 전 문장은 `수집 중`, 실시간 확정 문장은 `수집됨`, 종료 후 정밀 보정 문장은 `보정 완료`로 구분합니다.
- 정밀 보정 결과 수신 시 해당 녹음 시간 범위를 기준으로 기존 실시간 구간을 교체합니다.
- 처리 상태는 `수집 중 → 보정 중 → 완료` 흐름으로 항상 확인할 수 있습니다.
