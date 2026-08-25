from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import re
import socket
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse

import httpx


MAX_PROXY_BYTES = 25 * 1024 * 1024
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_PROXY_SESSIONS = 32
REQUEST_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

_STRIP_RESPONSE_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "content-security-policy",
    "content-security-policy-report-only",
    "cross-origin-embedder-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "keep-alive",
    "permissions-policy",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "x-frame-options",
}

_FORWARD_REQUEST_HEADERS = {
    "accept",
    "accept-language",
    "content-type",
    "if-modified-since",
    "if-none-match",
    "range",
    "user-agent",
    "x-requested-with",
}

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

_URL_ATTRS = {
    "src", "poster", "data", "background",
}


class BrowserProxyError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ProxyFetchResult:
    status_code: int
    content: bytes
    content_type: str
    headers: dict[str, str]
    final_url: str
    redirect_url: str = ""


@dataclass
class _ProxySession:
    cookies: httpx.Cookies
    last_used: float


_proxy_sessions: dict[str, _ProxySession] = {}
_proxy_session_lock = asyncio.Lock()


def _is_literal_internal_host(hostname: str) -> bool:
    host = (hostname or "").strip().lower().strip("[]")
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global


def is_direct_internal_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    return _is_literal_internal_host(parsed.hostname or "")


def _validate_url_shape(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise BrowserProxyError("프록시 대상 URL이 없습니다.")
    try:
        parsed = urlparse(raw)
    except Exception as exc:
        raise BrowserProxyError(f"올바른 URL이 아닙니다: {exc}") from exc
    if parsed.scheme not in {"http", "https"}:
        raise BrowserProxyError("Backend Proxy는 http/https URL만 허용합니다.")
    if not parsed.hostname:
        raise BrowserProxyError("URL에 host가 없습니다.")
    if parsed.username or parsed.password:
        raise BrowserProxyError("사용자명/비밀번호가 포함된 URL은 프록시할 수 없습니다.")
    return raw


async def validate_public_proxy_target(value: str) -> str:
    raw = _validate_url_shape(value)
    parsed = urlparse(raw)
    hostname = str(parsed.hostname or "").strip().lower().strip("[]")

    # Local/private destinations must be opened directly by the browser, never through Backend SSRF.
    if _is_literal_internal_host(hostname):
        raise BrowserProxyError(
            "내부 IP/localhost는 Backend Proxy 대상이 아닙니다. 기존 직접 표시 방식을 사용하세요.",
            status_code=403,
        )

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise BrowserProxyError("잘못된 포트입니다.") from exc

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not literal_ip.is_global:
            raise BrowserProxyError("공인 IP가 아닌 주소는 Backend Proxy에서 차단됩니다.", status_code=403)
        return raw

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM),
        )
    except socket.gaierror as exc:
        raise BrowserProxyError(f"도메인 주소를 확인할 수 없습니다: {hostname}", status_code=502) from exc

    resolved: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            resolved.add(str(sockaddr[0]))
    if not resolved:
        raise BrowserProxyError(f"도메인의 IP 주소를 확인하지 못했습니다: {hostname}", status_code=502)

    blocked = []
    for address in resolved:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            blocked.append(address)
            continue
        if not ip.is_global:
            blocked.append(address)
    if blocked:
        raise BrowserProxyError(
            f"공인 인터넷 주소가 아닌 IP로 해석되는 도메인은 Proxy에서 차단됩니다: {hostname}",
            status_code=403,
        )
    return raw


def _safe_session_id(session_id: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(session_id or "default"))[:120]
    return raw or "default"


async def _session_cookies(session_id: str) -> httpx.Cookies:
    key = _safe_session_id(session_id)
    async with _proxy_session_lock:
        entry = _proxy_sessions.get(key)
        if entry is None:
            entry = _ProxySession(cookies=httpx.Cookies(), last_used=time.time())
            _proxy_sessions[key] = entry
        entry.last_used = time.time()
        if len(_proxy_sessions) > MAX_PROXY_SESSIONS:
            oldest = sorted(_proxy_sessions.items(), key=lambda item: item[1].last_used)
            for old_key, _ in oldest[: len(_proxy_sessions) - MAX_PROXY_SESSIONS]:
                if old_key != key:
                    _proxy_sessions.pop(old_key, None)
        return httpx.Cookies(entry.cookies)


async def _store_session_cookies(session_id: str, cookies: httpx.Cookies) -> None:
    key = _safe_session_id(session_id)
    async with _proxy_session_lock:
        _proxy_sessions[key] = _ProxySession(cookies=httpx.Cookies(cookies), last_used=time.time())


def build_proxy_path(target_url: str, session_id: str) -> str:
    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return target_url
    if is_direct_internal_url(target_url):
        return target_url
    session = quote(_safe_session_id(session_id), safe="")
    netloc = quote(parsed.netloc, safe="")
    path = parsed.path or "/"
    proxy = f"/api/web-proxy/{session}/{parsed.scheme}/{netloc}{path}"
    if parsed.query:
        proxy += f"?{parsed.query}"
    if parsed.fragment:
        proxy += f"#{parsed.fragment}"
    return proxy


def reconstruct_proxy_target(scheme: str, netloc: str, target_path: str, query: str = "") -> str:
    clean_scheme = str(scheme or "").lower()
    if clean_scheme not in {"http", "https"}:
        raise BrowserProxyError("지원하지 않는 Proxy scheme입니다.")
    decoded_netloc = unquote(str(netloc or ""))
    path = "/" + str(target_path or "").lstrip("/")
    return urlunparse((clean_scheme, decoded_netloc, path, "", str(query or ""), ""))


def _should_leave_url_untouched(raw: str) -> bool:
    value = str(raw or "").strip()
    lowered = value.lower()
    return (
        not value
        or value.startswith("#")
        or lowered.startswith("data:")
        or lowered.startswith("blob:")
        or lowered.startswith("javascript:")
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
        or lowered.startswith("about:")
    )


def _proxied_reference(raw: str, base_url: str, session_id: str) -> tuple[str, str]:
    value = str(raw or "").strip()
    if _should_leave_url_untouched(value):
        return raw, ""
    absolute = urljoin(base_url, value)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return raw, ""
    if is_direct_internal_url(absolute):
        return absolute, absolute

    # Keep ordinary relative references relative. The proxy route mirrors the original path,
    # so relative JS chunks / images continue to resolve through the proxy automatically.
    if not value.startswith("/") and not value.startswith("//") and not re.match(r"^https?://", value, re.I):
        return raw, absolute
    return build_proxy_path(absolute, session_id), absolute


def _rewrite_srcset(value: str, base_url: str, session_id: str) -> str:
    output: list[str] = []
    for part in str(value or "").split(","):
        item = part.strip()
        if not item:
            continue
        pieces = item.split()
        src = pieces[0]
        rewritten, _ = _proxied_reference(src, base_url, session_id)
        output.append(" ".join([rewritten, *pieces[1:]]))
    return ", ".join(output)


_CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
_CSS_IMPORT_RE = re.compile(r"(@import\s+)(['\"])(.*?)\2", re.I)


def rewrite_css(css_text: str, base_url: str, session_id: str) -> str:
    def repl_url(match: re.Match[str]) -> str:
        quote_char = match.group(1) or ""
        raw = match.group(2)
        rewritten, _ = _proxied_reference(raw, base_url, session_id)
        return f"url({quote_char}{rewritten}{quote_char})"

    def repl_import(match: re.Match[str]) -> str:
        rewritten, _ = _proxied_reference(match.group(3), base_url, session_id)
        return f"{match.group(1)}{match.group(2)}{rewritten}{match.group(2)}"

    return _CSS_IMPORT_RE.sub(repl_import, _CSS_URL_RE.sub(repl_url, css_text))


def _js_literal(value: str) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


def _bootstrap_script(base_url: str, session_id: str) -> str:
    base_js = _js_literal(base_url)
    session_js = _js_literal(_safe_session_id(session_id))
    return f"""<script data-agentstudio-proxy-bootstrap=\"1\">(function(){{
const ORIGINAL_URL={base_js};
const SESSION={session_js};
const API_PREFIX='/api/web-proxy/'+encodeURIComponent(SESSION)+'/';
function isInternalHost(host){{
  host=String(host||'').toLowerCase().replace(/^\\[|\\]$/g,'');
  if(host==='localhost'||host==='127.0.0.1'||host==='0.0.0.0'||host==='::1') return true;
  if(/^10\\./.test(host)||/^192\\.168\\./.test(host)) return true;
  const m=host.match(/^172\\.(\\d+)\\./); return !!(m&&Number(m[1])>=16&&Number(m[1])<=31);
}}
function absoluteUrl(value){{ try{{ return new URL(String(value||''),ORIGINAL_URL).toString(); }}catch(_e){{ return String(value||''); }} }}
function proxyUrl(value){{
  const absolute=absoluteUrl(value); let u; try{{u=new URL(absolute)}}catch(_e){{return absolute}}
  if(!/^https?:$/.test(u.protocol)||isInternalHost(u.hostname)) return absolute;
  return API_PREFIX+u.protocol.slice(0,-1)+'/'+encodeURIComponent(u.host)+(u.pathname||'/')+u.search+u.hash;
}}
function notify(type,payload){{ try{{ window.parent.postMessage(Object.assign({{source:'agentstudio-web-proxy',type:type}},payload||{{}}),'*'); }}catch(_e){{}} }}
try{{
  const originalFetch=window.fetch.bind(window);
  window.fetch=function(input,init){{
    if(input instanceof Request) return originalFetch(new Request(proxyUrl(input.url),input),init);
    return originalFetch(proxyUrl(input),init);
  }};
}}catch(_e){{}}
try{{
  const originalOpen=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(method,url){{
    const args=Array.prototype.slice.call(arguments); args[1]=proxyUrl(url); return originalOpen.apply(this,args);
  }};
}}catch(_e){{}}
document.addEventListener('click',function(event){{
  const anchor=event.target&&event.target.closest?event.target.closest('a[href]'):null;
  if(!anchor) return;
  const rawHref=anchor.getAttribute('href')||'';
  if(!rawHref||rawHref.charAt(0)==='#'||/^(javascript:|mailto:|tel:|data:|blob:)/i.test(rawHref)) return;
  const target=anchor.getAttribute('data-agentstudio-target')||absoluteUrl(rawHref);
  if(!/^https?:/i.test(target)) return;
  event.preventDefault();
  notify(anchor.target==='_blank'?'new-tab':'navigate',{{url:target}});
}},true);
document.addEventListener('submit',function(event){{
  const form=event.target; if(!form||String(form.method||'get').toLowerCase()!=='get') return;
  const target=form.getAttribute('data-agentstudio-target')||absoluteUrl(form.getAttribute('action')||ORIGINAL_URL);
  try{{ const u=new URL(target); const data=new FormData(form); for(const pair of data.entries()) u.searchParams.append(pair[0],String(pair[1])); event.preventDefault(); notify('navigate',{{url:u.toString()}}); }}catch(_e){{}}
}},true);
window.addEventListener('DOMContentLoaded',function(){{ notify('loaded',{{url:ORIGINAL_URL,title:document.title||''}}); }});
}})();</script>"""


class _HTMLProxyRewriter(HTMLParser):
    def __init__(self, base_url: str, session_id: str):
        super().__init__(convert_charrefs=False)
        self.base_url = base_url
        self.session_id = session_id
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.injected = False
        self.skip_meta = False

    def _inject(self) -> None:
        if not self.injected:
            self.parts.append(_bootstrap_script(self.base_url, self.session_id))
            self.injected = True

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self.parts.append(f"<![{data}]>")

    def _render_tag(self, tag: str, attrs: Iterable[tuple[str, str | None]], closing: str = ">") -> str:
        rendered = ["<", tag]
        for name, value in attrs:
            rendered.extend([" ", name])
            if value is not None:
                rendered.extend(["=\"", html.escape(value, quote=True), "\""])
        rendered.append(closing)
        return "".join(rendered)

    def _rewrite_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        tag_lower = tag.lower()
        out: list[tuple[str, str | None]] = []
        added_target = False
        for name, value in attrs:
            lower = name.lower()
            raw = value or ""
            if lower == "integrity":
                continue
            if tag_lower == "base":
                continue
            if lower == "srcset" and value is not None:
                out.append((name, _rewrite_srcset(raw, self.base_url, self.session_id)))
                continue
            if lower == "style" and value is not None:
                out.append((name, rewrite_css(raw, self.base_url, self.session_id)))
                continue

            is_link = lower == "href" and tag_lower in {"a", "link", "area"}
            is_form = lower == "action" and tag_lower == "form"
            is_resource = lower in _URL_ATTRS
            if value is not None and (is_link or is_form or is_resource):
                rewritten, absolute = _proxied_reference(raw, self.base_url, self.session_id)
                out.append((name, rewritten))
                if absolute and (tag_lower == "a" and lower == "href" or is_form):
                    out.append(("data-agentstudio-target", absolute))
                    added_target = True
                continue
            if lower == "target" and raw.lower() in {"_top", "_parent"}:
                out.append((name, "_self"))
                continue
            out.append((name, value))
        if tag_lower == "form" and not added_target:
            action = next((value for name, value in attrs if name.lower() == "action"), "") or self.base_url
            absolute = urljoin(self.base_url, action)
            out.append(("data-agentstudio-target", absolute))
        return out

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "base":
            return
        if tag_lower == "meta":
            attr_map = {str(k).lower(): str(v or "") for k, v in attrs}
            http_equiv = attr_map.get("http-equiv", "").lower()
            if http_equiv in {"content-security-policy", "content-security-policy-report-only", "x-frame-options"}:
                return
            if http_equiv == "refresh" and "content" in attr_map:
                content = attr_map["content"]
                match = re.search(r"(?i)(url\s*=\s*)(.+)$", content)
                if match:
                    raw_target = match.group(2).strip(" '\"")
                    rewritten, _ = _proxied_reference(raw_target, self.base_url, self.session_id)
                    new_content = content[: match.start(2)] + rewritten
                    attrs = [(k, new_content if str(k).lower() == "content" else v) for k, v in attrs]

        rewritten = self._rewrite_attrs(tag, attrs)
        self.parts.append(self._render_tag(tag, rewritten))
        if tag_lower == "head":
            self._inject()
        if tag_lower not in _VOID_TAGS:
            self.stack.append(tag_lower)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "base":
            return
        rewritten = self._rewrite_attrs(tag, attrs)
        self.parts.append(self._render_tag(tag, rewritten, " />"))

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "base":
            return
        self.parts.append(f"</{tag}>")
        if self.stack:
            # Be tolerant of malformed HTML; remove the nearest matching open tag.
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index] == tag_lower:
                    del self.stack[index:]
                    break

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1] == "style":
            self.parts.append(rewrite_css(data, self.base_url, self.session_id))
        else:
            self.parts.append(data)

    def rewritten(self) -> str:
        self._inject()
        return "".join(self.parts)


def rewrite_html(html_text: str, base_url: str, session_id: str) -> str:
    parser = _HTMLProxyRewriter(base_url, session_id)
    try:
        parser.feed(html_text)
        parser.close()
        return parser.rewritten()
    except Exception:
        # A malformed page should still get the bootstrap and a useful base payload.
        return _bootstrap_script(base_url, session_id) + html_text


def _decode_text(response: httpx.Response) -> str:
    try:
        return response.text
    except Exception:
        return response.content.decode("utf-8", errors="replace")


def _filtered_response_headers(response: httpx.Response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in response.headers.items():
        lower = key.lower()
        if lower in _STRIP_RESPONSE_HEADERS or lower == "location" or lower == "content-type":
            continue
        headers[key] = value
    headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS"
    headers["Access-Control-Allow-Headers"] = "*"
    headers["Cache-Control"] = "no-store"
    return headers


async def fetch_external_page(
    target_url: str,
    session_id: str,
    method: str,
    request_headers: dict[str, str],
    body: bytes,
) -> ProxyFetchResult:
    target_url = await validate_public_proxy_target(target_url)
    method = str(method or "GET").upper()
    if method == "OPTIONS":
        return ProxyFetchResult(
            status_code=204,
            content=b"",
            content_type="text/plain; charset=utf-8",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "no-store",
            },
            final_url=target_url,
        )

    outgoing_headers: dict[str, str] = {}
    for key, value in request_headers.items():
        if key.lower() in _FORWARD_REQUEST_HEADERS:
            outgoing_headers[key] = value
    outgoing_headers.setdefault("Accept-Encoding", "gzip, deflate")
    outgoing_headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    )
    outgoing_headers["Referer"] = target_url
    parsed = urlparse(target_url)
    outgoing_headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"

    cookies = await _session_cookies(session_id)
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
            cookies=cookies,
            trust_env=False,
        ) as client:
            response = await client.request(
                method,
                target_url,
                headers=outgoing_headers,
                content=body if method not in {"GET", "HEAD"} else None,
            )
            await _store_session_cookies(session_id, client.cookies)
    except httpx.TimeoutException as exc:
        raise BrowserProxyError("외부 사이트 응답 시간이 초과되었습니다.", status_code=504) from exc
    except httpx.HTTPError as exc:
        raise BrowserProxyError(f"외부 사이트 연결 실패: {exc}", status_code=502) from exc

    location = response.headers.get("location", "")
    if response.status_code in {301, 302, 303, 307, 308} and location:
        redirect_url = urljoin(target_url, location)
        if is_direct_internal_url(redirect_url):
            redirect_target = redirect_url
        else:
            await validate_public_proxy_target(redirect_url)
            redirect_target = build_proxy_path(redirect_url, session_id)
        return ProxyFetchResult(
            status_code=response.status_code,
            content=b"",
            content_type="text/plain; charset=utf-8",
            headers=_filtered_response_headers(response),
            final_url=target_url,
            redirect_url=redirect_target,
        )

    content = response.content
    if len(content) > MAX_PROXY_BYTES:
        raise BrowserProxyError("외부 응답이 Proxy 허용 크기(25MB)를 초과했습니다.", status_code=413)

    content_type = response.headers.get("content-type", "application/octet-stream")
    media_type = content_type.split(";", 1)[0].strip().lower()
    final_url = str(response.url)

    if media_type in {"text/html", "application/xhtml+xml"}:
        if len(content) > MAX_HTML_BYTES:
            raise BrowserProxyError("HTML 문서가 Proxy 허용 크기(8MB)를 초과했습니다.", status_code=413)
        rewritten = rewrite_html(_decode_text(response), final_url, session_id)
        content = rewritten.encode("utf-8")
        content_type = "text/html; charset=utf-8"
    elif media_type == "text/css":
        rewritten_css = rewrite_css(_decode_text(response), final_url, session_id)
        content = rewritten_css.encode("utf-8")
        content_type = "text/css; charset=utf-8"

    return ProxyFetchResult(
        status_code=response.status_code,
        content=content,
        content_type=content_type,
        headers=_filtered_response_headers(response),
        final_url=final_url,
    )


def proxy_error_html(message: str, target_url: str) -> bytes:
    safe_message = html.escape(str(message or "외부 사이트를 불러오지 못했습니다."))
    safe_url = html.escape(str(target_url or ""))
    return f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>Proxy 연결 실패</title>
<style>body{{font-family:system-ui,sans-serif;background:#f3f4f6;color:#111827;padding:40px}}.box{{max-width:760px;margin:40px auto;background:#fff;border:1px solid #d1d5db;border-radius:14px;padding:28px;box-shadow:0 10px 30px rgba(0,0,0,.08)}}code{{word-break:break-all;color:#374151}}h2{{margin-top:0}}</style></head><body><div class=\"box\"><h2>외부 사이트 Proxy 연결 실패</h2><p>{safe_message}</p><code>{safe_url}</code><p>사이트가 자동화 접근을 차단하거나, 로그인/OAuth/WebSocket 같은 기능을 요구하면 Backend Proxy에서 일부 기능이 제한될 수 있습니다.</p></div></body></html>""".encode("utf-8")
