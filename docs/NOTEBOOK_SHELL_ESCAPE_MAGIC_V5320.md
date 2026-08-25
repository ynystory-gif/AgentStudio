# v5.320 Notebook Shell Escape / Pip Magic Support

## 목적
AgentStudio Notebook Code 셀에서 일반 Jupyter처럼 `!pip`, `!uv`, `!python` 및 일반 `!command`를 실행할 수 있게 합니다.

## 실행 규칙
- `!pip`, `!pip3`: 현재 프로젝트 Notebook Python으로 `python -m pip` 실행
- `%pip`: 기존과 동일하게 현재 Notebook Python으로 실행
- `!python`, `!python3`, `!py`: 현재 Notebook Python으로 실행
- 기타 `!command`: Notebook 파일이 있는 폴더를 CWD로 플랫폼 shell에서 실행
- 명령 성공 후 import cache를 무효화해 같은 persistent Notebook 세션에서 새 패키지를 바로 import할 수 있게 합니다.

## 예시
```text
!pip install -U langchain langchain-openai langchain-community sqlalchemy langchain "psycopg[binary]"
!uv add openai numpy "psycopg[binary]" pgvector python-dotenv
%pip install pandas
!python --version
```
