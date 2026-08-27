from __future__ import annotations

from copy import deepcopy

# v5.388: Imported Theme is stored as framework-neutral design tokens.
# Generator adapters convert the same tokens to the confirmed frontend stack.
FRONTEND_THEME_TARGETS: list[dict] = [
    {"id": "react_js", "label": "React + JavaScript", "group": "React", "language": "JavaScript", "keywords": ["react", "jsx"], "strategy": "CSS Variables + React Theme Provider/Context", "entries": ["App.jsx", "main.jsx"]},
    {"id": "react_ts", "label": "React + TypeScript", "group": "React", "language": "TypeScript", "keywords": ["react", "typescript", "tsx", "타입스크립트"], "strategy": "CSS Variables + typed Theme Provider/Context", "entries": ["App.tsx", "main.tsx"]},
    {"id": "next_js", "label": "Next.js + JavaScript", "group": "React", "language": "JavaScript", "keywords": ["next.js", "nextjs", "next js"], "strategy": "global.css CSS Variables + layout/provider", "entries": ["app/layout.js", "pages/_app.js"]},
    {"id": "next_ts", "label": "Next.js + TypeScript", "group": "React", "language": "TypeScript", "keywords": ["next.js typescript", "nextjs typescript", "next ts"], "strategy": "global.css CSS Variables + typed layout/provider", "entries": ["app/layout.tsx", "pages/_app.tsx"]},
    {"id": "vue_js", "label": "Vue + JavaScript", "group": "Vue", "language": "JavaScript", "keywords": ["vue", "vue.js", "vuejs"], "strategy": "CSS Variables + app-level composable/plugin", "entries": ["App.vue", "main.js"]},
    {"id": "vue_ts", "label": "Vue + TypeScript", "group": "Vue", "language": "TypeScript", "keywords": ["vue typescript", "vue ts", "vue3 typescript"], "strategy": "CSS Variables + typed composable/plugin", "entries": ["App.vue", "main.ts"]},
    {"id": "nuxt_js", "label": "Nuxt + JavaScript", "group": "Vue", "language": "JavaScript", "keywords": ["nuxt", "nuxt.js", "nuxtjs"], "strategy": "assets CSS Variables + app config/plugin", "entries": ["app.vue", "nuxt.config.js"]},
    {"id": "nuxt_ts", "label": "Nuxt + TypeScript", "group": "Vue", "language": "TypeScript", "keywords": ["nuxt typescript", "nuxt ts"], "strategy": "assets CSS Variables + typed app config/plugin", "entries": ["app.vue", "nuxt.config.ts"]},
    {"id": "angular_ts", "label": "Angular + TypeScript", "group": "Angular", "language": "TypeScript", "keywords": ["angular"], "strategy": "styles.scss/CSS Custom Properties + Angular theme service", "entries": ["app.component.ts", "styles.scss"]},
    {"id": "svelte_js", "label": "Svelte + JavaScript", "group": "Svelte", "language": "JavaScript", "keywords": ["svelte"], "strategy": "app.css CSS Variables + component styles", "entries": ["App.svelte", "main.js"]},
    {"id": "svelte_ts", "label": "Svelte + TypeScript", "group": "Svelte", "language": "TypeScript", "keywords": ["svelte typescript", "svelte ts"], "strategy": "app.css CSS Variables + typed stores", "entries": ["App.svelte", "main.ts"]},
    {"id": "sveltekit", "label": "SvelteKit", "group": "Svelte", "language": "JavaScript / TypeScript", "keywords": ["sveltekit", "svelte kit"], "strategy": "app.css CSS Variables + root layout", "entries": ["src/routes/+layout.svelte"]},
    {"id": "astro", "label": "Astro", "group": "Web", "language": "JavaScript / TypeScript", "keywords": ["astro"], "strategy": "global CSS Variables + BaseLayout", "entries": ["src/layouts/Layout.astro"]},
    {"id": "solid", "label": "SolidJS", "group": "Web", "language": "JavaScript / TypeScript", "keywords": ["solidjs", "solid js", "solid.js"], "strategy": "CSS Variables + theme context", "entries": ["App.tsx", "App.jsx"]},
    {"id": "preact", "label": "Preact", "group": "Web", "language": "JavaScript / TypeScript", "keywords": ["preact"], "strategy": "CSS Variables + theme context", "entries": ["App.tsx", "App.jsx"]},
    {"id": "remix_js", "label": "Remix + JavaScript", "group": "React", "language": "JavaScript", "keywords": ["remix"], "strategy": "root.css CSS Variables + root layout", "entries": ["app/root.jsx", "app/root.js"]},
    {"id": "remix_ts", "label": "Remix + TypeScript", "group": "React", "language": "TypeScript", "keywords": ["remix typescript", "remix ts"], "strategy": "root.css CSS Variables + typed root layout", "entries": ["app/root.tsx"]},
    {"id": "gatsby_js", "label": "Gatsby + JavaScript", "group": "React", "language": "JavaScript", "keywords": ["gatsby"], "strategy": "global CSS Variables + root wrapper/provider", "entries": ["gatsby-browser.js", "src/pages/index.jsx"]},
    {"id": "gatsby_ts", "label": "Gatsby + TypeScript", "group": "React", "language": "TypeScript", "keywords": ["gatsby typescript", "gatsby ts"], "strategy": "global CSS Variables + typed root wrapper/provider", "entries": ["gatsby-browser.tsx", "src/pages/index.tsx"]},
    {"id": "qwik", "label": "Qwik / Qwik City", "group": "Web", "language": "TypeScript / JavaScript", "keywords": ["qwik", "qwik city"], "strategy": "global.css CSS Variables + root layout", "entries": ["src/routes/layout.tsx", "src/global.css"]},
    {"id": "alpine", "label": "Alpine.js", "group": "Web", "language": "JavaScript", "keywords": ["alpine.js", "alpinejs"], "strategy": "CSS Custom Properties + Alpine stores where state is required", "entries": ["index.html", "styles.css"]},
    {"id": "htmx", "label": "HTMX", "group": "Web", "language": "HTML / JavaScript", "keywords": ["htmx"], "strategy": "CSS Custom Properties in shared/base stylesheet", "entries": ["templates/base.html", "static/css/theme.css"]},
    {"id": "html_css_js", "label": "HTML + CSS + JavaScript", "group": "Web", "language": "JavaScript", "keywords": ["html", "css", "vanilla js", "바닐라"], "strategy": "CSS Custom Properties in :root", "entries": ["index.html", "styles.css"]},
    {"id": "tailwind", "label": "Tailwind CSS 기반 UI", "group": "Styling", "language": "Framework dependent", "keywords": ["tailwind"], "strategy": "Design Token -> CSS Variables + Tailwind theme/config mapping", "entries": ["tailwind.config.*", "global.css"]},
    {"id": "bootstrap", "label": "Bootstrap 기반 UI", "group": "Styling", "language": "Framework dependent", "keywords": ["bootstrap"], "strategy": "CSS Variables/SCSS variable overrides", "entries": ["styles.scss", "styles.css"]},
    {"id": "mui", "label": "Material UI (MUI)", "group": "Styling", "language": "React JS / TS", "keywords": ["material ui", "mui"], "strategy": "Design Token -> createTheme palette/typography/shape/components", "entries": ["theme.ts", "theme.js"]},
    {"id": "chakra", "label": "Chakra UI", "group": "Styling", "language": "React JS / TS", "keywords": ["chakra"], "strategy": "Design Token -> extendTheme/createSystem", "entries": ["theme.ts", "theme.js"]},
    {"id": "antd", "label": "Ant Design", "group": "Styling", "language": "React JS / TS", "keywords": ["ant design", "antd"], "strategy": "Design Token -> ConfigProvider theme.token/components", "entries": ["theme.ts", "theme.js"]},
    {"id": "shadcn", "label": "shadcn/ui", "group": "Styling", "language": "React / TypeScript", "keywords": ["shadcn", "shadcn/ui"], "strategy": "Design Token -> CSS variables used by shadcn/Tailwind semantic tokens", "entries": ["globals.css", "components.json"]},
    {"id": "mantine", "label": "Mantine", "group": "Styling", "language": "React / TypeScript", "keywords": ["mantine"], "strategy": "Design Token -> Mantine theme object/CSS variables", "entries": ["theme.ts"]},
    {"id": "vuetify", "label": "Vuetify", "group": "Styling", "language": "Vue / TypeScript", "keywords": ["vuetify"], "strategy": "Design Token -> Vuetify createVuetify theme configuration", "entries": ["plugins/vuetify.ts"]},
    {"id": "prime_ui", "label": "PrimeReact / PrimeVue / PrimeNG", "group": "Styling", "language": "Framework dependent", "keywords": ["primereact", "primevue", "primeng"], "strategy": "Design Token -> Prime theme preset/CSS variables", "entries": ["theme.*", "styles.*"]},
    {"id": "streamlit", "label": "Streamlit", "group": "Python UI", "language": "Python", "keywords": ["streamlit"], "strategy": "config.toml theme + controlled CSS variables/style injection", "entries": ["streamlit_app.py", ".streamlit/config.toml"]},
    {"id": "gradio", "label": "Gradio", "group": "Python UI", "language": "Python", "keywords": ["gradio"], "strategy": "gradio Theme object + CSS overrides", "entries": ["app.py"]},
    {"id": "nicegui", "label": "NiceGUI", "group": "Python UI", "language": "Python", "keywords": ["nicegui", "nice gui"], "strategy": "CSS Variables + ui.colors/ui.add_css", "entries": ["main.py"]},
    {"id": "dash", "label": "Plotly Dash", "group": "Python UI", "language": "Python", "keywords": ["plotly dash", "dash app"], "strategy": "assets CSS Variables + component style mapping", "entries": ["app.py", "assets/theme.css"]},
    {"id": "panel", "label": "Panel / HoloViz", "group": "Python UI", "language": "Python", "keywords": ["holoviz", "panel python"], "strategy": "Panel theme/template + CSS variables", "entries": ["app.py"]},
    {"id": "django_templates", "label": "Django Templates", "group": "Server Rendered", "language": "Python / HTML", "keywords": ["django"], "strategy": "static CSS Variables + base template", "entries": ["templates/base.html", "static/css/theme.css"]},
    {"id": "jinja", "label": "Jinja2 / Flask / FastAPI Templates", "group": "Server Rendered", "language": "Python / HTML", "keywords": ["jinja", "flask template", "fastapi template"], "strategy": "static CSS Variables + base template", "entries": ["templates/base.html", "static/css/theme.css"]},
    {"id": "blazor", "label": "Blazor", "group": ".NET UI", "language": "C# / Razor", "keywords": ["blazor"], "strategy": "CSS Variables + scoped CSS / layout components", "entries": ["App.razor", "MainLayout.razor"]},
    {"id": "razor", "label": "ASP.NET Razor / MVC", "group": ".NET UI", "language": "C# / Razor", "keywords": ["razor pages", "asp.net mvc", "cshtml"], "strategy": "site.css CSS Variables + _Layout.cshtml", "entries": ["_Layout.cshtml", "site.css"]},
    {"id": "aspnet_webforms", "label": "ASP.NET WebForms", "group": ".NET UI", "language": "C# / ASPX", "keywords": ["webforms", "asp.net webforms", "aspx"], "strategy": "site.css CSS Variables + MasterPage/ASPX control classes", "entries": ["Site.Master", "Content/Site.css"]},
    {"id": "react_native", "label": "React Native / Expo", "group": "Mobile", "language": "JavaScript / TypeScript", "keywords": ["react native", "expo"], "strategy": "Design Token -> JS/TS theme object + StyleSheet", "entries": ["App.tsx", "App.jsx"]},
    {"id": "ionic", "label": "Ionic / Capacitor", "group": "Mobile", "language": "JavaScript / TypeScript", "keywords": ["ionic", "capacitor"], "strategy": "Ionic CSS variables + framework-specific theme provider", "entries": ["src/theme/variables.css"]},
    {"id": "flutter", "label": "Flutter", "group": "Mobile", "language": "Dart", "keywords": ["flutter", "dart"], "strategy": "Design Token -> ThemeData/ColorScheme/TextTheme", "entries": ["lib/theme/app_theme.dart"]},
    {"id": "electron", "label": "Electron", "group": "Desktop", "language": "JavaScript / TypeScript", "keywords": ["electron"], "strategy": "Renderer framework theme adapter + CSS Variables/theme object", "entries": ["src/renderer"]},
    {"id": "tauri", "label": "Tauri Frontend", "group": "Desktop", "language": "JavaScript / TypeScript / Rust shell", "keywords": ["tauri"], "strategy": "Web frontend native theme adapter inside Tauri renderer", "entries": ["src"]},
    {"id": "generic_web", "label": "기타 Web Frontend (Generic)", "group": "기타", "language": "Framework dependent", "keywords": [], "strategy": "Canonical Design Token -> target framework native theme mechanism; CSS capable targets use CSS Custom Properties", "entries": []},
]


def list_frontend_theme_targets() -> list[dict]:
    return deepcopy(FRONTEND_THEME_TARGETS)


def detect_frontend_theme_target(text: str) -> dict:
    value = str(text or "").casefold()
    by_id = {item["id"]: item for item in FRONTEND_THEME_TARGETS}
    ts = any(token in value for token in ("typescript", "type script", "타입스크립트", "타입 스크립트", ".tsx", " ts "))

    def has(*tokens: str) -> bool:
        return any(token.casefold() in value for token in tokens)

    if has("react native", "expo"):
        return deepcopy(by_id["react_native"])
    if has("remix"):
        return deepcopy(by_id["remix_ts" if ts else "remix_js"])
    if has("gatsby"):
        return deepcopy(by_id["gatsby_ts" if ts else "gatsby_js"])
    if has("next.js", "nextjs", "next js"):
        return deepcopy(by_id["next_ts" if ts else "next_js"])
    if has("nuxt", "nuxt.js", "nuxtjs"):
        return deepcopy(by_id["nuxt_ts" if ts else "nuxt_js"])
    if has("sveltekit", "svelte kit"):
        return deepcopy(by_id["sveltekit"])
    if has("react", "vite react"):
        return deepcopy(by_id["react_ts" if ts else "react_js"])
    if has("vue", "vue.js", "vuejs"):
        return deepcopy(by_id["vue_ts" if ts else "vue_js"])
    if has("svelte"):
        return deepcopy(by_id["svelte_ts" if ts else "svelte_js"])
    for target_id, tokens in (
        ("angular_ts", ("angular",)),
        ("streamlit", ("streamlit",)),
        ("gradio", ("gradio",)),
        ("nicegui", ("nicegui", "nice gui")),
        ("dash", ("plotly dash", "dash app")),
        ("panel", ("holoviz", "panel python")),
        ("django_templates", ("django",)),
        ("jinja", ("jinja", "flask template", "fastapi template")),
        ("blazor", ("blazor",)),
        ("razor", ("razor pages", "asp.net mvc", "cshtml")),
        ("aspnet_webforms", ("webforms", "asp.net webforms", "aspx")),
        ("flutter", ("flutter", "dart")),
        ("ionic", ("ionic", "capacitor")),
        ("electron", ("electron",)),
        ("tauri", ("tauri",)),
        ("qwik", ("qwik", "qwik city")),
        ("alpine", ("alpine.js", "alpinejs")),
        ("htmx", ("htmx",)),
        ("astro", ("astro",)),
        ("solid", ("solidjs", "solid js", "solid.js")),
        ("preact", ("preact",)),
        ("html_css_js", ("vanilla js", "바닐라", "html + css", "html/css")),
        ("mui", ("material ui", "mui",)),
        ("chakra", ("chakra",)),
        ("antd", ("ant design", "antd",)),
        ("shadcn", ("shadcn", "shadcn/ui")),
        ("mantine", ("mantine",)),
        ("vuetify", ("vuetify",)),
        ("prime_ui", ("primereact", "primevue", "primeng")),
        ("tailwind", ("tailwind",)),
        ("bootstrap", ("bootstrap",)),
    ):
        if has(*tokens):
            return deepcopy(by_id[target_id])
    return deepcopy(by_id["generic_web"])


def detect_frontend_style_adapters(text: str) -> list[dict]:
    value = str(text or "").casefold()
    adapters: list[dict] = []
    for item in FRONTEND_THEME_TARGETS:
        if item.get("group") != "Styling":
            continue
        if any(str(keyword).casefold() in value for keyword in item.get("keywords") or []):
            adapters.append(deepcopy(item))
    return adapters


def frontend_theme_generation_instruction(text: str) -> str:
    target = detect_frontend_theme_target(text)
    style_adapters = detect_frontend_style_adapters(text)
    style_instruction = ""
    if style_adapters:
        joined = "; ".join(f"{item['label']}: {item['strategy']}" for item in style_adapters)
        style_instruction = f" 함께 사용 중인 UI/Styling Adapter도 적용하십시오: {joined}."
    return (
        f"확정 Frontend 대상은 '{target['label']}'로 감지되었습니다. "
        f"Custom Theme의 canonical theme_tokens/component_rules/layout_rules를 보존하고 "
        f"'{target['strategy']}' 방식으로 변환하여 적용하십시오."
        f"{style_instruction} "
        "Theme 적용을 React/CSS Provider 하나로 고정하지 마십시오. 선택된 Frontend의 native theme API, "
        "CSS/SCSS variables, framework config 또는 theme object를 사용하십시오. "
        "미등록 Frontend라도 generic adapter를 사용해 같은 Design Token 의미(primary/background/surface/text/border, "
        "typography, radius, shadow, spacing/layout)를 유지하십시오. component_rules.menu에 normal/hover/active가 있으면 "
        "Navigation/Sidebar/Header menu의 기본 상태, 마우스 오버 상태, 활성 상태를 선택한 Frontend의 native styling 방식으로 반드시 구현하십시오. "
        "참조 사이트의 로고·문구·이미지·고유 콘텐츠는 복제하지 마십시오."
    )


def frontend_test_environment_files(target_id: str) -> dict:
    target_id = str(target_id or "generic_web")
    mapping = {
        "react_js": {"page": "frontend/src/pages/admin/TestEnvironmentPage.jsx", "api_client": "frontend/src/services/testEnvironmentApi.js"},
        "react_ts": {"page": "frontend/src/pages/admin/TestEnvironmentPage.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "next_js": {"page": "frontend/app/admin/test-environment/page.jsx", "api_client": "frontend/src/services/testEnvironmentApi.js"},
        "next_ts": {"page": "frontend/app/admin/test-environment/page.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "vue_js": {"page": "frontend/src/pages/admin/TestEnvironmentPage.vue", "api_client": "frontend/src/services/testEnvironmentApi.js"},
        "vue_ts": {"page": "frontend/src/pages/admin/TestEnvironmentPage.vue", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "nuxt_js": {"page": "frontend/pages/admin/test-environment.vue", "api_client": "frontend/composables/useTestEnvironment.js"},
        "nuxt_ts": {"page": "frontend/pages/admin/test-environment.vue", "api_client": "frontend/composables/useTestEnvironment.ts"},
        "angular_ts": {"page": "frontend/src/app/admin/test-environment/test-environment.component.ts", "api_client": "frontend/src/app/services/test-environment-api.service.ts"},
        "svelte_js": {"page": "frontend/src/pages/admin/TestEnvironmentPage.svelte", "api_client": "frontend/src/services/testEnvironmentApi.js"},
        "svelte_ts": {"page": "frontend/src/pages/admin/TestEnvironmentPage.svelte", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "sveltekit": {"page": "frontend/src/routes/admin/test-environment/+page.svelte", "api_client": "frontend/src/lib/testEnvironmentApi.ts"},
        "astro": {"page": "frontend/src/pages/admin/test-environment.astro", "api_client": "frontend/src/lib/testEnvironmentApi.ts"},
        "solid": {"page": "frontend/src/pages/admin/TestEnvironmentPage.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "preact": {"page": "frontend/src/pages/admin/TestEnvironmentPage.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "remix_js": {"page": "frontend/app/routes/admin.test-environment.jsx", "api_client": "frontend/app/services/testEnvironmentApi.js"},
        "remix_ts": {"page": "frontend/app/routes/admin.test-environment.tsx", "api_client": "frontend/app/services/testEnvironmentApi.ts"},
        "gatsby_js": {"page": "frontend/src/pages/admin/test-environment.jsx", "api_client": "frontend/src/services/testEnvironmentApi.js"},
        "gatsby_ts": {"page": "frontend/src/pages/admin/test-environment.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "qwik": {"page": "frontend/src/routes/admin/test-environment/index.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "alpine": {"page": "frontend/admin/test-environment.html", "api_client": "frontend/js/test-environment-api.js"},
        "htmx": {"page": "templates/admin/test_environment.html", "api_client": "static/js/test-environment.js"},
        "html_css_js": {"page": "frontend/admin/test-environment.html", "api_client": "frontend/js/test-environment-api.js"},
        "streamlit": {"page": "apps/pages/admin_test_environment.py", "api_client": "apps/services/test_environment_api.py"},
        "gradio": {"page": "frontend/admin_test_environment.py", "api_client": "frontend/test_environment_api.py"},
        "nicegui": {"page": "frontend/pages/admin_test_environment.py", "api_client": "frontend/services/test_environment_api.py"},
        "dash": {"page": "frontend/pages/admin_test_environment.py", "api_client": "frontend/services/test_environment_api.py"},
        "panel": {"page": "frontend/pages/admin_test_environment.py", "api_client": "frontend/services/test_environment_api.py"},
        "django_templates": {"page": "templates/admin/test_environment.html", "api_client": "static/js/test_environment.js"},
        "jinja": {"page": "templates/admin/test_environment.html", "api_client": "static/js/test_environment.js"},
        "blazor": {"page": "frontend/Pages/Admin/TestEnvironment.razor", "api_client": "frontend/Services/TestEnvironmentApi.cs"},
        "razor": {"page": "frontend/Pages/Admin/TestEnvironment.cshtml", "api_client": "frontend/wwwroot/js/test-environment.js"},
        "aspnet_webforms": {"page": "frontend/Admin/TestEnvironment.aspx", "api_client": "frontend/Scripts/test-environment.js"},
        "react_native": {"page": "frontend/src/screens/admin/TestEnvironmentScreen.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "ionic": {"page": "frontend/src/pages/admin/TestEnvironment.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
        "flutter": {"page": "frontend/lib/screens/admin/test_environment_screen.dart", "api_client": "frontend/lib/services/test_environment_api.dart"},
        "electron": {"page": "frontend/src/renderer/pages/admin/TestEnvironmentPage.tsx", "api_client": "frontend/src/renderer/services/testEnvironmentApi.ts"},
        "tauri": {"page": "frontend/src/pages/admin/TestEnvironmentPage.tsx", "api_client": "frontend/src/services/testEnvironmentApi.ts"},
    }
    return deepcopy(mapping.get(target_id, {"page": "frontend/admin/test-environment", "api_client": "frontend/services/test-environment-api"}))
