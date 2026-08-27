# v5.387 FrontendAgnosticThemeAdapters

## 목적
URL/화면 캡처에서 가져온 Theme을 React 전용으로 취급하지 않고 Frontend 기술 독립적인 Design Token으로 관리합니다.

## 목록 확인
신규 Agent > UI / Layout > Theme > `적용 Frontend 목록` 버튼에서 현재 Registry를 확인합니다.
Backend API는 `GET /api/ui-themes/frontend-targets`입니다.

## 적용 원칙
- React/Next: CSS Variables + Provider/Theme object
- Vue/Nuxt: CSS Variables + plugin/composable
- Angular: CSS Custom Properties/SCSS + theme service
- Svelte/SvelteKit/Astro/HTML: CSS Variables + root layout/global style
- Streamlit/Gradio/NiceGUI: 각 Python UI의 Theme API/CSS 기능
- Blazor/Razor: CSS Variables + Layout/scoped CSS
- React Native/Expo: JS/TS theme object + StyleSheet
- Flutter: ThemeData/ColorScheme/TextTheme
- 목록 밖 Frontend: Generic Adapter

Theme은 source URL/이미지의 로고·문구·이미지를 복제하지 않고 색상·Typography·Radius·Shadow·Spacing/Layout 특성만 재사용합니다.
