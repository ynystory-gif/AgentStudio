# v5.346 Project File Tree Root Binding Fix

## 문제

프로젝트 파일 트리와 PowerShell 터미널은 정상 프로젝트를 표시하지만 Editor 파일 열기 시 `프로젝트 root를 확인할 수 없습니다` 오류가 발생할 수 있었습니다. 일부 프로젝트 복원/외부 프로젝트 경로는 파일 트리를 직접 갱신해 전역 React `root` 상태와 파일 트리의 실제 root가 분리될 수 있었습니다.

## 수정

- 파일 트리 자체에 authoritative project root를 귀속합니다.
- 파일 열기 시 `tree root -> project state -> workspace ref -> active terminal root`를 사용해 안정적으로 root를 결정합니다.
- 열린 파일마다 load root를 저장해 프로젝트 전환 시 stale editor cache를 방지합니다.
- 저장/재로드/Notebook/코드 편집/Native Watcher도 같은 root 정책을 사용합니다.
- 신규 Agent 시작 시 tree/editor root cache를 명시적으로 초기화합니다.
