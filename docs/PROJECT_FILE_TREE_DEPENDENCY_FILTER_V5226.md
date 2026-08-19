# v5.226 ProjectFileTreeDependencyFilterFix

프로젝트 파일 탐색기가 `.venv_old`, `venv*`, `node_modules`, `__pycache__` 같은 의존성/가상환경 디렉터리의 수천 개 파일을 먼저 스캔하여 기존 2,000개 제한을 소진하고 실제 프로젝트 파일이 트리에서 누락되던 문제를 수정합니다.

- `os.walk()` 기반으로 전환해 무시 디렉터리를 탐색 전에 prune
- `.venv`, `.venv_old`, `venv`, `venv312`, `env`, `virtualenv*`, `node_modules`, 캐시 디렉터리 기본 제외
- 루트 파일을 먼저 수집하여 깊은 의존성 폴더 때문에 프로젝트 파일이 잘리지 않도록 보장
- 파일 안전 한도를 20,000개, 폴더 10,000개로 확장
- 외부 파일 변경 snapshot도 동일한 필터를 사용
- Project Analyzer도 가상환경 변형 폴더를 Context에서 제외
