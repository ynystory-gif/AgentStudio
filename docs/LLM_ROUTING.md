# AgentStudio LLM 자동 라우팅

## Ollama 담당
- 프로젝트 탐색
- MCP Tool 분류
- 테스트/실행 로그 1차 분석
- 간단한 개발 질문
- Memory 정리

## GPT-5 mini 담당
- 요구사항 분석 / 대화형 인터뷰
- 일반 코드 생성
- Patch 생성
- 일반 디버깅 / 수정 전략

## Debug 흐름
테스트 실패
→ Ollama: 긴 로그에서 핵심 오류 1차 추출
→ GPT-5 mini: 원인 판단 및 수정 전략
→ GPT-5 mini: 최소 Patch 생성
→ 재테스트

## Project Analyzer 흐름
로컬 Python: 파일/심볼/키워드 스캔
→ Ollama: 관련 파일 후보 우선순위 보조
→ GPT-5 mini: 실제 코드 Patch

사용자가 모델을 매번 직접 선택하지 않아도 중앙 `model_router.py`가 작업 종류에 따라 자동 선택합니다.
