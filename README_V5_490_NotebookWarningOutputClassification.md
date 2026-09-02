# THEANOVA AgentStudio v5.490 - NotebookWarningOutputClassification

- Python Warning과 실제 Exception/Traceback을 Notebook UI에서 분리
- DeprecationWarning/FutureWarning/UserWarning/RuntimeWarning 계열은 노란 접이식 경고 카드로 표시
- 일반 stderr는 중립 표시, 실제 output_type=error만 빨간 오류 표시
- 셀 실행 성공 + Warning 상태를 오류로 오인하지 않도록 개선
- v5.489 Windows Python Worker Runtime 구조 및 WinError 206 방지 기능 유지
