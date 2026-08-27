# v5.373 PDF Unified Find Support

## Problem
Chrome PDF Viewer의 `Ctrl+F`는 검색되지만 AgentStudio 코드 편집기 상단 `찾기`는 PDF를 바이너리로 차단했습니다.

## Fix
- 현재 파일이 PDF이면 `/files/search-text`에 `relative_path`를 전달합니다.
- Backend는 명시적으로 선택된 PDF에 한해 `pypdf`로 페이지별 텍스트를 추출합니다.
- 결과에 `page_number`, `line_number`, `column`, `snippet`을 포함합니다.
- 결과 클릭 시 PDF iframe URL의 `#page=N&search=...` fragment를 갱신하여 해당 페이지로 이동합니다.
- 프로젝트 전체 검색은 대량 PDF 추출 비용을 피하기 위해 기존 텍스트 파일 중심 정책을 유지합니다.

## Scanned PDF
추출 가능한 텍스트가 0페이지인 PDF는 OCR이 필요한 이미지 PDF일 수 있음을 사용자에게 안내합니다.
