# THEANOVA AgentStudio v5.494 - Active Ollama Model Resolver

- `theanova-learn:latest`가 현재 PC에 적용되어 있으면 일반 Ollama 요청의 단일 실행 모델로 사용합니다.
- 현재 curriculum 모델은 Ollama Modelfile의 `FROM qwen3.5:4b` + 누적 System Prompt 구조이므로 Fine-tuning 전에도 `theanova-learn:latest` 하나를 호출하면 Base 모델 능력과 THEANOVA 규칙이 함께 적용됩니다.
- 학습 파생 모델이 없으면 `qwen3.5:4b`, 이후에만 다른 설치 Chat 모델로 fallback합니다.
- `qwen2.5:*` 레거시 기본/fallback 모델 사용을 제거했습니다.
- 상단 Runtime 상태, LLM Catalog 요청 JSON, LangChain `ChatOllama`, Learning Teacher가 동일한 Active Model Resolver를 사용합니다.
