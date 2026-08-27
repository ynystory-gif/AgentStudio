# v5.374 PDF Search Dedup & Page Navigation Fix

## 문제
- PDF 통합 찾기 결과에 동일한 문장이 여러 번 표시될 수 있었습니다.
- pypdf의 추출 line/column은 PDF의 실제 화면 좌표가 아닌데 UI에서 시각적 위치처럼 표시했습니다.
- 결과 클릭 시 `#page`와 `#search`를 동시에 Chromium PDF Viewer에 전달해 내장 검색이 지정 페이지를 덮어쓰면서 여러 결과가 같은 위치로 이동할 수 있었습니다.

## 수정
1. PDF는 `layout` 추출을 우선 사용하고 실패 시 일반 추출로 fallback합니다.
2. 같은 페이지에서 동일한 텍스트/컬럼으로 중복 추출된 text-layer 결과를 제거합니다.
3. 검색 결과 snippet은 매치 줄과 인접 줄을 조합한 문맥으로 표시합니다.
4. PDF 결과 위치는 `페이지 N`을 authoritative location으로 표시하고 추출 line/column을 시각적 좌표처럼 노출하지 않습니다.
5. 결과 클릭 시 PDF Viewer에는 `#page=N`만 전달합니다. `#search`는 page navigation과 동시에 전달하지 않습니다.
6. 현재 선택한 결과의 매치 문장을 PDF toolbar에 표시하여 사용자가 어느 결과를 선택했는지 확인할 수 있습니다.
7. 중복 제거 건수를 검색 Summary에 표시합니다.

## 한계
브라우저 내장 Chromium PDF Viewer는 외부 React 코드에서 PDF 내부 텍스트 좌표를 직접 제어하거나 임의 highlight할 수 없습니다. AgentStudio 통합 찾기는 정확한 페이지로 이동하고 매치 문맥을 표시하며, 페이지 안에서 단어 highlight가 필요하면 브라우저 PDF Viewer의 Ctrl+F를 사용할 수 있습니다.
