from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
checks={
 'version': "AGENTSTUDIO_FRONTEND_VERSION='5.404'" in APP and 'version="5.404"' in MAIN and '"version": "5.404"' in ROUTES,
 'mobile menu state': 'const [mobileMenuOpen,setMobileMenuOpen]=useState(false)' in APP,
 'viewport reset': 'setMobileMenuOpen(false)' in APP and '},[viewport])' in APP,
 'mobile hamburger': 'ui-theme-preview-mobile-menu-trigger' in APP and '☰' in APP,
 'aria expanded': 'aria-expanded={mobileMenuOpen}' in APP,
 'mobile menu layer': 'ui-theme-preview-mobile-menu-layer' in APP,
 'mobile combined navigation': "mobileItem('products','Products',true" in APP and "mobileItem('catalog','Catalog',true" in APP,
 'desktop sidebar hidden on mobile': '.ui-theme-preview.mobile .ui-theme-preview-body>aside{display:none}' in CSS,
 'mobile drawer styling': '.ui-theme-preview-mobile-menu-panel' in CSS and '@keyframes uiThemeMobileMenuIn' in CSS,
 'mobile user popup constrained': '.ui-theme-preview.mobile .ui-theme-preview-user-menu' in CSS,
 'build flag': 'MobileInteractiveThemeMenuPreview' in ROUTES,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('v5.404 contract FAIL: '+', '.join(failed))
print(f'v5.404 mobile interactive Theme menu preview contract PASS {len(checks)}/{len(checks)}')
