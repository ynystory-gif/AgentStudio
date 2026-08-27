# v5.371 Global Command Palette / Agent Work Center / Help Center / Notebook Root Fix

## Global Command Palette
- 상단 명령 검색과 Ctrl+K 연결
- 명령 검색, 키보드 탐색, Enter 실행, Esc 닫기
- 주요 Workspace/Project/PPT/Find/DB/Recovery 명령 등록

## Agent Work Center
- 상단 ♢ 버튼 연결
- 현재/최근/실패 Job, 개발/Workflow 진행률 표시
- 실패 Checkpoint가 있으면 재개발 시작 제공

## Help Center
- 상단 ? 버튼 연결
- 검색 가능한 AgentStudio 사용 방법과 문제 해결 가이드 제공

## Notebook Workspace Root
- activeWorkspaceRoot만 의존하지 않고 열린 Editor/File Tree/Workspace/Terminal Root를 순서대로 해석
- 프로젝트 셀렉터가 비어 있어도 프로젝트 파일 트리에서 열린 Notebook은 정상 셀 실행
