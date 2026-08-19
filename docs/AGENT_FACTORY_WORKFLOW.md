# THEANOVA AgentStudio — Full Agent Factory Workflow

## 두 Workflow를 구분합니다

### 1. AgentStudio 제작 Workflow

```text
START
 ↓
requirement_analysis
 ↓
analyze_project
 ↓
capability_design
 ↓
tool_mcp_decision
 ↓
agent_architecture
 ↓
target_workflow_design
 ↓
project_file_plan
 ↓
checkpoint
 ↓
approval
 ↓
code_generation
 ↓
environment_configuration
 ↓
test
 ├─ 실패 → debug → code_generation → test
 └─ 성공
      ↓
package_completion
 ↓
review
 ↓
END
```

### 2. 생성 대상 Agent Workflow

`target_agent_workflow` State에 별도의 설계 결과로 저장합니다.

예: YouTube Agent

```text
영상 선택
→ 검증
→ 인증
→ 채널 확인
→ 업로드
→ 결과 확인
→ 실패 처리
```

## 핵심 변화

기존 Workflow는 `프로젝트 분석 → Patch → Test` 중심이었습니다.

v5.118부터는 요구사항 분석, Capability, Tool/MCP 판단, Agent Architecture,
대상 Agent Workflow, File Plan, Environment, Package Completion까지
독립적인 State와 Node로 관리합니다.

## 신규 파일 생성

Patch 계획은 기존 파일 replacement뿐 아니라:

```json
{
  "path": "...",
  "create_file": true,
  "content": "..."
}
```

형태의 신규 파일 생성을 지원합니다.

## 완료 조건

코드가 생성되었다는 이유만으로 완료되지 않습니다.

`test → package_completion → review`를 통과해야 최종 `COMPLETED` 상태가 됩니다.
