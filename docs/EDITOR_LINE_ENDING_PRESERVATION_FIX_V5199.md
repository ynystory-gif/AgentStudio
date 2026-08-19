# v5.199 Editor Line Ending Preservation Fix

- Windows에서 Monaco Editor 저장 시 CRLF가 `CRCRLF`로 중복 변환되어 줄마다 빈 줄이 생기던 문제를 수정합니다.
- 저장 전에 `CRLF`, `CR`, `LF` 입력을 내부 LF로 한 번 정규화합니다.
- 기존 파일의 실제 줄바꿈 형식을 감지하여 CRLF 파일은 CRLF, LF 파일은 LF로 다시 기록합니다.
- Python TextIO의 Windows 자동 newline 변환을 사용하지 않고 UTF-8 bytes로 직접 기록합니다.
- 기존 UTF-8 BOM 여부도 유지합니다.
- 동일 파일을 반복 저장해도 줄 수와 줄 간격이 변하지 않습니다.
