from __future__ import annotations

import asyncio
import uuid

from app.services.chromium_browser_service import chromium_browser_manager
from app.services.ui_theme_browser_analysis_service import _derive_browser_contract, _derive_rendered_theme_analysis
from app.services.ui_theme_killable_process_service import run_theme_worker

_BROWSER_START_TIMEOUT = 22
_BROWSER_ANALYSIS_TIMEOUT = 34
_STABILIZE_SECONDS = 2.0


async def analyze_rendered_theme_layout(url: str) -> dict:
    """Rendered Theme analysis whose synchronous Playwright work is process-isolated."""
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
        raw=await run_theme_worker(
            'browser_snapshot',
            {'cdp_endpoint':cdp,'target_url':url},
            timeout=_BROWSER_ANALYSIS_TIMEOUT,
        )
        contract=_derive_browser_contract(raw)
        analysis=_derive_rendered_theme_analysis(raw,url)
        return {
            'ok':True,
            'status':'success',
            'contract':contract,
            'analysis':analysis,
            'warning':'',
            'worker_mode':'KILLABLE_PROCESS',
        }
    except (asyncio.TimeoutError, TimeoutError):
        return {
            'ok':False,
            'status':'timeout',
            'contract':{},
            'warning':'Chrome CDP 동적 분석 제한시간을 초과했습니다. Worker Process를 종료하고 정적 분석 결과를 사용합니다.',
            'worker_mode':'KILLABLE_PROCESS',
        }
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return {
            'ok':False,
            'status':'failed',
            'contract':{},
            'warning':f'Chrome CDP 동적 분석 실패: {str(exc) or type(exc).__name__}. Worker Process를 종료하고 정적 분석 결과를 사용합니다.',
            'worker_mode':'KILLABLE_PROCESS',
        }
    finally:
        try:
            await asyncio.wait_for(chromium_browser_manager.close(session_id),timeout=8)
        except Exception:
            pass
