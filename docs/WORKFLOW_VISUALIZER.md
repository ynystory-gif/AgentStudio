# Workflow Visualizer

v5.119부터 Workspace에 `워크플로우` 탭을 제공합니다.

## 1. AgentStudio 전체 Workflow

Backend `GET /api/workflow/definition`을 읽어 Agent Factory 제작 공정 전체를 표시합니다.

- requirement_analysis
- analyze_project
- capability_design
- tool_mcp_decision
- agent_architecture
- target_workflow_design
- project_file_plan
- checkpoint
- approval
- code_generation
- environment_configuration
- test
- debug/repair
- package_completion
- review

Test 실패 시 Debug → Code Generation → Environment → Test 재검증 루프도 별도로 표시합니다.

## 2. 개발 대상 Agent Workflow

`POST /api/workflow/preview`에 자연어 개발 요청을 보내면
Agent Factory 설계 엔진이 `target_agent_workflow`를 반환합니다.

UI에는:
- steps
- branches
- retry_policy
- failure_policy

를 별도로 표시합니다.

따라서 AgentStudio 제작 Workflow와 생성 대상 Agent 업무 Workflow를 화면에서도 명확하게 구분합니다.
