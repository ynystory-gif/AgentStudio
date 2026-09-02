from __future__ import annotations

import asyncio
from copy import deepcopy

from app.services.ui_theme_browser_process_service import analyze_rendered_theme_layout
from app.services.ui_theme_fetch_context_service import analyze_theme_source_context, fetch_theme_source_context
from app.services.ui_theme_killable_process_service import run_theme_worker
from app.services.ui_theme_service import merge_theme_analyses

# v5.433: 300 seconds remains the one backend-authoritative hard deadline for the
# whole import job. Static HTTP/CSS and rendered Chrome analysis are independent
# evidence branches and run in parallel. A blocked/hanging static site must not
# prevent a valid rendered-page Theme from being saved.
_ANALYSIS_HARD_TIMEOUT_SECONDS = 300
_FETCH_TIMEOUT_SECONDS = 45
_STATIC_BRANCH_TIMEOUT_SECONDS = 90
_BROWSER_BRANCH_TIMEOUT_SECONDS = 90
_LAYOUT_WORKER_TIMEOUT_SECONDS = 30



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
    layout['sourceNavigationItemDetails']=list(navigation.get('item_details') or [])
    layout['sourceNavigationPresentation']=dict(navigation.get('presentation') or {})
    analysis['layout_rules']=layout


async def _analyze_static_theme(url: str) -> dict:
    context = await asyncio.wait_for(
        fetch_theme_source_context(url),
        timeout=_FETCH_TIMEOUT_SECONDS,
    )
    payload={
        'html': str(context.get('html') or ''),
        'css_text': str(context.get('css_text') or ''),
    }

    # Token/state extraction and Layout-contract extraction read the same immutable
    # HTML/CSS snapshot, so run them in parallel disposable processes. A Layout-only
    # timeout is non-fatal; the critical token result remains usable.
    analysis_task=asyncio.create_task(analyze_theme_source_context(context))
    layout_task=asyncio.create_task(
        run_theme_worker(
            'layout_contract',
            payload,
            timeout=_LAYOUT_WORKER_TIMEOUT_SECONDS,
        )
    )
    analysis_result, layout_result = await asyncio.gather(
        analysis_task,
        layout_task,
        return_exceptions=True,
    )

    if isinstance(analysis_result, asyncio.CancelledError):
        raise analysis_result
    if isinstance(analysis_result, BaseException):
        raise analysis_result
    analysis=dict(analysis_result or {})

    layout_warning=''
    if isinstance(layout_result, asyncio.CancelledError):
        raise layout_result
    if isinstance(layout_result, BaseException):
        contract={}
        layout_warning=(
            '정적 Layout 보강 분석을 완료하지 못했습니다: '
            f'{str(layout_result) or type(layout_result).__name__}. '
            'Theme 토큰 분석 결과를 유지하고 Chrome CDP 보강 분석을 계속합니다.'
        )
    else:
        contract=dict(layout_result or {})

    _apply_layout_convenience(analysis, contract)
    source_meta=dict(analysis.get('source_meta') or {})
    fetch_warnings=list(context.get('warnings') or [])
    if layout_warning:
        fetch_warnings.append(layout_warning)
    source_meta.update({
        'layout_contract':contract,
        'layout_css_files':int(context.get('css_files') or 0),
        'network_passes':1,
        'stylesheet_only':True,
        'parallel_stylesheet_fetch':True,
        'parallel_static_layout_workers':True,
        'stylesheet_candidates':len(context.get('stylesheet_urls') or []),
        'fetch_warnings':fetch_warnings,
        'layout_worker_mode':'KILLABLE_PROCESS',
        'layout_worker_status':'success' if contract else ('degraded' if layout_warning else 'empty'),
    })
    analysis['source_meta']=source_meta
    return analysis


async def analyze_theme_hybrid(url: str) -> dict:
    """Analyze one public site with independent static and rendered branches.

    A modern SPA may block httpx, return only an application shell, or expose its
    real palette only after JavaScript runs. Conversely Chrome startup can fail while
    static CSS is still perfectly usable. Neither branch is fatal by itself.
    """
    static_task=asyncio.create_task(_analyze_static_theme(url))
    browser_task=asyncio.create_task(analyze_rendered_theme_layout(url))

    async def collect_static() -> tuple[dict, str]:
        try:
            result=await asyncio.wait_for(static_task,timeout=_STATIC_BRANCH_TIMEOUT_SECONDS)
            return dict(result or {}),''
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            if not static_task.done(): static_task.cancel()
            return {},f'정적 HTML/CSS 분석이 내부 제한 {_STATIC_BRANCH_TIMEOUT_SECONDS}초를 초과하여 렌더링 분석 결과로 계속합니다.'
        except Exception as exc:
            return {},f'정적 HTML/CSS 분석 실패: {str(exc) or type(exc).__name__}. 렌더링 분석 결과로 계속합니다.'

    async def collect_browser() -> tuple[dict, dict, str]:
        try:
            result=await asyncio.wait_for(browser_task,timeout=_BROWSER_BRANCH_TIMEOUT_SECONDS)
            result=dict(result or {})
            analysis=dict(result.get('analysis') or {})
            contract=dict(result.get('contract') or {})
            warning=str(result.get('warning') or '')
            if not result.get('ok') and not warning:
                warning=f"Chrome 렌더링 분석 실패: {result.get('status') or 'failed'}"
            return analysis,contract,warning
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            if not browser_task.done(): browser_task.cancel()
            return {},{},f'Chrome 렌더링 분석이 내부 제한 {_BROWSER_BRANCH_TIMEOUT_SECONDS}초를 초과했습니다.'
        except Exception as exc:
            return {},{},f'Chrome 렌더링 분석 실패: {str(exc) or type(exc).__name__}'

    try:
        (static_analysis,static_warning),(browser_analysis,browser_contract,browser_warning)=await asyncio.gather(
            collect_static(),collect_browser()
        )
    except asyncio.CancelledError:
        for task in (static_task,browser_task):
            if not task.done(): task.cancel()
        await asyncio.gather(static_task,browser_task,return_exceptions=True)
        raise

    warnings=[warning for warning in (static_warning,browser_warning) if warning]
    usable=[row for row in (static_analysis,browser_analysis) if isinstance(row,dict) and row.get('tokens')]
    if not usable:
        detail=' | '.join(warnings) or '정적 분석과 Chrome 렌더링 분석에서 유효한 Theme 결과를 만들지 못했습니다.'
        raise RuntimeError(detail)

    if len(usable)>1:
        analysis=merge_theme_analyses(usable)
        # preserve URL provenance/source metadata after canonical merge
        analysis['analysis_source']='URL'
        analysis['source_url']=str(browser_analysis.get('source_url') or static_analysis.get('source_url') or url)
    else:
        analysis=deepcopy(usable[0])

    static_contract=dict(((static_analysis.get('layout_rules') or {}).get('layoutContract') or {})) if static_analysis else {}
    merged_contract=_merge_contract(static_contract,browser_contract)
    _apply_layout_convenience(analysis,merged_contract)

    source_meta={}
    if static_analysis:
        source_meta.update(dict(static_analysis.get('source_meta') or {}))
    browser_meta=dict(browser_analysis.get('source_meta') or {}) if browser_analysis else {}
    source_meta.update({f'browser_{key}':value for key,value in browser_meta.items() if key not in source_meta})
    source_meta.update({
        'analysis_pipeline':'PARALLEL_STATIC_HTML_CSS_AND_CHROME_RENDERED_COMPUTED_STYLE',
        'hard_timeout_seconds':_ANALYSIS_HARD_TIMEOUT_SECONDS,
        'static_branch_timeout_seconds':_STATIC_BRANCH_TIMEOUT_SECONDS,
        'browser_branch_timeout_seconds':_BROWSER_BRANCH_TIMEOUT_SECONDS,
        'static_analysis_status':'success' if static_analysis else 'degraded',
        'browser_analysis_status':'success' if browser_analysis else 'degraded',
        'browser_analysis_ok':bool(browser_analysis),
        'static_analysis_ok':bool(static_analysis),
        'partial_success':not (bool(static_analysis) and bool(browser_analysis)),
        'analysis_completeness':'full' if static_analysis and browser_analysis else ('rendered_only' if browser_analysis else 'static_only'),
        'analysis_warnings':warnings,
        'fetch_warnings':list(dict(static_analysis.get('source_meta') or {}).get('fetch_warnings') or [])+warnings if static_analysis else warnings,
        'rendered_layout_contract':browser_contract,
        'worker_isolation':'PROCESS_TREE_KILLABLE',
    })
    analysis['source_meta']=source_meta
    return analysis



analyze_theme_with_layout_contract=analyze_theme_hybrid
