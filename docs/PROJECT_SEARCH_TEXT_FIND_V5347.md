# v5.347 Project Search & Text Find

## 목표

코드 편집 Workspace에서 VS Code처럼 프로젝트 파일과 텍스트를 빠르게 찾습니다.

## 기능

- 우측 `프로젝트 파일` 탭에 파일명/상대경로 즉시 검색
- 검색 중에는 일치 파일의 부모 폴더를 자동 펼침
- 본문 Editor에 `현재 파일 찾기`와 `프로젝트 텍스트 찾기` 제공
- 현재 파일 찾기는 저장 전 Editor 메모리 내용까지 검색
- 프로젝트 텍스트 찾기는 사용자가 실행할 때만 Backend 온디맨드 검색
- `.git`, `.venv`, `node_modules`, 캐시 폴더는 검색에서 제외
- Jupyter Notebook은 JSON metadata/output이 아니라 Code/Markdown/Raw Cell source만 검색
- 검색 결과 클릭 시 해당 파일/라인으로 이동하며 Notebook은 해당 Cell로 이동
- 프로젝트 전체 검색은 파일당 4 MiB, 결과 300개(Frontend 기본) 안전 제한

## 디스크 I/O 정책

검색을 위한 백그라운드 polling은 추가하지 않습니다. 프로젝트 파일명 검색은 이미 메모리에 로드된 파일 목록을 필터링하며, 프로젝트 전체 텍스트 검색은 사용자가 `찾기`를 실행할 때만 디스크를 읽습니다.
