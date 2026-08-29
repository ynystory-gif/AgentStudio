from __future__ import annotations

import asyncio
from copy import deepcopy

from app.services.ui_theme_browser_analysis_service import analyze_rendered_theme_layout
from app.services.ui_theme_layout_contract_service import analyze_theme_with_layout_contract as analyze_static_theme

_STATIC_TIMEOUT_SECONDS = 38
_BROWSER_TIMEOUT_SECONDS = 58


def _merge_contract(static_contract: dict, browser_contract: dict) -> dict:
    merged=deepcopy(static_contract or {})
    browser=browser_contract or {}
    if not browser:
        return merged

    merged['version']=max(int(merged.get('version') or 0),int(browser.get('version') or 0),3)
    merged['source']='STATIC_HTML_CSS_PLUS_CHROME_CDP'

    b_header=dict(browser.get('header') or {})
    if b_header.get('detected'):
        merged['header']={**dict(merged.get('header') or {}),**b_header}

    # Rendered desktop layout is authoritative because CSS selectors alone cannot tell
    # whether an aside/sidebar is actually visible at the target viewport.
    if isinstance(browser.get('desktop'),dict):
        merged['desktop']={**dict(merged.get('desktop') or {}),**dict(browser.get('desktop') or {})}

    static_mobile=dict(merged.get('mobile') or {})
    browser_mobile=dict(browser.get('mobile') or {})
    browser_drawer=dict(browser_mobile.get('drawer') or {})
    static_drawer=dict(static_mobile.get('drawer') or {})
    if browser_drawer.get('detected'):
        static_mobile['drawer']={**static_drawer,**browser_drawer}
    static_mobile.update({k:v for k,v in browser_mobile.items() if k!='drawer' and v not in (None,'',[])})
    merged['mobile']=static_mobile

    b_nav=dict(browser.get('navigation') or {})
    if b_nav.get('items'):
        merged['navigation']={**dict(merged.get('navigation') or {}),**b_nav}
    if browser.get('evidence'):
        merged['browser_evidence']=dict(browser.get('evidence') or {})
    return merged


def _apply_layout_convenience(analysis: dict, contract: dict) -> None:
    layout=dict(analysis.get('layout_rules') or {})
    layout['layoutContract']=contract
    drawer=((contract.get('mobile') or {}).get('drawer') or {})
    desktop=dict(contract.get('desktop') or {})
    navigation=dict(contract.get('navigation') or {})
    layout['mobileDrawerSide']=drawer.get('side','left')
    layout['mobileDrawerWidth']=drawer.get('width','82%') or '82%'
    layout['desktopSidebarPresent']=bool(desktop.get('sidebar_present'))
    layout['sourceNavigationItems']=list(navigation.get('items') or [])
    analysis['layout_rules']=layout


async def analyze_theme_hybrid(url: str) -> dict:
    """Analyze a public theme URL with a fast static pass and bounded rendered-CDP pass.

    Static HTML/CSS remains the source for reusable design tokens and interaction CSS.
    Chrome CDP only supplements facts that require a rendered page: actual visible header,
    sidebar, responsive drawer direction/width, overlay and rendered navigation items.
    A browser failure never discards successful static results.
    """
    static_error=''
    try:
        analysis=await asyncio.wait_for(analyze_static_theme(url),timeout=_STATIC_TIMEOUT_SECONDS)
    except Exception as exc:
        static_error=str(exc) or type(exc).__name__
        raise RuntimeError(f'정적 Theme 분석에 실패했습니다: {static_error}') from exc

    static_contract=dict(((analysis.get('layout_rules') or {}).get('layoutContract') or {}))
    browser_result={'ok':False,'status':'skipped','contract':{},'warning':''}
    try:
        browser_result=await asyncio.wait_for(analyze_rendered_theme_layout(url),timeout=_BROWSER_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        browser_result={'ok':False,'status':'timeout','contract':{},'warning':'Chrome CDP 보강 분석이 제한시간을 초과했습니다. 정적 분석 결과를 저장합니다.'}
    except Exception as exc:
        browser_result={'ok':False,'status':'failed','contract':{},'warning':f'Chrome CDP 보강 분석 실패: {str(exc) or type(exc).__name__}. 정적 분석 결과를 저장합니다.'}

    browser_contract=dict(browser_result.get('contract') or {})
    merged_contract=_merge_contract(static_contract,browser_contract)
    _apply_layout_convenience(analysis,merged_contract)

    source_meta=dict(analysis.get('source_meta') or {})
    warnings=list(source_meta.get('fetch_warnings') or [])
    if browser_result.get('warning'):
        warnings.append(str(browser_result.get('warning')))
    browser_ok=bool(browser_result.get('ok'))
    source_meta.update({
        'analysis_pipeline':'STATIC_THEN_CHROME_CDP',
        'static_analysis_status':'success',
        'browser_analysis_status':str(browser_result.get('status') or ('success' if browser_ok else 'failed')),
        'browser_analysis_ok':browser_ok,
        'partial_success':not browser_ok,
        'analysis_completeness':'full' if browser_ok else 'static_only',
        'analysis_warnings':warnings,
        'rendered_layout_contract':browser_contract,
    })
    analysis['source_meta']=source_meta
    return analysis


# Keep the public name familiar to the dynamic-import route.
analyze_theme_with_layout_contract=analyze_theme_hybrid
