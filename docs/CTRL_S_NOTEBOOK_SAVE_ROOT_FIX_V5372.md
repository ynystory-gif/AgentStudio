# v5.372 Ctrl+S Notebook Save Root Fix

## 문제
상단 프로젝트 선택이 비어 있는 상태에서 프로젝트 파일 트리로 `.ipynb`를 열면 Notebook 실행은 가능하지만 `Ctrl+S` 저장 단축키가 `root` 상태값을 요구해 저장되지 않았습니다.

## 수정
- Ctrl+S/ Ctrl+Shift+S 단축키에서 상단 `root` 의존성 제거
- 현재 Editor가 기억하는 Root와 File Tree Root를 우선 사용
- Notebook 직렬화 결과를 즉시 Ref에 반영하여 마지막 키 입력까지 저장
- 저장 성공/실패 상태와 터미널 로그 제공

## 저장 Root 우선순위
1. 열린 파일의 `editorFileRoot`
2. `fileTreeRoot`
3. `workspaceRoot`
4. 활성 Terminal Root

## 완료 기준
- 상단 프로젝트가 `프로젝트 선택`이어도 파일 트리에서 연 `.ipynb`에서 Ctrl+S 저장 가능
- Dirty 표시가 저장 후 해제
- 재로드 후 마지막 수정 내용 유지
