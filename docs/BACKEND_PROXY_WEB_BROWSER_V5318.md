# v5.318 Backend Proxy Web Browser

## 목적

AgentStudio의 `웹브라우저` Workspace에서 내부 개발 서버는 기존처럼 브라우저가 직접 열고, iframe을 차단하는 외부 사이트는 FastAPI Backend Proxy를 통해 표시합니다.

## 라우팅 정책

- Direct iframe: `localhost`, `127.0.0.1`, `0.0.0.0`, RFC1918 private IPv4
- Backend Proxy: 그 외 public HTTP/HTTPS URL
- Backend Proxy 금지: loopback/private/link-local/reserved/metadata 등 public Internet이 아닌 IP로 DNS 해석되는 URL

## Proxy 처리

1. Frontend가 외부 URL을 path-preserving proxy URL로 변환합니다.
2. Backend가 DNS/IP를 검증한 뒤 외부 응답을 가져옵니다.
3. HTML은 frame 차단 header/meta를 제거하고 링크·폼·root-relative resource를 proxy 경로로 보정합니다.
4. CSS의 `url()` / `@import`도 proxy 경로를 유지하도록 보정합니다.
5. page-side `fetch`/XHR은 injected bootstrap이 proxy로 전달합니다.
6. 외부 페이지의 일반 링크/GET form은 parent Workspace에 navigation message를 보내 Browser history와 함께 이동합니다.
7. 세션별 cookie jar는 Backend memory에만 유지합니다.

## 보안

- `http` / `https`만 허용합니다.
- URL에 embedded username/password는 거부합니다.
- DNS 결과 중 하나라도 global public IP가 아니면 Proxy 요청을 차단합니다.
- redirect는 다음 URL을 다시 검증하고 proxy 경로로 이동시킵니다.
- 외부 iframe은 sandbox를 사용하며 `allow-same-origin`을 부여하지 않습니다.
- HTML 응답에는 `/api/web-proxy/` 경로만 script/style/image/connect/form 대상으로 허용하는 Proxy 전용 CSP를 추가합니다.
- 외부 `Set-Cookie`는 브라우저에 노출하지 않고 Backend session cookie jar로만 보관합니다.

## 제한

Backend Proxy는 실제 Chromium WebView가 아닙니다. 사이트가 OAuth, WebSocket, service worker, DRM, strict origin check, CAPTCHA/bot defense를 요구하면 일부 기능이 동작하지 않을 수 있습니다. 이 경우 `↗ Chrome`으로 외부 브라우저를 사용합니다.
