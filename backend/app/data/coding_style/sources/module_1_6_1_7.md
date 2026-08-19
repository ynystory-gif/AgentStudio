# 모듈 1-6 · 랭체인 개요 & 첫 호출 라이브코딩

이 자료는 사용자가 AgentStudio 코딩 스타일 학습의 첫 번째 입력으로 제공한 원본 자료입니다.
핵심 원문 내용은 다음을 포함합니다.

## 모듈 1-6
- LangChain 구성요소: Model, Prompt, Parser, Chain, Tool
- ChatOpenAI(model="gpt-4o-mini", temperature=0)
- llm.invoke()
- AIMessage.content
- AIMessage.usage_metadata
- SystemMessage: AI의 직책과 행동 지침
- HumanMessage: 실제 업무 지시
- LangSmith tracing
- ChatAnthropic 등 Provider 비교
- 필요한 LangChain 구성요소만 사용

## 모듈 1-7
- Colab → 로컬 변환
  - google.colab.userdata → dotenv/load_dotenv
  - userdata.get(...) → os.getenv(...)
  - !pip install → 로컬 터미널 설치
  - display(...) → print(...)
  - files.upload() → 로컬 파일 경로
- .env + .gitignore
- 로컬 가상환경 사용
- my_service_v1.py → v2 → v3 → v4 교육용 버전 관리 예시
- 실제 AgentStudio 프로젝트에서는 역할별 파일 구조 + Git 이력 관리로 해석
- 모델명과 비용 숫자는 교육 예시이므로 코딩 규칙에 고정하지 않음

## 분류 원칙
이 원본 자료 전체가 코딩 규칙은 아닙니다.
Coding Style Analyzer는 다음으로 분류합니다.
1. required
2. recommended
3. conditional
4. template_candidate
5. reference_only
