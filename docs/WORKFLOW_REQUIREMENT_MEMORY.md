# v5.123 Workflow Requirement Memory

문제:
기존 Workflow Designer는 현재 입력 문장 중심으로 설계해,
인터뷰에서 이미 확정된 세부 요구사항이 누락될 수 있었습니다.

개선:
- POST /api/workflow/preview가 interview_messages 전체를 받습니다.
- confirmed_requirements를 별도 구조화하여 전달합니다.
- Agent Factory Workflow Designer는 전체 인터뷰 + 확정 요구를 함께 사용합니다.
- 보안 검증, MCP Client/Transport/Server/Tool, Provider 선택, UI/저장 분기를 생략하지 않도록 Prompt 강화
- target_agent_workflow step에 name/label/description/type 구조 도입
- branches/retry_policy/failure_policy를 구조화
- Workflow 단계가 6개 미만이면 품질 경고
- UI에 단계 수 / 분기 / 재시도 / 실패 처리 반영 여부 표시

첫 검증 Agent에서 기대하는 예:
파일 선택
→ 프로젝트 Root 검증
→ 확장자 검증
→ MCP Client
→ stdio Transport
→ MCP Server
→ File Tool
→ 파일 읽기
→ LLM Provider 선택
→ 요약
→ React UI 표시
→ TXT/MD 저장 분기
→ 완료
