# v5.315 OpenAI Usage Toggle / Local-Only Mode

## 목적
시스템 관리의 OpenAI 설정에 `OpenAI 사용` 스위치를 추가합니다.

## 동작
- 기본값은 `true`로 기존 동작을 유지합니다.
- `false`로 저장하면 코딩, 디버깅, 요구사항 분석, 일반 질의 및 Embedding을 모두 Ollama로 강제합니다.
- 저장되어 있던 OpenAI API Key는 삭제하지 않지만 OpenAI API 호출에는 사용하지 않습니다.
- 기존 `LOCAL_LLM_PROVIDER`, `CODING_LLM_PROVIDER`, `REQUIREMENTS_LLM_PROVIDER`, `MEMORY_EMBEDDING_PROVIDER` 값도 Ollama로 동기화합니다.
- API 요청이 명시적으로 provider=openai를 보내더라도 OpenAI가 비활성화되어 있으면 Ollama로 처리합니다.
- OpenAI 연결 테스트는 비활성화 상태에서 외부 네트워크 요청을 하지 않고 skipped 성공으로 반환합니다.
- 다시 켠 뒤에는 상단 AI 모드에서 AUTO/OpenAI/Ollama를 선택할 수 있습니다.

## 보안/비용 기준
OpenAI 비사용 상태에서는 AgentStudio Runtime 코드에서 OpenAI Chat/Embedding API를 호출하지 않습니다. Ollama가 실행되지 않았거나 모델이 없으면 로컬 오류를 반환하며 OpenAI로 자동 fallback하지 않습니다.
