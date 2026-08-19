# v5.132 Requirement Completion Message

요구사항 인터뷰가 충분히 완료되면 마지막 문장을 다음으로 고정합니다.

> 요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다.

또한 완료 후 다음과 같은 불필요한 문장을 제거합니다.

- 추가 요구사항이 필요하시면 말씀해 주세요.
- 추가적인 질문이나 요구사항이 생기면 말씀해 주세요.
- 더 필요한 내용이 있으면 알려주세요.

구현은 두 단계입니다.

1. Requirements Agent System Prompt에서 완료 응답 규칙을 명시
2. LLM 응답 후 completion marker를 확인하여 최종 문장을 deterministic하게 보정

따라서 모델의 표현 변화가 있어도 완료 상태에서는 Workflow 설계 단계 안내가 유지됩니다.
