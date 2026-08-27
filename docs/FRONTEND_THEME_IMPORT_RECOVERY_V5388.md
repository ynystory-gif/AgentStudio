# v5.388 FrontendThemeImportRecovery

## 변경 목적
- Imported Theme을 특정 React/TSX 구현에 고정하지 않고 다양한 Frontend에 적용한다.
- 지원 목록을 레이아웃 Theme 화면에서 직접 확인한다.
- 기존 DB/Supabase에서 `ui_themes` 신규 테이블 누락 때문에 URL/이미지 Theme 저장이 모두 실패하던 경로를 자동 복구한다.

## Frontend/Styling Theme Adapter
`신규 Agent > UI / Layout > Theme > 지원 Frontend/스타일 목록 보기`에서 현재 Registry를 확인한다.

대표 지원군:
- React / Next.js / Remix / Gatsby (JavaScript, TypeScript)
- Vue / Nuxt
- Angular
- Svelte / SvelteKit
- Astro / SolidJS / Preact / Qwik / Alpine.js / HTMX / HTML+CSS+JS
- Streamlit / Gradio / NiceGUI / Plotly Dash / Panel
- Django Templates / Jinja2-Flask-FastAPI Templates
- Blazor / Razor-MVC / ASP.NET WebForms
- React Native / Expo / Ionic / Flutter
- Electron / Tauri
- Tailwind / Bootstrap / MUI / Chakra / Ant Design / shadcn/ui / Mantine / Vuetify / Prime UI
- 미등록 Frontend: Generic Adapter

Theme은 공통 Design Token으로 저장하고 생성 시 확인된 Frontend의 native Theme 방식으로 변환한다. Framework + Styling 조합(예: React+Tailwind, Vue+Vuetify)도 함께 적용한다.

## URL / 이미지 Theme 오류 복구
- 현재 활성 Runtime DB에 `Base.metadata.create_all(checkfirst)`를 재적용하여 새 버전에서 추가된 테이블을 자동 생성한다.
- Local bootstrap 뒤 Supabase로 전환된 경우에도 실제 Supabase schema에서 신규 ORM 테이블을 생성한다.
- `/ui-themes` 조회/등록/삭제 시 Theme storage를 한 번 더 self-heal한다.
- Backend 404일 경우 Frontend/Backend 버전 불일치를 이해하기 쉬운 메시지로 안내한다.
- URL은 `https://` 생략 입력도 보정한다.
- 401/403/406/429로 자동 수집이 차단된 사이트는 화면 캡처 방식 사용을 명확히 안내한다.
- 외부 공개 CDN CSS도 SSRF 검증 후 Theme 분석에 사용할 수 있다.
- 이미지 분석은 25MB 제한과 Canvas 사용 가능 여부를 검사한다.
