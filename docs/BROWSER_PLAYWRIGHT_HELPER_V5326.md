# v5.326 Playwright Helper Isolation / Diagnostics Persistence

Windows Backend는 psycopg async 호환을 위해 SelectorEventLoop를 사용합니다. Playwright Python driver는 Node subprocess를 기동하므로 Windows Proactor subprocess 지원이 필요합니다. v5.326은 Playwright를 별도 Python Helper 프로세스에 격리하여 두 요구사항을 동시에 만족시킵니다.

진단 로그 기본 경로:
`%LOCALAPPDATA%\THEANOVA\AgentStudio\logs\browser_cdp_diagnostics.log`

Helper 로그:
`%LOCALAPPDATA%\THEANOVA\AgentStudio\logs\browser_cdp_worker_<backend-pid>_<timestamp>.log`

Runtime startup log는 실패/종료 전에 같은 logs 폴더로 archive됩니다.
