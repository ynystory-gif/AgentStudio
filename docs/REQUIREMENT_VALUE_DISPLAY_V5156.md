# v5.156 요구사항 실제 값 표시

## 목적
우측 요구사항 수집 현황에서 `완료`만 표시하지 않고,
AgentStudio가 실제로 이해하고 저장한 값을 함께 보여줍니다.

예:
- LLM : gpt-4o-mini, Ollama
- UI : React + Vite
- Backend : FastAPI + Uvicorn
- MCP / Transport : stdio · Streamable HTTP 확장
- DB : 미사용 · PostgreSQL 확장
- 파일 형식 : .txt, .md, .py
- 권한 / 파일 접근 : Project Root 내부 · .txt/.md/.py 제한
- 실행 환경 : Windows 10/11 · Python 3.12 · .venv · 온프레미스
- 처리 제한 : 10MB · 120초 · Chunking

## 데이터 일치
우측 표시용 값은 별도의 가짜 문자열이 아니라
`confirmed_requirements` 및 현재 인터뷰 대화에서 추출합니다.

`buildConfirmedRequirementsFromChat()`도 다음 구조를 유지합니다.
- llm
- file_access
- mcp
- database
- result
- processing
- runtime
- auth

같은 `confirmed_requirements`는 Workflow Preview와 개발 design_bundle에도 전달됩니다.
따라서 화면에 표시하는 값과 Workflow 설계 입력의 원천을 맞춥니다.
