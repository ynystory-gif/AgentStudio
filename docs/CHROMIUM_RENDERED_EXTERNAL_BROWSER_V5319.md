# v5.319 Chromium Rendered External Browser + Popup Tabs

## 목적
Naver처럼 JavaScript와 동적 API 의존도가 높은 외부 사이트가 HTML rewrite proxy에서 일부 화면만 표시되는 문제를 해결합니다.

## 동작
- 내부 개발 주소: 기존 직접 iframe
- 외부 공인 인터넷 주소: Backend Chrome/Chromium 실제 렌더링
- UI는 활성 페이지의 JPEG viewport를 주기적으로 갱신하고 click / wheel / keyboard를 Chromium에 전달합니다.
- 사이트 popup은 동일 BrowserContext의 새 Page로 유지하며 AgentStudio Browser 서브탭으로 자동 생성합니다.

## 설치
`playwright` Python 패키지가 필요합니다. Windows에서는 설치된 Google Chrome을 우선 사용하므로 별도 Chromium 다운로드가 필수는 아닙니다.
필요하면 `AGENTSTUDIO_BROWSER_EXECUTABLE` 환경변수로 chrome.exe 경로를 지정할 수 있습니다.

## 보안
외부 Chromium은 public HTTP/HTTPS URL 전용입니다. 내부/사설/link-local 주소로의 네트워크 요청은 차단합니다. 내부 개발 서버는 Backend Chromium을 거치지 않고 기존 Frontend 직접 iframe으로 표시합니다.
