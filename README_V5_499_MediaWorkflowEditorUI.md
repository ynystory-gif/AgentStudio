# THEANOVA AgentStudio v5.499 — Media Workflow Editor UI

## 목적
Media Agent가 자동 설계한 Workflow를 기존 그룹형 화면에서 확인하는 데 그치지 않고, AgentStudio 안에서 고수준 Media Node를 직접 보고 수정할 수 있도록 Workflow UI를 확장합니다.

## 주요 변경
- 기존 Target Agent Workflow 그룹형 UI 보존
- Media Agent에서 `Media Workflow Editor` 진입 버튼 추가
- Backend `/api/media/workflow/catalog` 기반 Node Palette
- Drag/Click Node 추가, Canvas 내 Node 이동/삭제
- Output Port → Input Port 연결과 Backend Typed Port 검증
- Node 설정: Provider, Model/Workflow, Width/Height, Max Retry, Prompt/Instructions
- 전체 Workflow Validation 및 Normalize 후 설계 반영
- Workflow JSON Import/Export
- Artifact/Job 정보가 존재할 경우 Preview·Provider·Status·Progress 표시
- Editor 변경사항을 `target_agent_workflow.nodes/edges/extensions.media`에 저장하여 기존 Agent 설계 Draft/Checkpoint 저장 흐름 재사용

## 실행 범위
이 버전은 Media Workflow **Editor UI와 설계 계약 연결** 단계입니다. AgentStudio 자체가 ComfyUI를 실행하거나 저수준 KSampler/VAE/Checkpoint 편집기를 복제하지 않습니다. 실제 Media Provider 실행은 생성 대상 Agent의 Provider Adapter Runtime이 담당합니다.
