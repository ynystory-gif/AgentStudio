# THEANOVA AgentStudio v5.412

## High-Speed Analysis Pipeline

Agent 설계/개발 진행 전에 프로젝트 전체를 LLM이 반복 분석하지 않도록 `Incremental Cache + BM25 + AST/Import Parser + Dependency Graph + Optional PyTorch Tensor Fusion`을 통합했습니다. 관련 후보를 먼저 로컬에서 압축한 뒤 기존 Validator/LLM Workflow로 넘깁니다.

> Latest patch: **v5.412 NotebookSmoothLiveOutputRendering**




### v5.412 주요 변경
- `clear_output(wait=True)`를 Jupyter 의미 그대로 **지연 Clear**로 처리하여 현재 프레임을 먼저 지우지 않습니다.
- 다음 `display(fig)` 프레임이 도착할 때 이전 프레임을 **한 번의 상태 갱신으로 교체**해 빈 화면 Flash를 제거합니다.
- 실행 시작 시 기존 마지막 프레임을 첫 새 프레임이 준비될 때까지 유지해 초기 깜박임도 줄였습니다.
- 스트리밍 PNG는 브라우저에서 먼저 preload/decode한 뒤 `<img>`의 표시 소스를 바꾸므로 이미지 decode 사이의 순간 공백을 방지합니다.
- Backend의 `rich_outputs`도 `wait=True` 지연 Clear를 동일하게 적용해 마지막 프레임 저장 의미를 Jupyter와 맞췄습니다.
- 실행 종료 시 임시 Live Output layer를 즉시 제거하지 않고 짧은 handoff 시간을 두어 저장된 최종 출력으로 자연스럽게 전환합니다.

### v5.411 주요 변경
- Notebook `IPython.display.clear_output()` + `display(fig)` 실시간 Rich Output 스트리밍
- Matplotlib Figure를 PNG MIME bundle로 즉시 전송하여 같은 셀 출력 영역에서 프레임 교체
- 학습 중 Epoch/Loss/Accuracy/결정 경계가 실행 중 실시간 갱신
- 마지막 프레임은 `.ipynb` 출력으로 유지되어 재오픈 후에도 확인 가능
- 기존 `/python/execute`는 유지하고 Notebook은 `/python/execute/stream` NDJSON 경로 사용

### v5.410 주요 변경

- Jupyter Markdown의 `![alt](data:image/...;base64,...)` 인라인 이미지 렌더링 지원
- 긴 base64가 notebook source 여러 줄로 나뉘어 `![alt]`와 `(data:...)` 사이에 공백/줄바꿈이 생겨도 복구 렌더링
- PNG/JPEG/GIF/WebP/SVG image data URI만 허용하고 기타 data URI는 기존처럼 텍스트로 유지
- base64 payload 내부 줄바꿈/공백을 제거한 뒤 안전한 `<img>`로 표시
- 기존 `attachment:`, HTTPS 이미지, 제한된 raw `<img>` 렌더링 유지

### v5.409 주요 변경

- Notebook 상단 도구 영역을 `flex-wrap` 기반 Responsive Toolbar로 변경
- 좌우 분할처럼 Notebook 실제 가로 폭이 좁아지면 북마크/코드/Markdown/출력 버튼이 자동으로 다음 줄로 이동
- 한글 버튼이 한 글자씩 세로로 찌그러지지 않도록 `white-space: nowrap`과 비축소 정책 적용
- 브라우저 전체 폭이 아니라 각 Notebook pane 실제 폭을 기준으로 동작하도록 CSS Container Query 적용
- 760px 이하에서는 정보 영역과 작업 버튼 영역을 2행으로 분리하고, 520px 이하에서는 북마크 그룹도 자연스럽게 Wrap
- 단일 화면과 v5.408 좌우 분할 Notebook 모두 같은 Responsive 규칙 사용

### v5.408 주요 변경

- 열린 파일 탭 우클릭 메뉴에 **오른쪽으로 화면 열기 / 왼쪽으로 화면 열기** 추가
- VS Code 방식의 좌우 2분할 코드/Notebook/CSV/PDF/PPT/DB Diagram 동시 보기
- 두 화면 사이 세로 Divider 드래그로 20~80% 범위 너비 조절
- Divider 더블클릭 시 50:50 복원, 비율은 `localStorage`에 저장
- 분할 화면 Header에서 좌/우 방향 교환 및 분할 닫기
- 분할된 보조 화면도 텍스트/Notebook/CSV 편집 가능하며 활성 화면 기준 `Ctrl+S` 저장
- 분할 파일은 열린 파일 탭에 별도 표시

### v5.407 주요 변경

- 프로젝트 스캔 중복 제거: 한 분석 요청에서 동일 프로젝트를 2번 읽지 않습니다.
- 변경되지 않은 파일은 `mtime + size` Incremental Cache로 재사용합니다.
- 변경 파일은 최대 8 Worker로 병렬 인덱싱합니다.
- BM25 + Path/Symbol + Python AST/JS·TS import parser + Dependency Graph를 결합합니다.
- PyTorch 설치 시 Tensor Score Fusion, 미설치 시 Python fallback을 사용합니다.
- 1차 후보 압축은 LLM/Embedding API를 호출하지 않아 토큰 비용이 없습니다.
- `/project/high-speed-analysis/status`로 Torch/CUDA/tree-sitter/pgvector 가용 상태를 확인할 수 있습니다.
- 기존 Agent 설계/Workflow Preview/개발 분석 경로가 자동으로 이 Pipeline을 사용합니다.

## v5.404 MobileInteractiveThemeMenuPreview

- Theme 전체 미리보기의 Mobile viewport에서 데스크톱 상단 메뉴와 Sidebar를 억지로 가로 배치하지 않습니다.
- Mobile에서는 실제 `☰ 메뉴` 버튼을 Header에 표시하고 클릭하면 Theme의 normal/hover/active/submenu 규칙을 사용하는 모바일 Drawer가 열립니다.
- Header 메뉴와 Sidebar 메뉴를 모바일 Drawer 안에서 통합해 Products/Catalog 하위 메뉴 Open까지 직접 확인할 수 있습니다.
- Desktop/Tablet에서 열어 둔 submenu/user menu 상태가 Mobile로 전환될 때 남아서 겹치지 않도록 viewport 변경 시 Interaction state를 초기화합니다.
- 모바일 사용자 메뉴 popup 폭과 위치를 viewport 안으로 제한합니다.
- 기존 Desktop/Tablet Interactive Theme Preview와 외부 스타일 재현 근거 표시는 유지합니다.


## v5.405 CSV Spreadsheet Grid Viewer
- `.csv`/`.tsv` 파일을 기본적으로 Excel과 유사한 행/열 Grid로 표시합니다.
- 열 머리글(A, B, C...), 행 번호, 고정 헤더/행 번호, 셀 선택/복사, 가로·세로 스크롤을 지원합니다.
- 구분자(쉼표/TAB/세미콜론/파이프)를 자동 감지하고 quoted CSV를 처리합니다.
- `표 보기`와 `원문 편집`을 전환할 수 있어 기존 CSV 텍스트 편집 기능도 유지합니다.
- 대용량 CSV는 UI 안정성을 위해 최대 5,000행 × 200열을 Grid로 미리보고 원문 데이터는 변경하지 않습니다.
