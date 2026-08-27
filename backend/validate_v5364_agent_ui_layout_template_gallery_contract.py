from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
PPT=(ROOT/'backend/app/services/presentation_export_service.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
checks={
 'frontend version':"AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
 'template gallery':'UI_LAYOUT_TEMPLATES' in APP and 'UILayoutTemplateGallery' in APP,
 'visual previews':'UILayoutWireframe' in APP and 'ui-layout-wireframe' in CSS,
 'layout controls':all(x in APP for x in ['상단 Header','좌측 메뉴','Footer','사용자 메뉴','Main Layout','Theme']),
 'builder step':"['05','UI / Layout'" in APP,
 'draft persistence':'ui_layout:uiLayoutConfig||null' in APP and 'setUiLayoutConfig(snapshot?.ui_layout' in APP,
 'confirmed requirements':'ui_layout:uiLayoutConfig?.template_id' in APP,
 'workflow prompt':'confirmed_requirements.ui_layout' in ROUTES,
 'ppt payload':'ui_layout:uiLayoutConfig||confirmedInterviewRequirements?.ui_layout||null' in APP,
 'ppt slide':'def _add_ui_layout_slide' in PPT and 'UI / UX Layout' in PPT,
 'backend model':'ui_layout: dict = {}' in ROUTES,
 'backend version':'version="5.369"' in MAIN and '"version": "5.369"' in ROUTES,
}
failed=[k for k,v in checks.items() if not v]
if failed: raise SystemExit('v5.369 contract failed: '+', '.join(failed))
print('PASS v5.369 Agent UI Layout Template Gallery contract')
