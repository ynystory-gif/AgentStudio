# v5.381 Notebook Line Bookmark Navigation

## 목적
긴 Jupyter Notebook에서 위쪽 코드를 확인한 뒤 사용자가 수정 중이던 줄로 빠르게 돌아갈 수 있도록 Visual Studio 스타일의 줄 북마크를 제공합니다.

## 사용 방법
1. Code Cell에서 줄 번호보다 더 왼쪽의 빈 여백(glyph margin)을 클릭합니다.
2. 해당 줄에 파란 북마크 리본이 표시됩니다.
3. Notebook 상단의 `▶` 또는 `◀` 버튼으로 다음/이전 북마크로 이동합니다.
4. 다시 같은 줄의 북마크 여백을 클릭하면 북마크가 해제됩니다.
5. `모두 해제`로 현재 Notebook의 북마크를 한 번에 지울 수 있습니다.

## 저장 범위
북마크는 Notebook 원본 JSON을 수정하지 않고 `projectRoot + filePath` 기준으로 브라우저 localStorage에 저장합니다. 따라서 학습용 Notebook 파일 자체에는 불필요한 metadata가 추가되지 않습니다.
