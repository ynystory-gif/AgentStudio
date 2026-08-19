# v5.185 Terminal Focus + Ollama Diagnostics Fix

- CODE 탭 터미널에 키보드 포커스가 있을 때 파란 테두리와 `입력 포커스` 배지를 표시합니다.
- 터미널을 다시 클릭/포커스할 때 세로 스크롤은 현재 입력 줄을 보이게 하고, 빈 프롬프트는 가로 시작 위치, 긴 입력의 끝 커서는 우측 위치를 보이게 합니다.
- Enter 직후에는 새 출력과 다음 PowerShell 프롬프트의 시작 부분을 볼 수 있도록 가로 스크롤을 왼쪽으로 복귀시키고 세로는 아래로 이동합니다.
- Ollama 연결 테스트 실패 시 `backend/logs/connection_tests` 아래에 상세 로그를 생성합니다.
- 시스템 관리자 화면에 오류 유형, 연결 URL, 포트 상태, Ollama 실행 파일, 확인 사항, 로그 파일 전체 경로와 경로 복사 버튼을 표시합니다.
- 상세 로그에는 URL/host/port, port_open, Ollama 실행 파일 탐지 결과, HTTP 상태, 예외 타입/메시지, 응답 일부와 traceback을 기록합니다.
