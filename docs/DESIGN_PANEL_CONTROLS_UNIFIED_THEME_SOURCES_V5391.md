# v5.391 DesignPanelControlsUnifiedThemeSources

## Agent 설계 우측 패널

- `프로젝트 저장` / `프로젝트 로드`는 중앙 인터뷰 상단에서 제거하고 우측 `Agent 제작 진행` 카드 아래로 이동했습니다.
- 이 위치에서는 `새 프로젝트` 버튼을 표시하지 않습니다.
- 기능 관리 전체를 `Agent 제작 진행` 아래로 이동하여 `기능 추가`, `수정`, `사용 안 함`, `삭제`, `복원`을 한곳에서 처리합니다.
- `프로젝트 구성` 카드는 자체 세로 스크롤을 만들지 않습니다.
- DESIGN 우측 패널은 마우스 휠/트랙패드 스크롤을 유지하지만 고정 스크롤바는 숨겨 화면을 정리합니다.

## Theme 참고 소스 통합

`스타일 가져오기`는 URL/이미지 탭을 없애고 하나의 패널에서 동시에 입력할 수 있습니다.

- 웹사이트 URL: 선택 입력
- 화면 캡처 이미지: 선택 입력, 최대 3개
- URL만 입력: URL HTML/CSS 분석 Theme
- 이미지만 입력: 1~3개 캡처를 병합한 Theme
- URL + 이미지: CSS 의미/상태와 실제 화면 색감을 병합한 Theme

URL이 자동 분석 차단(403/429 등)되더라도 캡처 이미지가 함께 있으면 이미지 기반 Theme 저장을 계속하고 경고를 표시합니다.

## Menu / Navigation 상태 Theme

URL CSS에서 Menu/Navigation/Sidebar/Header 관련 selector를 찾아 다음 상태를 Design Token의 `component_rules.menu`에 저장합니다.

- `normal`
- `hover`
- `active`

캡처 이미지에서는 화면의 상단/좌측 Navigation 가능 영역 색상을 추가 분석하여 메뉴 기본/강조 상태를 보완합니다. 여러 캡처가 있으면 상태 후보를 통합합니다.

저장된 Menu 상태 규칙은 React/TypeScript에 고정하지 않고 Frontend Theme Adapter Registry의 모든 대상과 Generic Adapter에 전달되어 해당 Framework의 native styling 방식으로 생성됩니다.
