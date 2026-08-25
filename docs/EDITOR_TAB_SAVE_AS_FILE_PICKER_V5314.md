# v5.314 Editor Tab Save As File Picker

- 열린 파일 탭 우클릭 메뉴에 `다른 이름으로 저장...`을 추가했습니다.
- Chrome/Edge의 native `showSaveFilePicker()`를 사용해 저장 폴더와 파일명을 직접 선택합니다.
- SQL/Python/Notebook/JSON/Markdown 등 편집 가능한 파일은 현재 Editor buffer를 저장하므로 디스크에 아직 저장하지 않은 변경도 포함됩니다.
- PDF/PPT/PPTX 읽기 전용 탭은 `/api/files/raw`에서 프로젝트 allow-list 검증 후 원본 bytes를 읽어 선택한 위치로 복사 저장합니다.
- Save As는 원본 파일 경로, 열린 탭 경로, dirty 상태를 변경하지 않습니다.
- 사용자가 파일 선택창에서 취소하면 오류로 표시하지 않습니다.
