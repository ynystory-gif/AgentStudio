from __future__ import annotations

import asyncio
import re
import uuid
from urllib.parse import urlparse

from app.services.chromium_browser_service import chromium_browser_manager

_BROWSER_START_TIMEOUT = 22
_BROWSER_ANALYSIS_TIMEOUT = 32
_STABILIZE_SECONDS = 2.0
_MAX_ELEMENTS = 120


def _same_host(left: str, right: str) -> bool:
    try:
        return (urlparse(left).hostname or "").casefold() == (urlparse(right).hostname or "").casefold()
    except Exception:
        return False


def _snapshot_script(max_elements: int = _MAX_ELEMENTS) -> str:
    # Keep the browser-side payload compact. We intentionally inspect high-value visible
    # controls/layout nodes instead of serialising the entire DOM of modern SPA sites.
    return f"""
() => {{
  const limit={int(max_elements)};
  const selectors=[
    'header','nav','aside','main','button','input','select','textarea',
    '[role="menu"]','[role="dialog"]','[role="navigation"]','[aria-expanded]',
    'a[href]'
  ].join(',');
  const nodes=Array.from(document.querySelectorAll(selectors));
  const interesting=[];
  const seen=new Set();
  const add=(el)=>{{
    if(!el || seen.has(el) || interesting.length>=limit)return;
    seen.add(el);
    const r=el.getBoundingClientRect();
    const s=getComputedStyle(el);
    const visible=r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity||1)>0.01;
    const positioned=['fixed','sticky'].includes(s.position);
    const semantic=['HEADER','NAV','ASIDE','MAIN','BUTTON','INPUT','SELECT','TEXTAREA'].includes(el.tagName) || el.hasAttribute('role') || el.hasAttribute('aria-expanded');
    if(!visible && !positioned)return;
    if(!semantic && !positioned && el.tagName!=='A')return;
    interesting.push({{
      tag:el.tagName.toLowerCase(),
      role:el.getAttribute('role')||'',
      text:(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,120),
      ariaLabel:el.getAttribute('aria-label')||'',
      ariaExpanded:el.getAttribute('aria-expanded')||'',
      cls:String(el.className||'').slice(0,180),
      rect:{{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}},
      style:{{
        display:s.display,position:s.position,background:s.backgroundColor,color:s.color,
        borderColor:s.borderColor,borderRadius:s.borderRadius,fontFamily:s.fontFamily,
        fontSize:s.fontSize,fontWeight:s.fontWeight,boxShadow:s.boxShadow,zIndex:s.zIndex,
        transform:s.transform,opacity:s.opacity
      }}
    }});
  }};
  nodes.forEach(add);
  document.querySelectorAll('*').forEach(el=>{{
    if(interesting.length>=limit)return;
    const s=getComputedStyle(el);
    if(s.position==='fixed'||s.position==='sticky')add(el);
  }});
  return {{
    url:location.href,title:document.title,viewport:{{width:innerWidth,height:innerHeight}},
    body:{{scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight}},
    elements:interesting
  }};
}}
"""


def _pick_page(browser, target_url: str):
    pages=[]
    for context in browser.contexts:
        pages.extend(context.pages)
    exact=[p for p in pages if str(p.url or '').rstrip('/') == str(target_url or '').rstrip('/')]
    if exact:
        return exact[-1]
    same=[p for p in pages if _same_host(str(p.url or ''), target_url)]
    if same:
        return same[-1]
    return pages[-1] if pages else None


def _browser_snapshot_sync(cdp_endpoint: str, target_url: str) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser=playwright.chromium.connect_over_cdp(cdp_endpoint, timeout=10_000)
        try:
            page=_pick_page(browser,target_url)
            if page is None:
                raise RuntimeError('CDP Theme 분석 페이지를 찾을 수 없습니다.')
            page.set_default_timeout(5_000)
            desktop=page.evaluate(_snapshot_script())

            # Mobile pass uses the same dedicated Theme session. No reload/network-idle wait:
            # responsive CSS/JS reacts to viewport changes immediately on modern sites.
            try:
                page.set_viewport_size({'width':390,'height':844})
                page.wait_for_timeout(350)
            except Exception:
                pass
            mobile_before=page.evaluate(_snapshot_script())

            menu_opened=False
            try:
                menu_opened=bool(page.evaluate("""
() => {
  const candidates=Array.from(document.querySelectorAll('button,[role="button"]'));
  const el=candidates.find(node=>{
    const key=((node.getAttribute('aria-label')||'')+' '+(node.textContent||'')+' '+String(node.className||'')).toLowerCase();
    const r=node.getBoundingClientRect();
    return r.width>0&&r.height>0&&(key.includes('menu')||key.includes('navigation')||key.includes('hamburger'));
  });
  if(!el)return false;
  el.click();return true;
}
"""))
                if menu_opened:
                    page.wait_for_timeout(450)
            except Exception:
                menu_opened=False
            mobile_after=page.evaluate(_snapshot_script()) if menu_opened else mobile_before
            return {'desktop':desktop,'mobile':mobile_after,'mobile_before':mobile_before,'menu_opened':menu_opened}
        finally:
            # Disconnect only. The manager owns the Chrome process/session lifecycle.
            browser.close()


def _rect(row: dict) -> dict:
    return dict(row.get('rect') or {}) if isinstance(row,dict) else {}


def _visible_rows(snapshot: dict) -> list[dict]:
    return [row for row in list(snapshot.get('elements') or []) if isinstance(row,dict)]


def _derive_browser_contract(raw: dict) -> dict:
    desktop=dict(raw.get('desktop') or {})
    mobile=dict(raw.get('mobile') or {})
    drows=_visible_rows(desktop)
    mrows=_visible_rows(mobile)
    width=max(1,int((mobile.get('viewport') or {}).get('width') or 390))

    headers=[r for r in drows if r.get('tag')=='header']
    navs=[r for r in drows if r.get('tag')=='nav' or r.get('role')=='navigation']
    asides=[r for r in drows if r.get('tag')=='aside']
    menu_items=[]
    for row in [*navs,*[r for r in drows if r.get('tag')=='a']]:
        text=str(row.get('text') or '').strip()
        if text and len(text)<=48 and text not in menu_items:
            menu_items.append(text)
        if len(menu_items)>=10:break

    drawer_candidates=[]
    for row in mrows:
        style=dict(row.get('style') or {})
        rect=_rect(row)
        rw=float(rect.get('width') or 0)
        rh=float(rect.get('height') or 0)
        if style.get('position')=='fixed' and rw>=width*.45 and rh>=300:
            drawer_candidates.append(row)
    drawer=None
    if drawer_candidates:
        drawer=max(drawer_candidates,key=lambda r:float(_rect(r).get('height') or 0)*float(_rect(r).get('width') or 0))
    drawer_rect=_rect(drawer or {})
    x=float(drawer_rect.get('x') or 0)
    rw=float(drawer_rect.get('width') or 0)
    side='left' if x <= width*.20 else 'right'

    overlay=False
    for row in mrows:
        if row is drawer:continue
        style=dict(row.get('style') or {});rect=_rect(row)
        if style.get('position')=='fixed' and float(rect.get('width') or 0)>=width*.9 and float(rect.get('height') or 0)>=700:
            overlay=True;break

    return {
        'version':3,
        'source':'CHROME_CDP_RENDERED_DOM',
        'header':{
            'detected':bool(headers),
            'height':int(_rect(headers[0]).get('height') or 0) if headers else 0,
        },
        'desktop':{
            'sidebar_present':bool(asides),
            'sidebar_side':'left' if (asides and float(_rect(asides[0]).get('x') or 0)<720) else ('right' if asides else ''),
            'sidebar_width':int(_rect(asides[0]).get('width') or 0) if asides else 0,
        },
        'mobile':{
            'breakpoint_observed':390,
            'drawer':{
                'detected':bool(drawer),
                'side':side if drawer else 'left',
                'width':f'{int(round(rw))}px' if drawer else '',
                'overlay':{'detected':overlay},
                'confidence':0.94 if drawer else 0.0,
            },
            'menu_toggle_opened':bool(raw.get('menu_opened')),
        },
        'navigation':{
            'items':menu_items,
            'use_source_items_in_preview':bool(menu_items),
        },
        'evidence':{
            'desktop_element_count':len(drows),
            'mobile_element_count':len(mrows),
            'rendered_url':desktop.get('url') or '',
            'title':desktop.get('title') or '',
        },
    }


async def analyze_rendered_theme_layout(url: str) -> dict:
    """Best-effort rendered DOM/layout analysis using AgentStudio's existing Chrome CDP runtime.

    This function is deliberately bounded and disposable: a dedicated browser session is
    created for Theme analysis and always closed. Failure is returned as metadata so callers
    can preserve successful static analysis instead of failing the whole Theme import.
    """
    session_id=f'theme-analysis-{uuid.uuid4().hex[:12]}'
    try:
        nav=await asyncio.wait_for(
            chromium_browser_manager.navigate(session_id,url,width=1440,height=900,force_restart=False),
            timeout=_BROWSER_START_TIMEOUT,
        )
        await asyncio.sleep(_STABILIZE_SECONDS)
        state=await asyncio.wait_for(chromium_browser_manager.state(session_id,consume_popups=False),timeout=6)
        cdp=str((state or {}).get('cdp_endpoint') or (nav or {}).get('cdp_endpoint') or '').strip()
        if not cdp:
            raise RuntimeError('Chrome CDP endpoint를 확인할 수 없습니다.')
        raw=await asyncio.wait_for(asyncio.to_thread(_browser_snapshot_sync,cdp,url),timeout=_BROWSER_ANALYSIS_TIMEOUT)
        contract=_derive_browser_contract(raw)
        return {'ok':True,'status':'success','contract':contract,'warning':''}
    except asyncio.TimeoutError:
        return {'ok':False,'status':'timeout','contract':{},'warning':'Chrome CDP 동적 분석 제한시간을 초과했습니다. 정적 분석 결과를 사용합니다.'}
    except Exception as exc:
        return {'ok':False,'status':'failed','contract':{},'warning':f'Chrome CDP 동적 분석 실패: {str(exc) or type(exc).__name__}. 정적 분석 결과를 사용합니다.'}
    finally:
        try:
            await asyncio.wait_for(chromium_browser_manager.close(session_id),timeout=8)
        except Exception:
            pass


def is_dynamic_site_candidate(html: str, static_contract: dict) -> bool:
    source=str(html or '')[:500_000].casefold()
    script_count=len(re.findall(r'<script\b',source))
    dynamic_markers=('__next_data__','/_next/','react','webpack','vite','data-reactroot','application/ld+json')
    marker_hits=sum(1 for marker in dynamic_markers if marker in source)
    drawer=(((static_contract.get('mobile') or {}).get('drawer') or {}) if isinstance(static_contract,dict) else {})
    nav=((static_contract.get('navigation') or {}) if isinstance(static_contract,dict) else {})
    return script_count>=8 or marker_hits>=2 or not bool(drawer.get('detected')) or not bool(nav.get('items'))
