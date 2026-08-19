# 모듈 4-1 ~ 4-4 · Function Calling / Tool 연결

AgentStudio Coding Style 원본 자료의 핵심을 보존한 요약 파일입니다.

핵심 원칙:
- AI는 Tool 호출을 결정하고 실제 실행은 애플리케이션 코드가 수행한다.
- @tool 타입 힌트와 docstring에서 Tool Schema가 만들어진다.
- docstring은 사용 시점, Args, Returns, 제약, 필요 시 예시를 포함한다.
- bind_tools로 Tool을 명시적으로 등록한다.
- tool_calls를 만든 AIMessage를 messages에 보존한다.
- ToolMessage에는 tool_call_id를 연결한다.
- tool_calls가 없는 직접 답변 경로를 처리한다.
- 다중 Tool에서 description 품질이 Tool 선택 정확도에 영향을 준다.
- Mock Tool에서 실제 API/DB Tool로 단계적으로 전환할 수 있게 설계한다.
- 외부 API 결과는 LLM에 필요한 형태로 정제한다.
- API Key는 .env에서 관리한다.
- 교육용 eval 예시는 프로덕션 코드에서 사용하지 않는다.
- Tool 하나의 실패가 전체 Agent를 중단시키지 않도록 예외를 격리한다.
- MCP Tool도 동일한 Tool 명세 품질을 적용한다.
