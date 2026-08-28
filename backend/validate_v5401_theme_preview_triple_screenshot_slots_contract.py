from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"frontend/src/App.jsx").read_text(encoding="utf-8")
CSS=(ROOT/"frontend/src/styles.css").read_text(encoding="utf-8")
MAIN=(ROOT/"backend/app/main.py").read_text(encoding="utf-8")
ROUTES=(ROOT/"backend/app/api/routes.py").read_text(encoding="utf-8")
checks={
 "version": "AGENTSTUDIO_FRONTEND_VERSION='5.401'" in APP and 'version="5.401"' in MAIN and '"version": "5.401"' in ROUTES,
 "preview component": 'function UILayoutThemePreview' in APP and 'uiThemePreviewTokens' in APP,
 "live preview": 'Theme 미리보기' in APP and '전체 미리보기' in APP,
 "viewport": all(x in APP for x in ["'desktop'","'tablet'","'mobile'"]),
 "menu states": all(x in APP for x in ['Menu Normal','Menu Hover','Menu Active']),
 "three slots": '화면 캡처 {index+1}' in APP and '[0,1,2].map' in APP,
 "single file per slot": 'chooseThemeImageSlot(index,e.target.files)' in APP and 'multiple' not in APP[APP.find('ui-layout-theme-file-slots'):APP.find('ui-layout-theme-file-slots')+1800],
 "three-slot storage": 'useState([null,null,null])' in APP,
 "css preview": '.ui-layout-theme-preview-modal' in CSS and '.ui-theme-preview-body>aside .hover' in CSS,
 "css slots": '.ui-layout-theme-file-slots' in CSS and '.ui-layout-theme-file-slot' in CSS,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('FAIL: '+', '.join(failed))
print(f'v5.401 theme preview triple screenshot slots contract PASS {len(checks)}/{len(checks)}')
