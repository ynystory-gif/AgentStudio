# v5.178 Terminal Prompt Input Echo Fix

## 증상
코드 편집기 하단 xterm 터미널에서 긴 PowerShell 프롬프트를 사용하는 경우 문자 하나를 입력할 때마다 동일 프롬프트가 새 줄처럼 반복 표시되었습니다.

## 원인
프론트엔드의 로컬 명령행 편집기가 모든 printable key 입력마다 `prompt + 전체 buffer`를 다시 그렸습니다. 프로젝트 경로가 긴 프롬프트는 좁은 터미널에서 여러 행으로 wrap되며, 현재 행만 지우는 ANSI sequence로는 이전 wrapped row가 제거되지 않아 프롬프트가 누적되었습니다.

## 수정
- 일반 문자 입력이 command buffer의 끝에서 발생하면 전체 prompt를 다시 그리지 않고 새 문자만 xterm에 append합니다.
- 일반적인 끝 위치 Backspace도 전체 prompt redraw 없이 `\\b \\b`로 처리합니다.
- 명령은 이전과 동일하게 로컬 buffer에만 누적하고 Enter를 눌렀을 때만 WebSocket `command` 메시지로 Backend에 전송합니다.
- 좌우 이동 후 중간 삽입, history 등 기존 편집 기능은 기존 redraw 경로를 유지합니다.

## 기대 결과
`(.venv) PS F:\\AI\\CursorProjects\\fastapi-signup-api> python ...`처럼 프롬프트는 한 번만 표시되고 입력 문자가 같은 명령행에 이어집니다.
