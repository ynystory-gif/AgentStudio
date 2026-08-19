# THEANOVA AgentStudio v5.163 - Failure Diagnostic Path Readability

## 수정 목적
실행 결과의 `진단 / 로그 파일` 영역에서 절대 경로가 `...`으로 생략되어 실제 저장 위치를 알기 어렵고, 실패 진단 영역의 글씨가 지나치게 작은 문제를 수정합니다.

## 변경 사항
- `진단 / 로그 파일`의 절대 경로를 말줄임표 없이 전체 표시합니다.
- 긴 Windows 경로는 영역 너비에 맞춰 자동 줄바꿈합니다.
- 각 진단/로그 파일에 `경로 복사` 버튼을 추가합니다.
- 진단 자료의 기준이 되는 `기준 프로젝트 폴더`를 별도 표시합니다.
- 기준 프로젝트 폴더에도 `경로 복사` 버튼을 제공합니다.
- 실패 진단 제목, 상태, 요약, 실패 원인, 실행 상태, Code Plan 진단, 파일명/경로 글씨 크기를 확대했습니다.
- `/workflow/diagnostics` 복구 조회와 일반 실패 진단 모두 `project_root`를 전달하도록 통일했습니다.

## 표시 예
- 기준 프로젝트 폴더: `F:\Source\repos\...\MyAgent`
- 실패 리포트: `F:\Source\repos\...\MyAgent\reports\failure_report.md`
- Agent Factory Log: `F:\Source\repos\...\MyAgent\logs\agent_factory.log`

이제 사용자는 경로의 앞/중간 부분이 잘리지 않은 상태로 전체 위치를 확인하거나 버튼으로 복사할 수 있습니다.
