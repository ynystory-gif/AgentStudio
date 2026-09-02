## v5.483

### v5.483
- `v5.482`를 기준으로 기존 기능을 유지하면서 코딩 스타일 설정 UI를 고정형 오버레이 카드로 정리해 좁은 우측 패널에서도 설명이 세로로 찌그러지지 않도록 개선했습니다. 이름·타입 / 구조·Notebook 그룹 설명, 전체 선택, 기본값 버튼을 정리했습니다.
- 메모 > 실시간 기록의 Transcript 헤더에 `요약정리` 버튼을 배치해 녹음 중에도 현재까지 수집된 확정+임시 텍스트를 즉시 요약할 수 있습니다.
- Backend faster-whisper의 `partial` 이벤트에 임시 구간 시작/종료 시간을 포함하고 Frontend에서 임시 Segment로 즉시 표시합니다. YouTube/화면 오디오 재생 중에도 확정 전 텍스트가 `수집 중` 상태로 Transcript 영역에 바로 반영됩니다.
- 실시간 확정 Segment는 `수집됨`, 종료 후 정밀 보정 Segment는 `보정 완료`로 표시하며, 보정 결과가 들어오면 recording time range 기준으로 기존 임시/실시간 구간을 교체합니다.
- Transcript 처리 흐름을 `수집 중 → 보정 중 → 완료` 3단계 상태로 표시합니다.

## v5.482

### v5.482
- 첨부 파일 AI 정리의 파일 칩을 실제 클릭 가능한 파일 열기 버튼으로 변경했습니다. 프로젝트 내부 첨부 파일은 중앙 코드 편집 탭에서 바로 열립니다.
- Agent Database 설정에 `PostgreSQL 스키마 생성`과 `Firestore Database 생성` 수동 실행 버튼을 추가했습니다. 실제 생성 전 확인 창을 표시하고 연결 정보만 사용 모드에서는 생성 버튼을 비활성화합니다.
- Frontend 전체 CSS/JS/TS의 명시적 글자 크기를 점검하여 13px 미만 `font-size`, `font` shorthand, inline `fontSize`를 모두 13px 이상으로 상향했습니다.
- v5.481의 코딩 스타일 UI 정리, 실시간 Transcript 요약정리, 화면/시스템 오디오 STT 보호 기능을 그대로 포함합니다.

### v5.481
- 코딩 스타일 설정 팝오버를 두 그룹으로 정리하고 우측 제작 카드의 전역 button 폭 규칙 때문에 설명 문구가 세로로 찌그러지던 레이아웃을 수정했습니다.
- 메모 > 실시간 기록에 `요약정리` 버튼을 추가해 현재 Transcript를 사용 중인 LLM 라우팅으로 요약하고 결과를 바로 확인/복사할 수 있습니다.
- 화면/시스템 오디오 STT에서 Audio Track이 없는 공유를 즉시 감지합니다. YouTube는 Chrome 탭 + 탭 오디오 공유가 켜져야 실시간 STT와 종료 후 정밀 보정이 동작합니다.

- Media Session TypeScript Undefined Guard Fix: Windows strict TypeScript build에서 Transcript 마지막 segment 접근 시 발생하던 TS2532 오류를 optional chaining guard로 수정했습니다.
- v5.479 faster-whisper 실시간 STT 기능은 그대로 유지합니다.

- 실시간 음성 텍스트 변환의 기본 엔진을 브라우저 SpeechRecognition에서 Backend `faster-whisper` PCM Streaming으로 전환했습니다.
- 마이크/화면 공유 오디오를 16kHz PCM으로 WebSocket 전송하고, VAD + Overlap Window로 구간 경계의 발화 누락을 줄입니다.
- 실시간 임시 문장과 확정 문장을 분리하며 음성 입력 레벨, STT 엔진, 마지막 인식 시각, 재연결/전송 누락 상태를 표시합니다.
- 녹음 종료 시 전체 PCM을 다시 분석하여 누락/오인식을 보정한 최종 Transcript로 교체합니다.
- `faster-whisper`를 사용할 수 없는 마이크 환경에서는 기존 Chrome SpeechRecognition을 보조 fallback으로 사용합니다.
- STT는 CPU/int8을 기본으로 하며 GPU 사용은 `AGENTSTUDIO_STT_DEVICE=cuda`를 명시한 경우에만 활성화합니다.

## v5.478

- `Agent 제작 진행` 제목 오른쪽에 기존 `변수·메소드 설명 추가`와 함께 `코딩 스타일` 설정 메뉴를 추가했습니다.
- 신규 Agent의 기본 코딩 스타일은 의미 있는 변수명, 상수 UPPER_SNAKE_CASE, Python 함수 snake_case, 클래스 PascalCase, 함수 Type Hint, 함수 Docstring, Notebook 한 셀 한 역할, 반복 로직 함수화, 실행 결과 단계 Label, Magic Number 최소화를 개별 ON/OFF 할 수 있습니다.
- 코딩 스타일 선택값은 Agent 설계 Draft/Checkpoint에 저장되어 프로젝트를 다시 열거나 재개발할 때 유지됩니다.
- 개발/재개발 시작 시 선택한 스타일 Profile을 Agent Factory `design_bundle.user_coding_style`로 전달하고 코드 생성·수정·테스트 실패 Repair·증분 재개발 Prompt에 일관되게 적용합니다.
- 함수 Docstring 항목은 `변수·메소드 설명 추가` 옵션과 연동하여 설명 주석을 원하지 않는 프로젝트에 주석을 강제로 만들지 않습니다.
- 기존 Coding Style Registry의 프로젝트/Framework별 규칙은 유지하며, 이번 사용자 Profile은 그 위에 적용되는 프로젝트별 기본 스타일 정책입니다.
