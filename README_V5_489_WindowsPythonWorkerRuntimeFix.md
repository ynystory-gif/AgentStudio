# THEANOVA AgentStudio v5.489 - WindowsPythonWorkerRuntimeFix

- Python Worker를 `python -c` 인라인 문자열에서 별도 `python_worker_runtime.py` 실행으로 분리
- Windows `WinError 206` 명령행 길이 문제 제거
- Notebook `%pip` / `!pip` / `!python -m pip`를 Backend 패키지 실행 경로로 분리
- 패키지 설치 전 Worker 종료 및 설치 후 새 Worker 사용
- 같은 셀의 일반 Python 코드는 설치 성공 후 새 Worker에서 이어 실행
- Windows Runtime 회귀검사 추가
