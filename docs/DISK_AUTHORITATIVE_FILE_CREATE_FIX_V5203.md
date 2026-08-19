# v5.203 Disk Authoritative File Create Fix

- 신규 파일 생성의 최종 기준을 Frontend 캐시가 아니라 실제 디스크로 통일합니다.
- Backend는 `xb` 원자적 생성으로 check-then-create race를 제거합니다.
- 동일 파일 생성 요청이 중복 도착해 첫 요청이 이미 파일을 만든 경우에는 409 대신 실제 디스크 파일 metadata를 정상 반환합니다.
- 같은 이름의 폴더가 있는 경우에만 명확한 충돌로 처리합니다.
- Frontend는 `fileCreateBusyRef`로 렌더 이전의 중복 클릭/요청까지 차단합니다.
- 외부 파일 감시의 첫 snapshot부터 디스크 목록을 다시 load하여 메모리에만 남은 ghost entry를 제거합니다.
- 생성 성공 후 실제 canonical relative path, mtime, size를 기준으로 tree/editor를 갱신합니다.
