from __future__ import annotations

import asyncio
import re
import uuid
from collections import Counter
from urllib.parse import urlparse

from app.services.chromium_browser_service import chromium_browser_manager
from app.services.ui_theme_service import _default_tokens, _luminance, _normalize_color, _saturation, build_rules

_BROWSER_START_TIMEOUT = 22
_BROWSER_ANALYSIS_TIMEOUT = 32
_STABILIZE_SECONDS = 2.0
_MAX_ELEMENTS = 180


def _same_host(left: str, right: str) -> bool:
    try:
        return (urlparse(left).hostname or "").casefold() == (urlparse(right).hostname or "").casefold()
    except Exception:
        return False


def _snapshot_script(max_elements: int = _MAX_ELEMENTS) -> str:
    return fr"""
() => {{
  const limit={int(max_elements)};
  const selectors=[
    'html','body','header','nav','aside','main','section','article','button','input','select','textarea',
    '[role="button"]','[role="menu"]','[role="menuitem"]','[role="dialog"]','[role="navigation"]','[aria-expanded]',
    '[class*="card"]','[class*="surface"]','a[href]'
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
    const iconCandidates=Array.from(el.querySelectorAll('svg,img,[class*="icon"],[data-testid*="icon"],[aria-hidden="true"]')).filter(node=>{{
      const ir=node.getBoundingClientRect(); const is=getComputedStyle(node);
      return ir.width>0&&ir.height>0&&ir.width<=64&&ir.height<=64&&is.display!=='none'&&is.visibility!=='hidden';
    }});
    const iconEl=iconCandidates[0]||null;
    const ir=iconEl?iconEl.getBoundingClientRect():null;
    const iconSide=ir?(ir.x+ir.width/2 <= r.x+r.width/2?'left':'right'):'';
    interesting.push({{
      tag:el.tagName.toLowerCase(),
      role:el.getAttribute('role')||'',
      text:(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,120),
      ariaLabel:el.getAttribute('aria-label')||'',
      ariaExpanded:el.getAttribute('aria-expanded')||'',
      ariaCurrent:el.getAttribute('aria-current')||'',
      ariaSelected:el.getAttribute('aria-selected')||'',
      dataState:el.getAttribute('data-state')||'',
      href:el.getAttribute('href')||'',
      navigationContext:Boolean(el.closest('nav,aside,[role="navigation"],[role="menu"],[role="menuitem"],[class*="menu"],[class*="nav"]')),
      cls:String(el.className||'').slice(0,180),
      rect:{{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}},
      icon:{{
        detected:Boolean(iconEl),count:iconCandidates.length,tag:iconEl?iconEl.tagName.toLowerCase():'',
        width:ir?Math.round(ir.width):0,height:ir?Math.round(ir.height):0,side:iconSide
      }},
      style:{{
        display:s.display,position:s.position,background:s.backgroundColor,color:s.color,
        borderColor:s.borderColor,borderRadius:s.borderRadius,fontFamily:s.fontFamily,
        fontSize:s.fontSize,fontWeight:s.fontWeight,boxShadow:s.boxShadow,zIndex:s.zIndex,
        transform:s.transform,transformOrigin:s.transformOrigin,opacity:s.opacity,filter:s.filter,gap:s.gap,columnGap:s.columnGap,padding:s.padding,
        alignItems:s.alignItems,justifyContent:s.justifyContent,textDecoration:s.textDecoration,outline:s.outline,
        borderTop:s.borderTop,borderRight:s.borderRight,borderBottom:s.borderBottom,borderLeft:s.borderLeft,
        transition:s.transition,transitionProperty:s.transitionProperty,transitionDuration:s.transitionDuration,
        transitionTimingFunction:s.transitionTimingFunction,transitionDelay:s.transitionDelay,
        animationName:s.animationName,animationDuration:s.animationDuration,animationTimingFunction:s.animationTimingFunction,
        animationDelay:s.animationDelay,animationIterationCount:s.animationIterationCount,animationFillMode:s.animationFillMode,
        letterSpacing:s.letterSpacing
      }}
    }});
  }};
  nodes.forEach(add);
  document.querySelectorAll('*').forEach(el=>{{
    if(interesting.length>=limit)return;
    const s=getComputedStyle(el);
    if(s.position==='fixed'||s.position==='sticky')add(el);
  }});
  const rootStyle=getComputedStyle(document.documentElement);
  const bodyStyle=getComputedStyle(document.body||document.documentElement);
  const rootVars={{}};
  for(let i=0;i<rootStyle.length && Object.keys(rootVars).length<160;i+=1){{
    const name=rootStyle[i];
    if(!name||!name.startsWith('--'))continue;
    if(!/(color|background|surface|border|accent|primary|secondary|brand|text|font|radius|shadow)/i.test(name))continue;
    const value=rootStyle.getPropertyValue(name).trim();
    if(value&&value.length<=220)rootVars[name]=value;
  }}
  return {{
    url:location.href,title:document.title,viewport:{{width:innerWidth,height:innerHeight}},
    body:{{scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight}},
    pageStyle:{{background:bodyStyle.backgroundColor,color:bodyStyle.color,fontFamily:bodyStyle.fontFamily,fontSize:bodyStyle.fontSize}},
    rootVars,
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


_INTERACTION_PROBE_SCRIPT = r"""
el => {
  const styleOf=(pseudo=null)=>{
    const s=getComputedStyle(el,pseudo);
    return {
      background:s.backgroundColor,color:s.color,borderColor:s.borderColor,borderRadius:s.borderRadius,
      boxShadow:s.boxShadow,fontWeight:s.fontWeight,fontSize:s.fontSize,lineHeight:s.lineHeight,
      padding:s.padding,transform:s.transform,transformOrigin:s.transformOrigin,opacity:s.opacity,filter:s.filter,
      textDecoration:s.textDecoration,outline:s.outline,borderTop:s.borderTop,borderRight:s.borderRight,
      borderBottom:s.borderBottom,borderLeft:s.borderLeft,transition:s.transition,
      transitionProperty:s.transitionProperty,transitionDuration:s.transitionDuration,
      transitionTimingFunction:s.transitionTimingFunction,transitionDelay:s.transitionDelay,
      animationName:s.animationName,animationDuration:s.animationDuration,
      animationTimingFunction:s.animationTimingFunction,animationDelay:s.animationDelay,
      animationIterationCount:s.animationIterationCount,animationFillMode:s.animationFillMode,
      letterSpacing:s.letterSpacing,content:s.content,width:s.width,height:s.height,position:s.position
    };
  };
  return {
    text:(el.innerText||el.textContent||el.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim().slice(0,80),
    ariaCurrent:el.getAttribute('aria-current')||'',ariaSelected:el.getAttribute('aria-selected')||'',
    dataState:el.getAttribute('data-state')||'',cls:String(el.className||'').slice(0,180),
    style:styleOf(null),before:styleOf('::before'),after:styleOf('::after')
  };
}
"""


def _collect_hover_probes(page, *, max_probes: int = 5) -> list[dict]:
    """Capture real rendered menu hover state without clicking/navigation.

    This complements static CSS extraction for React/Next/SPA sites whose interaction
    rules are generated at runtime or only become visible after hydration.
    """
    probes: list[dict] = []
    selector=(
        'nav a,nav button,aside a,aside button,'
        '[role="navigation"] a,[role="navigation"] button,[role="menuitem"]'
    )
    try:
        locator=page.locator(selector)
        count=min(int(locator.count()),40)
    except Exception:
        return probes
    seen: set[str] = set()
    for index in range(count):
        if len(probes)>=max_probes:
            break
        item=locator.nth(index)
        try:
            if not item.is_visible(timeout=250):
                continue
            before=dict(item.evaluate(_INTERACTION_PROBE_SCRIPT) or {})
            label=str(before.get('text') or '').strip()
            if not label or len(label)>64 or label.casefold() in seen:
                continue
            seen.add(label.casefold())
            item.hover(timeout=1_200)
            page.wait_for_timeout(180)
            hover=dict(item.evaluate(_INTERACTION_PROBE_SCRIPT) or {})
            probes.append({'label':label,'before':before,'hover':hover})
            try:
                page.mouse.move(2,2)
                page.wait_for_timeout(45)
            except Exception:
                pass
        except Exception:
            continue
    return probes


def _browser_snapshot_sync(cdp_endpoint: str, target_url: str) -> dict:
    from playwright.sync_api import sync_playwright

    # sync_playwright().stop() disconnects this client. Do not call browser.close() on a
    # connect_over_cdp Browser because AgentStudio owns and reuses that Chrome process.
    playwright=sync_playwright().start()
    browser=None
    try:
        browser=playwright.chromium.connect_over_cdp(cdp_endpoint, timeout=10_000)
        page=_pick_page(browser,target_url)
        if page is None:
            raise RuntimeError('CDP Theme 분석 페이지를 찾을 수 없습니다.')
        page.set_default_timeout(5_000)
        desktop=page.evaluate(_snapshot_script())
        hover_probes=_collect_hover_probes(page,max_probes=5)
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
                mobile_hover_probes=_collect_hover_probes(page,max_probes=5)
                known={str(row.get('label') or '').casefold() for row in hover_probes}
                hover_probes.extend(row for row in mobile_hover_probes if str(row.get('label') or '').casefold() not in known)
        except Exception:
            menu_opened=False
        mobile_after=page.evaluate(_snapshot_script()) if menu_opened else mobile_before
        return {'desktop':desktop,'mobile':mobile_after,'mobile_before':mobile_before,'menu_opened':menu_opened,'hover_probes':hover_probes}
    finally:
        try:
            playwright.stop()
        except Exception:
            pass


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
    # Prefer the rendered mobile drawer after it has been opened. Modern sites such as
    # GitHub often expose the real navigation structure (including icon+text items) only
    # in the responsive drawer, while desktop <nav> containers collapse many labels into
    # one innerText value. Keep the old string list for compatibility and add item_details.
    menu_candidates=[]
    raw_candidates=[*mrows,*drows] if raw.get('menu_opened') else [*drows,*mrows]
    candidate_rows=[row for row in raw_candidates if row.get('navigationContext')] + [row for row in raw_candidates if not row.get('navigationContext')]
    seen_menu_labels=set()
    for row in candidate_rows:
        tag=str(row.get('tag') or '').casefold()
        role=str(row.get('role') or '').casefold()
        if tag not in {'a','button'} and role!='menuitem':
            continue
        label=str(row.get('text') or row.get('ariaLabel') or '').strip()
        if not label or len(label)>48:
            continue
        key=label.casefold()
        if key in seen_menu_labels:
            continue
        # Skip generic mobile toggle controls; they are navigation chrome, not items.
        if key in {'menu','navigation','close','open menu','닫기','메뉴'}:
            continue
        seen_menu_labels.add(key)
        icon=dict(row.get('icon') or {})
        style=dict(row.get('style') or {})
        menu_candidates.append({
            'label':label,
            'has_icon':bool(icon.get('detected')),
            'icon':icon,
            'gap':str(style.get('gap') or style.get('columnGap') or ''),
            'padding':str(style.get('padding') or ''),
            'display':str(style.get('display') or ''),
            'align_items':str(style.get('alignItems') or ''),
            'transition':str(style.get('transition') or ''),
            'transform':str(style.get('transform') or ''),
            'opacity':str(style.get('opacity') or ''),
        })
        if len(menu_candidates)>=12:
            break

    menu_items=[item['label'] for item in menu_candidates]
    if not menu_items:
        for row in [*navs,*[r for r in drows if r.get('tag')=='a']]:
            label=str(row.get('text') or '').strip()
            if label and len(label)<=48 and label not in menu_items:
                menu_items.append(label)
            if len(menu_items)>=10:
                break

    icon_rows=[item for item in menu_candidates if item.get('has_icon')]
    icon_ratio=(len(icon_rows)/len(menu_candidates)) if menu_candidates else 0.0
    icon_sizes=[int((item.get('icon') or {}).get('width') or 0) for item in icon_rows if int((item.get('icon') or {}).get('width') or 0)>0]
    icon_size=sorted(icon_sizes)[len(icon_sizes)//2] if icon_sizes else 0
    icon_sides=[str((item.get('icon') or {}).get('side') or '') for item in icon_rows]
    icon_side=Counter([side for side in icon_sides if side]).most_common(1)[0][0] if any(icon_sides) else 'left'
    navigation_mode='icon_text' if len(icon_rows)>=2 and icon_ratio>=0.35 else 'text'
    hover_probes=[probe for probe in list(raw.get('hover_probes') or []) if isinstance(probe,dict)]
    motion_probe_labels=[str(probe.get('label') or '') for probe in hover_probes if str(probe.get('label') or '').strip()]

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
        'version':4,
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
            'item_details':menu_candidates,
            'presentation':{
                'mode':navigation_mode,
                'icon_text_detected':navigation_mode=='icon_text',
                'icon_ratio':round(icon_ratio,3),
                'icon_side':icon_side,
                'icon_size':icon_size,
                'motion_probe_count':len(hover_probes),
                'motion_detected':bool(hover_probes),
                'motion_probe_labels':motion_probe_labels[:5],
                'source':'CHROME_CDP_RENDERED_DOM',
            },
            'use_source_items_in_preview':bool(menu_items),
        },
        'evidence':{
            'desktop_element_count':len(drows),
            'mobile_element_count':len(mrows),
            'rendered_url':desktop.get('url') or '',
            'title':desktop.get('title') or '',
        },
    }



_COLOR_VALUE_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]{3,100}\)")
_RADIUS_VALUE_RE = re.compile(r"([0-9.]+)px", re.IGNORECASE)


def _colors_from_value(value: object) -> list[str]:
    result: list[str] = []
    for raw in _COLOR_VALUE_RE.findall(str(value or "")):
        color = _normalize_color(raw)
        if color and color not in result:
            result.append(color)
    return result


def _motion_has_duration(value: object) -> bool:
    raw=str(value or '').strip().lower()
    if not raw or raw in {'none','normal'}:
        return False
    for amount,unit in re.findall(r'([0-9]*\.?[0-9]+)\s*(ms|s)\b',raw):
        try:
            seconds=float(amount)/(1000.0 if unit=='ms' else 1.0)
        except ValueError:
            continue
        if seconds>0.001:
            return True
    return False


def _style_to_rule(style: dict) -> dict:
    style=dict(style or {})
    result={}
    for source,target in (
        ('background','background'),('color','color'),('borderColor','border'),
        ('boxShadow','boxShadow'),('fontWeight','fontWeight'),('fontSize','fontSize'),
        ('lineHeight','lineHeight'),('padding','padding'),('transform','transform'),
        ('transformOrigin','transformOrigin'),('textDecoration','textDecoration'),
        ('outline','outline'),('filter','filter'),('letterSpacing','letterSpacing'),
        ('borderTop','borderTop'),('borderRight','borderRight'),('borderBottom','borderBottom'),('borderLeft','borderLeft'),
    ):
        value=style.get(source)
        if value in (None,'','rgba(0, 0, 0, 0)','transparent'):
            continue
        if source in {'background','color','borderColor'}:
            colors=_colors_from_value(value)
            if colors:
                result[target]=colors[0]
        elif source in {'boxShadow','transform','filter','textDecoration','outline'} and str(value).strip().lower()=='none':
            continue
        elif source.startswith('border') and source!='borderColor' and ('0px' in str(value) or str(value).strip().lower()=='none'):
            continue
        else:
            result[target]=value
    radius=str(style.get('borderRadius') or '')
    match=_RADIUS_VALUE_RE.search(radius)
    if match:
        try: result['radius']=int(round(float(match.group(1))))
        except ValueError: pass
    opacity=str(style.get('opacity') or '').strip()
    if opacity:
        try:
            number=float(opacity)
            if abs(number-1.0)>0.001:
                result['opacity']=round(number,4)
        except ValueError:
            pass

    transition=str(style.get('transition') or '').strip()
    if _motion_has_duration(transition):
        result['transition']=transition[:260]
    else:
        duration=str(style.get('transitionDuration') or '').strip()
        if _motion_has_duration(duration):
            prop=str(style.get('transitionProperty') or 'all').strip() or 'all'
            timing=str(style.get('transitionTimingFunction') or 'ease').strip() or 'ease'
            delay=str(style.get('transitionDelay') or '').strip()
            result['transition']=' '.join(part for part in (prop,duration,timing,delay) if part)[:260]

    animation_name=str(style.get('animationName') or '').strip()
    animation_duration=str(style.get('animationDuration') or '').strip()
    if animation_name and animation_name!='none' and _motion_has_duration(animation_duration):
        timing=str(style.get('animationTimingFunction') or 'ease').strip() or 'ease'
        delay=str(style.get('animationDelay') or '').strip()
        iteration=str(style.get('animationIterationCount') or '1').strip()
        fill=str(style.get('animationFillMode') or '').strip()
        result['animation']=' '.join(part for part in (animation_name,animation_duration,timing,delay,iteration,fill) if part)[:260]
        # Source keyframes are intentionally not copied. Reuse their timing as a safe
        # motion transition so the preview still demonstrates the site's interaction feel.
        if 'transition' not in result:
            result['motionTransition']=' '.join(part for part in ('all',animation_duration,timing,delay) if part)[:220]
    return result


def _computed_style_rules(rows: list[dict], tag_names: set[str]) -> dict:
    for row in rows:
        if str(row.get('tag') or '').casefold() not in tag_names:
            continue
        result=_style_to_rule(dict(row.get('style') or {}))
        if result:
            return result
    return {}


def _menu_row(row: dict) -> bool:
    tag=str(row.get('tag') or '').casefold()
    role=str(row.get('role') or '').casefold()
    return bool(row.get('navigationContext')) and (tag in {'a','button'} or role=='menuitem')


def _active_menu_row(row: dict) -> bool:
    if not _menu_row(row):
        return False
    if str(row.get('ariaCurrent') or '').strip().casefold() not in {'','false'}:
        return True
    if str(row.get('ariaSelected') or '').strip().casefold()=='true':
        return True
    if str(row.get('dataState') or '').strip().casefold() in {'active','selected','open','current'}:
        return True
    return bool(re.search(r'(^|[\s_-])(active|selected|current)([\s_-]|$)',str(row.get('cls') or ''),re.I))


def _hover_probe_rules(raw: dict) -> tuple[dict,dict,str]:
    best_before={}
    best_hover={}
    best_label=''
    best_score=-1
    keys={'background','color','border','radius','boxShadow','fontWeight','fontSize','lineHeight','padding','transform','opacity','filter','textDecoration','outline','borderTop','borderRight','borderBottom','borderLeft','letterSpacing'}
    for probe in list(raw.get('hover_probes') or []):
        if not isinstance(probe,dict):
            continue
        before=_style_to_rule(dict((probe.get('before') or {}).get('style') or {}))
        hover=_style_to_rule(dict((probe.get('hover') or {}).get('style') or {}))
        changed=sum(1 for key in keys if before.get(key)!=hover.get(key) and hover.get(key) not in (None,''))
        has_motion=bool(hover.get('transition') or before.get('transition') or hover.get('motionTransition') or before.get('motionTransition'))
        score=changed*10+(4 if has_motion else 0)
        if score>best_score and (changed>0 or has_motion):
            best_before,best_hover,best_label,best_score=before,hover,str(probe.get('label') or ''),score
    return best_before,best_hover,best_label


def _derive_rendered_theme_analysis(raw: dict, target_url: str) -> dict:
    desktop=dict(raw.get('desktop') or {})
    rows=_visible_rows(desktop)
    mobile_rows=_visible_rows(dict(raw.get('mobile') or {}))
    root_vars=dict(desktop.get('rootVars') or {})
    page_style=dict(desktop.get('pageStyle') or {})

    weighted_colors: list[str] = []
    for value in root_vars.values():
        weighted_colors.extend(_colors_from_value(value))
    for key in ('background','color'):
        weighted_colors.extend(_colors_from_value(page_style.get(key)))
    for row in rows:
        style=dict(row.get('style') or {})
        for key in ('background','color','borderColor','boxShadow'):
            weighted_colors.extend(_colors_from_value(style.get(key)))

    counts=Counter(weighted_colors)
    palette=[color for color,_ in counts.most_common(24)]
    tokens=_default_tokens()
    if palette:
        darkest=min(palette,key=_luminance)
        lightest=max(palette,key=_luminance)
        saturated=[c for c in palette if 0.10 < _luminance(c) < 0.94 and _saturation(c)>=0.22]
        primary=max(saturated or palette,key=lambda c:(_saturation(c),counts[c]))
        page_backgrounds=_colors_from_value(page_style.get('background'))
        background=page_backgrounds[0] if page_backgrounds else (max(palette,key=lambda c:counts[c]) if palette else lightest)
        # Transparent/very dark backgrounds from overlay elements should not replace the actual page surface.
        if _luminance(background)<0.08 and _luminance(lightest)>0.90:
            background=lightest
        surface_candidates=[c for c in palette if abs(_luminance(c)-_luminance(background))<0.18]
        surface=surface_candidates[0] if surface_candidates else lightest
        border_candidates=[c for c in palette if 0.35 <= _luminance(c) <= 0.94 and _saturation(c)<0.30 and c not in {background,surface}]
        secondary_candidates=[c for c in palette if 0.16 <= _luminance(c) <= 0.70 and c!=darkest]
        tokens['colors'].update({
            'primary':primary,'background':background,'surface':surface,'textPrimary':darkest,
            'textSecondary':secondary_candidates[0] if secondary_candidates else tokens['colors']['textSecondary'],
            'border':border_candidates[0] if border_candidates else tokens['colors']['border'],
        })

    fonts=[]
    if page_style.get('fontFamily'): fonts.append(str(page_style.get('fontFamily')))
    fonts.extend(str((row.get('style') or {}).get('fontFamily') or '') for row in rows)
    fonts=[font for font in fonts if font.strip()]
    if fonts:
        tokens['typography']['fontFamily']=Counter(fonts).most_common(1)[0][0][:300]

    radii=[]
    for row in rows:
        match=_RADIUS_VALUE_RE.search(str((row.get('style') or {}).get('borderRadius') or ''))
        if match:
            try:
                value=int(round(float(match.group(1))))
                if 0<=value<=64:radii.append(value)
            except ValueError: pass
    if radii:
        common=Counter(radii).most_common(1)[0][0]
        tokens['radius'].update({'button':common,'card':common,'input':common})

    components,layout=build_rules(tokens)
    button=_computed_style_rules(rows,{'button'})
    input_rule=_computed_style_rules(rows,{'input','select','textarea'})
    menu_rows=[row for row in [*rows,*mobile_rows] if _menu_row(row)]
    nav_rule=_style_to_rule(dict((menu_rows[0].get('style') or {}))) if menu_rows else _computed_style_rules(rows,{'nav','a'})
    active_row=next((row for row in menu_rows if _active_menu_row(row)),None)
    active_rule=_style_to_rule(dict((active_row or {}).get('style') or {})) if active_row else {}
    hover_before,hover_rule,hover_label=_hover_probe_rules(raw)
    card=_computed_style_rules(rows,{'section','article','main'})
    if button:
        components['button']={**dict(components.get('button') or {}),**button,'source':'CHROME_COMPUTED_STYLE'}
    if input_rule:
        components['input']={**dict(components.get('input') or {}),**input_rule,'source':'CHROME_COMPUTED_STYLE'}
    if nav_rule or hover_rule or active_rule:
        menu=dict(components.get('menu') or {})
        if nav_rule or hover_before:
            menu['normal']={**dict(menu.get('normal') or {}),**nav_rule,**hover_before}
        if hover_rule:
            # transition is often declared on the normal state while hover only changes
            # transform/color/shadow. Carry the timing over so Preview motion is faithful.
            if not hover_rule.get('transition') and not hover_rule.get('motionTransition'):
                motion=hover_before.get('transition') or hover_before.get('motionTransition')
                if motion:
                    hover_rule={**hover_rule,'transition':motion}
            menu['hover']={**dict(menu.get('hover') or {}),**hover_rule}
        if active_rule:
            menu['active']={**dict(menu.get('active') or {}),**active_rule}
        menu['source']='CHROME_INTERACTION_PROBE' if hover_rule else 'CHROME_COMPUTED_STYLE'
        if hover_label:
            menu['probe_label']=hover_label
        components['menu']=menu
    if card:
        components['card']={**dict(components.get('card') or {}),**card,'source':'CHROME_COMPUTED_STYLE'}
    evidence={
        **dict(components.get('_evidence') or {}),
        'theme.rendered':{'status':'confirmed','source':'CHROME_COMPUTED_STYLE','confidence':0.94},
    }
    if nav_rule:
        evidence['menu.normal']={'status':'confirmed','source':'CHROME_COMPUTED_STYLE','confidence':0.93}
    if hover_rule:
        evidence['menu.hover']={'status':'confirmed','source':'CHROME_INTERACTION_PROBE','confidence':0.97,'selector':hover_label}
    if active_rule:
        evidence['menu.active']={'status':'confirmed','source':'CHROME_ACTIVE_STATE','confidence':0.95}
    components['_evidence']=evidence
    return {
        'tokens':tokens,
        'component_rules':components,
        'layout_rules':layout,
        'preview_colors':palette[:8],
        'analysis_source':'URL',
        'source_url':str(desktop.get('url') or target_url or ''),
        'source_meta':{
            'analysis':'Chrome CDP rendered DOM/computed-style design-token extraction',
            'browser_rendered_theme':True,
            'rendered_element_count':len(rows),
            'css_custom_property_count':len(root_vars),
            'interaction_hover_probe_count':len(list(raw.get('hover_probes') or [])),
            'interaction_hover_probe_label':hover_label,
            'rendered_title':str(desktop.get('title') or ''),
        },
    }


async def analyze_rendered_theme_layout(url: str) -> dict:
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
        analysis=_derive_rendered_theme_analysis(raw,url)
        return {'ok':True,'status':'success','contract':contract,'analysis':analysis,'warning':''}
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
