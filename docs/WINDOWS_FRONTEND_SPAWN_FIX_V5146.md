# v5.146 Windows Frontend Spawn Fix

## 오류

Windows에서 Frontend Runner가 다음 오류로 종료되었습니다.

```text
Error: spawn EINVAL
at ChildProcess.spawn
at start (...frontend_console_runner.cjs)
```

Backend/FastAPI와 PostgreSQL은 정상 시작된 상태였습니다.

## 원인

Node.js `child_process.spawn()`에서 Windows의 `npm.cmd`를 직접 실행하는 방식이
환경에 따라 `EINVAL`을 발생시킬 수 있습니다.

## 수정

Windows에서는 `npm.cmd`를 직접 spawn하지 않습니다.

다음 방식으로 변경했습니다.

```text
cmd.exe /d /s /c npm run dev -- --host 127.0.0.1 --port <PORT> --strictPort
```

`ComSpec` 환경변수가 존재하면 해당 `cmd.exe`를 사용합니다.

## 추가 보강

- spawn 자체가 동기적으로 실패해도 Runner가 죽지 않고 재시작
- Vite 비정상 종료 시 자동 재시작
- Windows 종료 시 `taskkill /PID ... /T /F`로 자식 프로세스 트리 정리
- 기존 frontend_console.log 유지
