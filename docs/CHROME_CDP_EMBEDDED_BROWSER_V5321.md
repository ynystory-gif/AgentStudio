# v5.321 Chrome CDP Embedded Browser

외부 사이트는 AgentStudio Backend가 Windows에 설치된 Google Chrome 또는 Microsoft Edge를 전용 프로필로 직접 실행하고 Chrome DevTools Protocol(CDP)에 연결해 표시한다.

- 내부 주소(localhost, 127.0.0.1, RFC1918)는 기존 iframe 직접 표시를 유지한다.
- 외부 주소는 `Page.startScreencast` JPEG frame을 AgentStudio WebSocket으로 실시간 전달한다.
- 마우스/휠/키보드/한글 입력은 CDP에 연결된 실제 Chrome page로 전달한다.
- `window.open()` / `target=_blank` popup은 같은 BrowserContext에서 새 AgentStudio Browser 서브탭으로 연결한다.
- Profile: `%LOCALAPPDATA%\\THEANOVA\\AgentStudio\\BrowserProfile`
- 저장된 Cookie/Login session은 AgentStudio 재시작 후에도 profile에 유지된다.
- Playwright는 browser binary를 launch하지 않고 CDP client로만 사용한다. 시스템 Chrome/Edge를 자동 탐지한다.
- 외부 페이지가 localhost/private/link-local/metadata로 요청을 우회하지 못하도록 HTTP/HTTPS/WebSocket target을 검증한다.
