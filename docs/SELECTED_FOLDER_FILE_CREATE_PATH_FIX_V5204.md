# v5.204 Selected Folder File Create Path Fix

- 프로젝트 파일 트리에서 선택한 폴더를 신규 파일/폴더 생성 기준 경로로 사용합니다.
- Windows Backend가 반환한 `src\rag`와 UI tree의 `src/rag` 경로 구분자 차이를 canonical `/` 형식으로 통일합니다.
- `src/rag` 폴더를 선택하고 `rag.service.ts`를 생성하면 실제 디스크에도 `src/rag/rag.service.ts`로 생성됩니다.
- 선택 항목이 파일이면 해당 파일의 부모 폴더를 생성 기준으로 사용합니다.
- Backend `/files`, `/folders` 응답도 POSIX relative path로 통일하여 Windows/Unix 환경에서 동일하게 비교합니다.
