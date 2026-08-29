from __future__ import annotations

import asyncio
from copy import deepcopy

from app.services.ui_theme_browser_process_service import analyze_rendered_theme_layout
from app.services.ui_theme_fetch_context_service import analyze_theme_source_context, fetch_theme_source_context
from app.services.ui_theme_killable_process_service import run_theme_worker

_STATIC_TIMEOUT_SECONDS = 38
_BROWSER_TIMEOUT_SECONDS = 58
_LAYOUT_WORKER_TIMEOUT_SECONDS = 20


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


async def _analyze_static_theme(url: str) -> dict:
    context = await fetch_theme_source_context(url)
    analysis = await analyze_theme_source_context(context)
    contract = await run_theme_worker(
        'layout_contract',
        {
            'html': str(context.get('html') or ''),
            'css_text': str(context.get('css_text') or ''),
        },
        timeout=_LAYOUT_WORKER_TIMEOUT_SECONDS,
    )
    _apply_layout_convenience(analysis, contract)
    source_meta=dict(analysis.get('source_meta') or {})
    source_meta.update({
        'layout_contract':contract,
        'layout_css_files':int(context.get('css_files') or 0),
        'network_passes':1,
        'stylesheet_only':True,
        'parallel_stylesheet_fetch':True,
        'stylesheet_candidates':len(context.get('stylesheet_urls') or []),
        'fetch_warnings':list(context.get('warnings') or []),
        'layout_worker_mode':'KILLABLE_PROCESS',
    })
    analysis['source_meta']=source_meta
    return analysis


async def analyze_theme_hybrid(url: str) -> dict:
    try:
        analysis=await asyncio.wait_for(_analyze_static_theme(url),timeout=_STATIC_TIMEOUT_SECONDS)
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
        'analysis_pipeline':'STATIC_KILLABLE_PROCESS_THEN_CHROME_CDP_PROCESS',
        'static_analysis_status':'success',
        'browser_analysis_status':str(browser_result.get('status') or ('success' if browser_ok else 'failed')),
        'browser_analysis_ok':browser_ok,
        'partial_success':not browser_ok,
        'analysis_completeness':'full' if browser_ok else 'static_only',
        'analysis_warnings':warnings,
        'rendered_layout_contract':browser_contract,
        'worker_isolation':'PROCESS_TREE_KILLABLE',
    })
    analysis['source_meta']=source_meta
    return analysis


analyze_theme_with_layout_contract=analyze_theme_hybrid
