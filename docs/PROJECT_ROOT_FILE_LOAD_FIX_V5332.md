# v5.332 Project Root File Load Fix

## 증상

프로젝트 파일 트리에는 `main.py` 등 파일이 정상 표시되지만 파일을 선택하면 Editor가 다음 오류를 표시했습니다.

`Backend HTTP 400: {"detail":"root가 필요합니다."}`

## 원인

파일 트리를 로드할 때 사용한 프로젝트 root와 Editor 파일 읽기 요청에서 사용하는 React state가 분리되어 있었습니다. 프로젝트 전환/DB 프로젝트 메타데이터 갱신 시점에 `activeWorkspaceRoot`가 일시적으로 빈 문자열이 되면 파일 트리는 이전에 정상 로드된 상태로 남아 있어도 `/api/files/read` 요청은 빈 `root`를 보낼 수 있었습니다.

## 수정

- 파일 트리를 정상 로드한 root를 `workspaceRootRef`에 보관합니다.
- `resolveWorkspaceRoot()`가 `activeWorkspaceRoot -> root -> newAgentProjectRoot -> workspaceRootRef` 순서로 유효 root를 결정합니다.
- 파일 읽기/재로드/저장/생성/rename/delete 및 PDF/PPT Viewer에서 같은 resolver를 사용합니다.
- 신규 Agent 시작 시 ref를 초기화합니다.
- 유효 root가 전혀 없으면 Backend 호출 전에 사용자 친화적 오류를 표시합니다.

## 안전성

Backend의 `root + relative_path` 경로 검증은 그대로 유지합니다. root 누락을 Backend에서 임의 추론하도록 완화하지 않았습니다.
