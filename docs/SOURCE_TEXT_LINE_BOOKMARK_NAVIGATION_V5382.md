# v5.382 SourceTextLineBookmarkNavigation

## 목적
- Notebook에서 북마크를 추가할 클릭 위치를 찾기 어려운 문제를 해결한다.
- Notebook뿐 아니라 일반 소스/텍스트 파일에서도 같은 북마크 탐색 UX를 제공한다.

## 변경
- Notebook 상단 `🔖 현재 줄` 버튼 추가.
- Notebook 줄 번호/glyph/line-decoration gutter 클릭 모두 북마크 토글.
- 일반 Monaco Source/Text Editor에 glyph margin, 줄 북마크 decoration, 이전/다음 탐색, 전체 해제 추가.
- 프로젝트+파일 경로 단위 localStorage 영속화.
- PDF/Presentation/DB Diagram/Binary Viewer 제외.
