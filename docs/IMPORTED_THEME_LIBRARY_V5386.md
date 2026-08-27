# v5.386 Imported Theme Library

## 목적
레이아웃 갤러리의 Theme을 시스템 기본 Light/Dark/Auto뿐 아니라 사용자가 참고 URL 또는 화면 캡처에서 추출한 Design Token으로 확장합니다.

## 흐름
URL 또는 Screenshot -> Style 분석 -> Design Token -> PostgreSQL ui_themes -> Theme Select -> Layout Preview -> Agent Generation

## 저장 정보
- colors / typography / radius / shadow / spacing
- component_rules (button/card/input/header/sidebar)
- layout_rules
- source_type / source_url or file label / preview colors

## 생성 규칙
custom Theme 선택 시 confirmed_requirements.ui_layout 안의 theme_id, theme_name, theme_tokens, theme_component_rules, theme_layout_rules를 생성 Prompt의 UI 기준으로 사용합니다. React/TypeScript에서는 CSS Variables 또는 Theme Provider를 통해 공통 컴포넌트에 일관되게 적용합니다.

## 안전
참조 사이트의 로고, 문구, 이미지, 고유 콘텐츠를 복제하지 않습니다. URL fetch는 localhost/사설망/비표준 포트를 차단합니다.
