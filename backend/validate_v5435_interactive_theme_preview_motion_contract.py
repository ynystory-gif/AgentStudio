from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

APP = (ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
BROWSER = (ROOT/'backend/app/services/ui_theme_browser_analysis_service.py').read_text(encoding='utf-8')
THEME = (ROOT/'backend/app/services/ui_theme_service.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT/'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
MAIN = (ROOT/'backend/app/main.py').read_text(encoding='utf-8')

from app.services.ui_theme_service import _declaration_map, merge_theme_analyses
from app.services.ui_theme_browser_analysis_service import _style_to_rule, _hover_probe_rules

motion_css = _declaration_map(
    'transition-property: transform, opacity; transition-duration: .24s; '
    'transition-timing-function: cubic-bezier(.2,.8,.2,1); transform: translateY(-2px); opacity:.82;'
)
rendered_rule = _style_to_rule({
    'background':'rgb(255,255,255)', 'color':'rgb(20,20,20)', 'borderColor':'rgb(220,220,220)',
    'transition':'transform 0.2s ease 0s, opacity 0.2s ease 0s',
    'transform':'matrix(1, 0, 0, 1, 2, 0)', 'opacity':'0.9', 'filter':'brightness(0.98)'
})
probe_before, probe_hover, probe_label = _hover_probe_rules({'hover_probes':[{
    'label':'Home',
    'before':{'style':{'background':'rgb(255,255,255)','color':'rgb(0,0,0)','transition':'transform 0.2s ease 0s','transform':'none'}},
    'hover':{'style':{'background':'rgb(245,245,245)','color':'rgb(0,0,0)','transition':'transform 0.2s ease 0s','transform':'matrix(1,0,0,1,2,0)'}},
}]})
static={'analysis_source':'URL','tokens':{'colors':{}},'component_rules':{'menu':{'normal':{'background':'#ffffff'},'hover':{'background':'#eeeeee','transition':'all .1s ease'},'active':{},'source':'CSS_SELECTOR_ANALYSIS'},'_evidence':{'menu.hover':{'status':'confirmed','source':'URL_CSS_SELECTOR','confidence':.90}}},'layout_rules':{}}
browser={'analysis_source':'URL','tokens':{'colors':{}},'component_rules':{'menu':{'normal':{'background':'#ffffff'},'hover':{'background':'#dddddd','transform':'translateX(2px)','transition':'all .2s ease'},'active':{},'source':'CHROME_INTERACTION_PROBE'},'_evidence':{'menu.hover':{'status':'confirmed','source':'CHROME_INTERACTION_PROBE','confidence':.97}}},'layout_rules':{}}
merged_hover=merge_theme_analyses([static,browser])['component_rules']['menu']['hover']

checks = {
    'frontend version 5.435': "AGENTSTUDIO_FRONTEND_VERSION='5.435'" in APP,
    'backend version 5.435': 'version="5.435"' in MAIN,
    'preview keeps interactive page state': 'const [activePage,setActivePage]=useState(0)' in APP,
    'Dashboard Activity Settings are fallback pages': "[{label:'Dashboard'},{label:'Activity'},{label:'Settings'}]" in APP,
    'preview tab click changes page': 'onClick={()=>setActivePage(index)}' in APP,
    'preview has distinct activity page': "pageModel.kind==='activity'" in APP and 'ui-theme-preview-activity' in CSS,
    'preview has distinct settings page': "pageModel.kind==='settings'" in APP and 'ui-theme-preview-settings' in CSS,
    'source navigation replaces preview tab labels': 'sourceMenuItems.length?sourceMenuItems.slice(0,5)' in APP,
    'source icon text shown in page navigation': "sourceMenuItems.length?renderMenuLabel(item,index)" in APP and 'ui-theme-preview-menu-icon' in APP,
    'custom theme preview applies imported menu states': "config?.theme==='custom'?'imported-navigation':''" in APP,
    'imported navigation has hover transform': '--tp-menu-hover-transform' in APP and 'transform:var(--tp-menu-hover-transform)' in CSS,
    'imported navigation has source timing': '--tp-menu-transition' in APP and 'transition:var(--tp-menu-transition)' in CSS,
    'imported navigation has opacity/filter/font motion': '--tp-menu-hover-opacity' in APP and '--tp-menu-hover-filter' in APP and '--tp-menu-hover-font-weight' in APP,
    'browser collects live hover probes': '_collect_hover_probes' in BROWSER and "'hover_probes':hover_probes" in BROWSER,
    'browser captures computed transition animation': 'transitionDuration:s.transitionDuration' in BROWSER and 'animationDuration:s.animationDuration' in BROWSER,
    'browser exposes motion metadata in nav contract': "'motion_detected':bool(hover_probes)" in BROWSER,
    'browser hover probe creates explicit menu hover evidence': "'source':'CHROME_INTERACTION_PROBE'" in BROWSER,
    'static parser reconstructs split transition': motion_css.get('transition','').startswith('transform, opacity .24s'),
    'rendered rule keeps transition': '0.2s' in str(rendered_rule.get('transition') or ''),
    'rendered rule keeps transform': str(rendered_rule.get('transform') or '').startswith('matrix('),
    'hover probe detects actual hover delta': probe_label == 'Home' and probe_hover.get('background') == '#f5f5f5' and probe_hover.get('transform'),
    'merge prefers stronger live hover evidence': merged_hover.get('background') == '#dddddd' and merged_hover.get('transform') == 'translateX(2px)',
    'generated agent motion policy exists': 'motionTransition' in WORKFLOW and 'duration/timing/transform/opacity' in WORKFLOW,
}

failed=[name for name,ok in checks.items() if not ok]
for name,ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit(f"v5.435 contract failed: {', '.join(failed)}")
print(f"v5.435 contract PASS {len(checks)}/{len(checks)}")
