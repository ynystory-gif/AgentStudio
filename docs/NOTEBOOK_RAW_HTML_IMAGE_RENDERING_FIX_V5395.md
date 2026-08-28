# v5.395 Notebook Raw HTML Image Rendering Fix

## 문제
Notebook Markdown Cell에 `<img src="https://..." />`가 들어 있으면 기존 전용 Markdown Renderer가 raw HTML을 텍스트로 취급해 태그 자체가 화면에 노출되었습니다.

## 수정
- `<img>`만 제한적으로 파싱해 React `<img>`로 렌더링합니다.
- `src`는 `http://`, `https://`, Notebook `attachment:`, 제한된 `data:image/...`만 허용합니다.
- `alt`, `title`만 반영하며 이벤트 속성이나 임의 HTML은 실행하지 않습니다.
- 기존 Markdown 이미지와 attachment 렌더링도 공통 안전 이미지 컴포넌트를 사용합니다.
- 원격 이미지 실패 시 URL 링크가 포함된 오류 안내를 표시합니다.
