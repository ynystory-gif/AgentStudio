# v5.187 Terminal Caret Scroll Visibility Fix

- 터미널에서 문자를 입력할 때 가로 스크롤이 무조건 오른쪽 끝으로 이동하던 동작을 제거했습니다.
- 긴 prompt/command는 기존 가로 스크롤 기능을 유지하되, 자동 이동은 현재 caret를 화면에 보여 주는 데 필요한 최소 거리만 이동합니다.
- xterm 내부 viewport의 가로 스크롤을 비활성화하고 외부 terminal wrapper 하나만 가로 스크롤을 담당하도록 하여 이중 스크롤/빈 화면 문제를 방지했습니다.
- 프로젝트 로딩, 기존 터미널 선택, 새 PowerShell prompt 표시 시 현재 prompt/caret가 보이는 위치로 자동 정렬합니다.
- 터미널 상단의 `실행 중` 상태 pill을 제거했습니다. 종료된 세션에는 기존 `다시 시작` 버튼만 표시합니다.
