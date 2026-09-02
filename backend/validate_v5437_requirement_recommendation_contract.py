from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend/app/services/agent_factory_workflow_design.py').read_text(encoding='utf-8')
SERVICE_PATH = ROOT / 'backend/app/services/requirement_recommendation_service.py'

spec = importlib.util.spec_from_file_location('requirement_recommendation_service', SERVICE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

registered = [
    {
        'provider': 'Blender MCP',
        'name': 'create_mesh',
        'description': 'Create Blender mesh object in scene',
        'category': '3D',
        'subcategory': 'MESH',
        'capability': 'scene_modeling',
        'risk_level': 2,
        'requires_confirmation': False,
        'enabled': True,
    },
    {
        'provider': 'Browser MCP',
        'name': 'browser_search',
        'description': 'Search web pages',
        'category': 'BROWSER',
        'subcategory': 'SEARCH',
        'capability': 'web_search',
        'risk_level': 1,
        'requires_confirmation': False,
        'enabled': True,
    },
]

bundle = mod.build_requirement_recommendations(
    'Blender MCP를 이용한 3D 제작 Agent를 만들고 Render와 Export를 지원해줘.',
    [],
    agent_specialization='BLENDER_3D',
    registered_tools=registered,
)
feature_ids = {row.get('id') for row in bundle.get('features') or []}
menu_ids = {row.get('id') for row in bundle.get('menus') or []}
tool_ids = {row.get('id') for row in bundle.get('tools') or []}
routing = bundle.get('llm_tool_routing') or {}
defaults = bundle.get('default_settings') or {}

selected_feature = next(row for row in bundle['features'] if row['id'] == 'scene_spec')
selected_menu = next(row for row in bundle['menus'] if row['id'] == 'scene')
selected_tool = next(row for row in bundle['tools'] if row['id'] == 'blender_scene_tool')
confirmed = {
    'recommendation_settings': {
        'selected_features': [selected_feature],
        'selected_menus': [selected_menu],
        'selected_tools': [selected_tool],
        'llm_tool_routing': defaults.get('llm_tool_routing') or {},
    }
}
design = mod.apply_recommendation_settings_to_design(
    {'target_agent_workflow': {'steps': [{'name': 'done', 'label': '완료', 'type': 'complete'}]}},
    confirmed,
)
step_names = [row.get('name') for row in (design.get('target_agent_workflow') or {}).get('steps') or [] if isinstance(row, dict)]
component_names = [row.get('name') for row in (design.get('agent_architecture') or {}).get('components') or [] if isinstance(row, dict)]
file_paths = {row.get('path') for row in (design.get('file_plan') or {}).get('new_files') or [] if isinstance(row, dict)}

checks = {
    'recommendation service route import': 'build_requirement_recommendations, apply_recommendation_settings_to_design' in ROUTES,
    'interview returns recommendation bundle': '"requirement_recommendations": recommendation_bundle' in ROUTES,
    'registry tools read for recommendation': 'select(ToolRecord).where(ToolRecord.enabled == True)' in ROUTES,
    'frontend recommendation state': 'requirementRecommendationSettings' in APP and 'requirementRecommendations' in APP,
    'frontend feature recommendation panel': '<strong>추천 기능</strong>' in APP,
    'frontend menu recommendation panel': '<strong>추천 메뉴</strong>' in APP,
    'frontend tool recommendation panel': '<strong>추천 Tool</strong>' in APP,
    'frontend first stage selector': '1차 분류 Tool' in APP and 'llm_intent_capability_classifier' in APP,
    'frontend second stage selector': '2차 분류 Tool' in APP and 'tool_registry_candidate_selector' in APP,
    'recommendations persist in snapshot': 'requirement_recommendations:requirementRecommendations||null' in APP and 'requirement_recommendation_settings:normalizeRequirementRecommendationSettings' in APP,
    'confirmed requirements carry settings': 'recommendation_settings:(()=>{' in APP,
    'workflow request carries selected recommendations': '[요구사항 분석 AI 추천 구성 - 사용자가 적용한 설정, Workflow/코드 생성 시 반영]' in APP,
    'incremental impact maps recommendations': '"recommendation_settings": {' in WORKFLOW,
    'workflow prompt honors recommendations': '[요구사항 분석 AI 추천 구성]' in WORKFLOW and '1차 Intent/Capability 분류 → 2차 Tool Registry 후보 선택' in WORKFLOW,
    'css recommendation card': '.requirement-recommendation-card' in CSS and '.requirement-tool-routing-card' in CSS,
    'blender feature recommendations': {'scene_spec','scene_modeling','viewport_vision_qa','render_export'}.issubset(feature_ids),
    'blender menu recommendations': {'scene','assets','materials','lighting_camera','render_export','settings','activity'}.issubset(menu_ids),
    'blender tool recommendations': {'blender_scene_tool','viewport_capture_tool','vision_qa_tool','render_export_tool','asset_resolver_tool'}.issubset(tool_ids),
    'registered tool is detected': selected_tool.get('registered') is True and selected_tool.get('registry_tool_name') == 'create_mesh',
    'two stage routing defaults': (routing.get('first_stage') or {}).get('id') == 'llm_intent_capability_classifier' and (routing.get('second_stage') or {}).get('id') == 'tool_registry_candidate_selector',
    'llm ambiguity policy': (routing.get('first_stage') or {}).get('llm_condition') and (routing.get('second_stage') or {}).get('llm_condition'),
    'design gets routing steps': 'classify_tool_capability' in step_names and 'select_registry_tool' in step_names,
    'design gets routing components': 'Tool Capability Router (1차)' in component_names and 'Tool Registry Selector (2차)' in component_names,
    'routing source files planned': {'backend/app/services/tool_category_router.py','backend/app/services/tool_candidate_selector.py','backend/tests/test_two_stage_tool_routing.py'}.issubset(file_paths),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.437 recommendation contract failed: ' + ', '.join(failed))
print(f'v5.437 requirement recommendation contract PASS {len(checks)}/{len(checks)}')
