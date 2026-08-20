# v5.276 Notebook Working Directory Fix

## 문제
AgentStudio Notebook 셀 실행 시 Python worker의 현재 작업 디렉터리(CWD)가 항상 프로젝트 root로 설정되어, `.ipynb`와 같은 폴더에 있는 `serviceAccountKey.json`, CSV, JSON 등을 상대 경로로 찾지 못할 수 있었습니다.

## 수정
- Notebook(`.ipynb`) 셀 실행 시 CWD를 현재 Notebook 파일의 부모 폴더로 설정합니다.
- 프로젝트 root는 Python interpreter 선택, persistent session key, `sys.path` 기준으로 계속 유지합니다.
- 각 셀 실행마다 Notebook 위치로 CWD를 재설정하므로 여러 폴더의 Notebook을 번갈아 실행해도 상대 경로가 올바르게 동작합니다.
- 일반 `.py` 실행은 기존 프로젝트 root CWD 동작을 유지합니다.
- 별도 패치 실행 CMD를 추가하지 않습니다. 기존 `SYSTEM_ADMIN.cmd`만 사용합니다.

## 예
Notebook:
`...\실습3\4.NoSQL_연습문제.ipynb`

같은 폴더의 파일:
`...\실습3\serviceAccountKey.json`

Notebook 셀에서 아래 코드가 정상적으로 `True`가 됩니다.

```python
from pathlib import Path
print(Path("serviceAccountKey.json").exists())
```
