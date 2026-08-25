from __future__ import annotations

"""Dedicated Playwright CDP worker for AgentStudio.

Why a separate process on Windows?
AgentStudio's FastAPI backend intentionally uses WindowsSelectorEventLoopPolicy for
psycopg async compatibility. Playwright's Python driver starts a Node subprocess and
needs the normal Windows Proactor loop. Running Playwright in this helper keeps those
two event-loop requirements isolated from each other.

Protocol: one JSON request per stdin line, one JSON response per stdout line.
No unsolicited stdout is allowed; diagnostics go to stderr.
"""

import asyncio
import base64
import ipaddress
import json
import socket
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, CDPSession, Page, Route, sync_playwright

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 720
MIN_VIEWPORT_WIDTH = 320
MIN_VIEWPORT_HEIGHT = 220
MAX_VIEWPORT_WIDTH = 3840
MAX_VIEWPORT_HEIGHT = 2160


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _error_payload(request_id: int, exc: BaseException) -> dict[str, Any]:
    return {
        "id": request_id,
        "ok": False,
        "error": str(exc),
        "exception_type": type(exc).__name__,
        "exception_repr": repr(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:],
    }


@dataclass
class PopupInfo:
    session_id: str
    url: str
    title: str


@dataclass
class PageState:
    session_id: str
    page: Page
    cdp: CDPSession | None = None
    loading: bool = False
    popups: list[PopupInfo] = field(default_factory=list)
    frame_data: str = ""
    frame_revision: int = 0
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT
    screencast_active: bool = False


class Worker:
    def __init__(self, endpoint: str, storage_state_path: str) -> None:
        self.endpoint = endpoint
        self.storage_state_path = Path(storage_state_path)
        self.pw = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.pages: dict[str, PageState] = {}
        self.allowed_host_cache: dict[str, tuple[float, bool]] = {}

    @staticmethod
    def safe_session_id(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in str(value or ""))[:160]
        return cleaned or f"browser-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def viewport(width: Any, height: Any) -> dict[str, int]:
        try:
            w = int(width or DEFAULT_VIEWPORT_WIDTH)
        except Exception:
            w = DEFAULT_VIEWPORT_WIDTH
        try:
            h = int(height or DEFAULT_VIEWPORT_HEIGHT)
        except Exception:
            h = DEFAULT_VIEWPORT_HEIGHT
        return {
            "width": max(MIN_VIEWPORT_WIDTH, min(MAX_VIEWPORT_WIDTH, w)),
            "height": max(MIN_VIEWPORT_HEIGHT, min(MAX_VIEWPORT_HEIGHT, h)),
        }

    @staticmethod
    def literal_is_private(hostname: str) -> bool:
        host = str(hostname or "").strip().lower().strip("[]")
        if host in {"localhost", "localhost.localdomain"}:
            return True
        try:
            return not ipaddress.ip_address(host).is_global
        except ValueError:
            return False

    def validate_public_target(self, value: str) -> str:
        raw = str(value or "").strip()
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError("외부 Chrome은 http/https URL만 허용합니다.")
        if not parsed.hostname:
            raise RuntimeError("URL에 host가 없습니다.")
        if parsed.username or parsed.password:
            raise RuntimeError("사용자명/비밀번호가 URL에 포함된 주소는 열 수 없습니다.")
        hostname = str(parsed.hostname).strip().lower().strip("[]")
        if self.literal_is_private(hostname):
            raise RuntimeError("localhost/내부 IP는 기존 직접 표시 방식을 사용하세요.")
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise RuntimeError("잘못된 포트입니다.") from exc
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None
        if literal is not None:
            if not literal.is_global:
                raise RuntimeError("공인 IP가 아닌 주소는 차단됩니다.")
            return raw
        cache_key = f"{parsed.scheme}://{hostname}:{port}"
        now = time.time()
        cached = self.allowed_host_cache.get(cache_key)
        if cached and now - cached[0] < 300:
            if not cached[1]:
                raise RuntimeError("공인 인터넷 주소가 아닌 대상은 차단됩니다.")
            return raw
        try:
            infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            self.allowed_host_cache[cache_key] = (now, False)
            raise RuntimeError(f"도메인 주소를 확인할 수 없습니다: {hostname}") from exc
        addresses = {str(info[4][0]) for info in infos if info[4]}
        allowed = bool(addresses) and all(ipaddress.ip_address(addr).is_global for addr in addresses)
        self.allowed_host_cache[cache_key] = (now, allowed)
        if not allowed:
            raise RuntimeError(f"공인 인터넷 주소가 아닌 IP로 해석되는 도메인은 차단됩니다: {hostname}")
        return raw

    def route_guard(self, route: Route) -> None:
        url = str(route.request.url or "")
        parsed = urlparse(url)
        if parsed.scheme in {"data", "blob", "about"}:
            route.continue_()
            return
        if parsed.scheme not in {"http", "https"}:
            route.abort("blockedbyclient")
            return
        try:
            self.validate_public_target(url)
            route.continue_()
        except Exception:
            route.abort("blockedbyclient")

    def websocket_guard(self, ws_route: Any) -> None:
        try:
            raw = str(ws_route.url or "")
            parsed = urlparse(raw)
            if parsed.scheme not in {"ws", "wss"}:
                ws_route.close(code=1008, reason="Blocked by AgentStudio")
                return
            equivalent = ("https" if parsed.scheme == "wss" else "http") + "://" + str(parsed.netloc) + (parsed.path or "/")
            if parsed.query:
                equivalent += "?" + parsed.query
            self.validate_public_target(equivalent)
            ws_route.connect_to_server()
        except Exception:
            try:
                ws_route.close(code=1008, reason="Private/non-public WebSocket blocked")
            except Exception:
                pass

    def connect(self) -> None:
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(self.endpoint, timeout=15000)
        contexts = self.browser.contexts
        self.context = contexts[0] if contexts else None
        if self.context is None:
            raise RuntimeError("Chrome BrowserContext를 얻지 못했습니다.")
        self.context.route("**/*", self.route_guard)
        if hasattr(self.context, "route_web_socket"):
            self.context.route_web_socket("**/*", self.websocket_guard)
        self.restore_storage_state()

    def restore_storage_state(self) -> None:
        if not self.context or not self.storage_state_path.is_file():
            return
        try:
            state = json.loads(self.storage_state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        cookies = state.get("cookies") if isinstance(state, dict) else None
        if isinstance(cookies, list) and cookies:
            try:
                self.context.add_cookies(cookies)
            except Exception:
                pass
        origins = state.get("origins") if isinstance(state, dict) else None
        if isinstance(origins, list) and origins:
            origin_map: dict[str, list[dict[str, str]]] = {}
            for entry in origins:
                if not isinstance(entry, dict):
                    continue
                origin = str(entry.get("origin") or "").strip()
                values = entry.get("localStorage")
                if origin and isinstance(values, list):
                    cleaned = [
                        {"name": str(item["name"]), "value": str(item["value"])}
                        for item in values
                        if isinstance(item, dict) and "name" in item and "value" in item
                    ]
                    if cleaned:
                        origin_map[origin] = cleaned
            if origin_map:
                payload = json.dumps(origin_map, ensure_ascii=False)
                script = """(() => {
                    const states = __STATE__;
                    const items = states[location.origin];
                    if (!items) return;
                    for (const item of items) {
                        try { localStorage.setItem(item.name, item.value); } catch (_) {}
                    }
                })()""".replace("__STATE__", payload)
                try:
                    self.context.add_init_script(script)
                except Exception:
                    pass

    def save_storage_state(self) -> None:
        if not self.context:
            return
        try:
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            self.context.storage_state(path=str(self.storage_state_path))
        except Exception as exc:
            print(f"storage state save failed: {exc!r}", file=sys.stderr, flush=True)

    def register_page_events(self, item: PageState) -> None:
        item.page.on("load", lambda: setattr(item, "loading", False))
        item.page.on("domcontentloaded", lambda: setattr(item, "loading", False))
        item.page.on("popup", lambda popup: self.register_popup(item.session_id, popup))

    def start_screencast(self, item: PageState) -> None:
        if not self.context:
            raise RuntimeError("Chrome BrowserContext가 준비되지 않았습니다.")
        if item.cdp is not None:
            try:
                item.cdp.send("Page.stopScreencast")
            except Exception:
                pass
            try:
                item.cdp.detach()
            except Exception:
                pass
        cdp = self.context.new_cdp_session(item.page)
        item.cdp = cdp

        def on_frame(event: dict[str, Any]) -> None:
            data = str(event.get("data") or "")
            if data:
                item.frame_data = data
                item.frame_revision += 1
            sid = event.get("sessionId")
            if sid is not None:
                try:
                    cdp.send("Page.screencastFrameAck", {"sessionId": sid})
                except Exception:
                    pass

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.enable")
        cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": 72,
                "maxWidth": item.viewport_width,
                "maxHeight": item.viewport_height,
                "everyNthFrame": 3,
            },
        )
        item.screencast_active = True

    def register_popup(self, parent_session_id: str, popup: Page) -> None:
        popup_id = self.safe_session_id(f"popup-{uuid.uuid4().hex}")
        item = PageState(session_id=popup_id, page=popup, loading=True)
        self.pages[popup_id] = item
        self.register_page_events(item)
        raw_url = str(popup.url or "")
        if raw_url.startswith(("http://", "https://")):
            try:
                self.validate_public_target(raw_url)
            except Exception:
                try:
                    popup.close()
                except Exception:
                    pass
                self.pages.pop(popup_id, None)
                return
        self.start_screencast(item)
        try:
            title = popup.title() or "Popup"
        except Exception:
            title = "Popup"
        parent = self.pages.get(parent_session_id)
        if parent:
            parent.popups.append(PopupInfo(popup_id, raw_url, title))

    def ensure_page(self, session_id: str, width: Any = None, height: Any = None) -> PageState:
        if not self.context:
            raise RuntimeError("Chrome BrowserContext가 준비되지 않았습니다.")
        key = self.safe_session_id(session_id)
        vp = self.viewport(width, height)
        item = self.pages.get(key)
        if item and not item.page.is_closed():
            if item.viewport_width != vp["width"] or item.viewport_height != vp["height"]:
                item.page.set_viewport_size(vp)
                item.viewport_width = vp["width"]
                item.viewport_height = vp["height"]
                self.start_screencast(item)
            elif not item.screencast_active:
                self.start_screencast(item)
            return item
        page = self.context.new_page()
        page.set_viewport_size(vp)
        item = PageState(key, page, viewport_width=vp["width"], viewport_height=vp["height"])
        self.pages[key] = item
        self.register_page_events(item)
        self.start_screencast(item)
        return item

    def existing_page(self, session_id: str) -> PageState:
        key = self.safe_session_id(session_id)
        item = self.pages.get(key)
        if not item or item.page.is_closed():
            raise RuntimeError("해당 외부 브라우저 탭 세션이 없습니다. 다시 연결하세요.")
        return item

    def state(self, session_id: str, consume_popups: bool = True) -> dict[str, Any]:
        item = self.existing_page(session_id)
        try:
            item.page.wait_for_timeout(1)
        except Exception:
            pass
        try:
            title = item.page.title() or "Browser"
        except Exception:
            title = "Browser"
        popup_payload: list[dict[str, str]] = []
        for popup in item.popups:
            p = self.pages.get(popup.session_id)
            try:
                url = str(p.page.url if p and not p.page.is_closed() else popup.url)
            except Exception:
                url = popup.url
            try:
                ptitle = str((p.page.title() if p and not p.page.is_closed() else popup.title) or "Popup")
            except Exception:
                ptitle = popup.title or "Popup"
            popup_payload.append({"session_id": popup.session_id, "url": url, "title": ptitle})
        if consume_popups:
            item.popups.clear()
        return {
            "ok": True,
            "session_id": item.session_id,
            "url": str(item.page.url or ""),
            "title": title,
            "loading": bool(item.loading),
            "viewport_width": item.viewport_width,
            "viewport_height": item.viewport_height,
            "popups": popup_payload,
            "transport": "cdp-screencast-helper",
            "frame_revision": item.frame_revision,
            "remaining_sessions": len(self.pages),
        }

    def navigate(self, req: dict[str, Any]) -> dict[str, Any]:
        target = self.validate_public_target(str(req.get("url") or ""))
        item = self.ensure_page(str(req.get("session_id") or ""), req.get("width"), req.get("height"))
        item.loading = True
        try:
            item.page.goto(target, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            if not item.page.url or item.page.url == "about:blank":
                item.loading = False
                raise
        item.loading = False
        try:
            item.page.wait_for_timeout(200)
        except Exception:
            pass
        return self.state(item.session_id, consume_popups=False)

    def action(self, req: dict[str, Any]) -> dict[str, Any]:
        item = self.existing_page(str(req.get("session_id") or ""))
        page = item.page
        kind = str(req.get("action") or "").strip().lower()
        payload = req.get("payload") or {}
        if kind == "resize":
            vp = self.viewport(payload.get("viewport_width"), payload.get("viewport_height"))
            page.set_viewport_size(vp)
            item.viewport_width = vp["width"]
            item.viewport_height = vp["height"]
            if item.screencast_active:
                self.start_screencast(item)
        elif kind == "suspend":
            if item.cdp and item.screencast_active:
                try:
                    item.cdp.send("Page.stopScreencast")
                except Exception:
                    pass
            item.screencast_active = False
        elif kind == "resume":
            if not item.screencast_active:
                self.start_screencast(item)
        elif kind == "click":
            page.mouse.click(
                float(payload.get("x", 0)),
                float(payload.get("y", 0)),
                button=str(payload.get("button") or "left"),
                click_count=int(payload.get("click_count") or 1),
            )
        elif kind == "scroll":
            page.mouse.wheel(float(payload.get("delta_x", 0)), float(payload.get("delta_y", 0)))
        elif kind == "key":
            key = str(payload.get("key") or "").strip()
            if key:
                page.keyboard.press(key)
        elif kind == "text":
            text = str(payload.get("text") or "")
            if text:
                page.keyboard.insert_text(text)
        elif kind == "back":
            page.go_back(wait_until="domcontentloaded", timeout=15000)
        elif kind == "forward":
            page.go_forward(wait_until="domcontentloaded", timeout=15000)
        elif kind == "reload":
            page.reload(wait_until="domcontentloaded", timeout=20000)
        else:
            raise RuntimeError(f"지원하지 않는 브라우저 동작입니다: {kind}")
        return self.state(item.session_id, consume_popups=True)

    def next_frame(self, req: dict[str, Any]) -> dict[str, Any]:
        item = self.existing_page(str(req.get("session_id") or ""))
        after_revision = int(req.get("after_revision") or 0)
        deadline = time.time() + 0.08
        while time.time() < deadline and item.frame_revision <= after_revision:
            try:
                item.page.wait_for_timeout(12)
            except Exception:
                break
        return {
            "revision": item.frame_revision,
            "data": item.frame_data if item.frame_revision > after_revision else "",
            "url": str(item.page.url or ""),
            "loading": bool(item.loading),
        }

    def screenshot(self, req: dict[str, Any]) -> dict[str, Any]:
        item = self.existing_page(str(req.get("session_id") or ""))
        content = item.page.screenshot(type="jpeg", quality=82, full_page=False, animations="allow")
        return {"data": base64.b64encode(content).decode("ascii")}

    def close_page(self, req: dict[str, Any]) -> dict[str, Any]:
        key = self.safe_session_id(str(req.get("session_id") or ""))
        item = self.pages.pop(key, None)
        if item:
            try:
                if item.cdp and item.screencast_active:
                    item.cdp.send("Page.stopScreencast")
            except Exception:
                pass
            try:
                if not item.page.is_closed():
                    item.page.close()
            except Exception:
                pass
        return {"ok": True, "session_id": key, "remaining_sessions": len(self.pages)}

    def dispatch(self, req: dict[str, Any]) -> dict[str, Any]:
        op = str(req.get("op") or "")
        if op == "navigate":
            return self.navigate(req)
        if op == "state":
            return self.state(str(req.get("session_id") or ""), bool(req.get("consume_popups", True)))
        if op == "action":
            return self.action(req)
        if op == "next_frame":
            return self.next_frame(req)
        if op == "screenshot":
            return self.screenshot(req)
        if op == "close":
            return self.close_page(req)
        if op == "ping":
            return {"ok": True, "pages": len(self.pages)}
        if op == "shutdown":
            return {"ok": True, "shutdown": True}
        raise RuntimeError(f"Unknown worker operation: {op}")

    def shutdown(self) -> None:
        self.save_storage_state()
        for item in list(self.pages.values()):
            try:
                if item.cdp and item.screencast_active:
                    item.cdp.send("Page.stopScreencast")
            except Exception:
                pass
            try:
                if not item.page.is_closed():
                    item.page.close()
            except Exception:
                pass
        self.pages.clear()
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        self.browser = None
        self.context = None
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass
        self.pw = None


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: chromium_playwright_worker.py <cdp_endpoint> <storage_state_path>", file=sys.stderr)
        return 2
    endpoint = sys.argv[1]
    storage_state_path = sys.argv[2]
    worker = Worker(endpoint, storage_state_path)
    try:
        worker.connect()
        _emit({
            "id": 0,
            "ok": True,
            "ready": True,
            "python": sys.executable,
            "platform": sys.platform,
            "endpoint": endpoint,
            "event_loop_policy": type(asyncio.get_event_loop_policy()).__name__,
        })
    except BaseException as exc:
        _emit(_error_payload(0, exc))
        return 3

    try:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            request_id = 0
            try:
                req = json.loads(raw)
                request_id = int(req.get("id") or 0)
                payload = worker.dispatch(req)
                _emit({"id": request_id, "ok": True, "result": payload})
                if req.get("op") == "shutdown":
                    break
            except BaseException as exc:
                _emit(_error_payload(request_id, exc))
    finally:
        worker.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
