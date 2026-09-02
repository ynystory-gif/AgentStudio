# THEANOVA AgentStudio v5.498 — Media Workflow Core

## 목적
AgentStudio를 ComfyUI 복제품으로 만들지 않고 Agent Creator / Agent Editor가 미디어 생성·처리 Agent를 설계·생성·수정할 수 있도록 기존 Workflow Core를 확장합니다.

## 이번 버전
- 고수준 Media Node Registry와 Typed Port 계약
- Media Artifact / Async Job 상태 계약
- Provider Adapter 공통 계약(health/capabilities/submit/status/result/cancel)
- 기존 Workflow Schema를 교체하지 않는 `extensions.media` additive extension
- Media Agent 전문화 설계 및 증분 수정 시 specialization 보존
- ComfyUI를 외부 Provider로 계획하고 Workflow JSON/Input/Output Mapping/Queue/Progress/Cancel 책임 분리
- 기술 Retry와 품질 Correction Retry 분리
- Human Approval을 WAITING_APPROVAL interrupt/resume로 설계
- Target Workflow UI에서 Media Input/Analysis/Plan/Execution/Approval/Preview 그룹 표시
- `/api/media/workflow/catalog`, `/contracts`, `/validate-port`, `/normalize`, `/validate` 제공

## 단계
현재 v5.498은 Media Workflow Core와 Agent Factory 설계 계약을 먼저 확장한 단계입니다. 실제 Provider 실행 구현은 생성 대상 Agent의 Adapter로 생성되며, AgentStudio 자체에는 ComfyUI의 KSampler/VAE/Checkpoint 같은 저수준 Node를 복제하지 않습니다.
