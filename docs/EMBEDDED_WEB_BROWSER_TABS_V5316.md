# v5.316 Embedded Web Browser Tabs

## 목적
AgentStudio를 벗어나지 않고 Streamlit, Vite/React, FastAPI Swagger 등 로컬 개발 웹 서비스를 확인할 수 있도록 코드 편집 탭 영역에 내장 Browser를 제공합니다.

## 기본 고정 Browser
- `Chrome` 이름의 Browser 탭이 항상 코드 편집 탭 레일에 존재합니다.
- 고정 탭은 닫히지 않습니다.
- 주소 입력, 뒤로, 앞으로, 새로고침, 새 탭, 외부 Chrome 열기를 지원합니다.

## 웹 URL 감지
Terminal 출력에서 다음 범위의 HTTP/HTTPS URL만 감지합니다.
- localhost
- 127.0.0.1 / 0.0.0.0
- RFC1918 사설 IP(10/8, 172.16/12, 192.168/16)

감지 후 자동 탐색하지 않습니다. 사용자에게 다음 선택을 제공합니다.
1. 고정 Chrome에서 열기
2. 새 Browser 탭
3. 무시

0.0.0.0 URL은 브라우저 접근용으로 127.0.0.1로 정규화합니다.

## 보안/호환성
내장 Browser는 브라우저 iframe을 사용합니다. X-Frame-Options 또는 CSP frame-ancestors로 iframe을 차단하는 사이트는 내장 표시가 불가능할 수 있으며, 이 경우 `↗ Chrome` 버튼으로 외부 브라우저에서 엽니다.
