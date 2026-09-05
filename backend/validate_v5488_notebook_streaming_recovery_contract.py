from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/"frontend/src/App.jsx").read_text(encoding="utf-8")
service=(ROOT/"backend/app/services/python_execution_service.py").read_text(encoding="utf-8")
main=(ROOT/"backend/app/main.py").read_text(encoding="utf-8")
routes=(ROOT/"backend/app/api/routes.py").read_text(encoding="utf-8")
checks={
    "frontend":"AGENTSTUDIO_FRONTEND_VERSION='5.488'" in app,
    "backend":'version="5.488"' in main,
    "health":'"version": "5.488"' in routes,
    "pip":"packageManagementMode" in app and "[패키지 설치 중]" in app,
    "recovery":"NotebookStreamingRecovered" in app and "'/python/reset'" in app,
    "safe":"중복 실행 방지를 위해 해당 셀은 자동 재실행하지 않았습니다" in app,
    "worker":service.count('"error_type": "PythonWorkerExited"')>=2,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(f"[{'OK' if v else 'FAIL'}] {k}")
if failed: raise SystemExit(', '.join(failed))
print('v5.488 contract: PASS')
