from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX=(ROOT/'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks={
  'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.457'" in APP,
  'backend version': 'version="5.457"' in MAIN and '"version": "5.457"' in ROUTES,
  'codex version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.457"' in CODEX,
  'new design step': "['07','개발 계획',developmentPlanSummary]" in APP and "['08','최종 확인',leftSummary.confirmation]" in APP,
  'right tabs': "builderSummaryTab==='REQUIREMENTS'" in APP and "builderSummaryTab==='STAGES'" in APP and "builderSummaryTab==='SUMMARY'" in APP and 'workspace-design-tabs' in APP,
  'stage edit button': '>단계 수정</button>' in APP,
  'stage add': '＋ Stage 추가' in APP,
  'stage remove': 'className="danger" onClick={()=>removeDraft(index)}' in APP,
  'stage reorder': 'moveDraft(index,-1)' in APP and 'moveDraft(index,1)' in APP,
  'stage editable fields': '포함 기능 · 한 줄에 하나' in APP and '완료 / 테스트 조건 · 한 줄에 하나' in APP,
  'manual plan invalidates workflow': 'applyUserEditedDevelopmentStagePlan' in APP and 'setTargetWorkflowPreview(null)' in APP,
  're-recommend invalidates approval': 'if(force&&developmentStagePlan?.approved)' in APP,
  'stage approval gate cta': "!developmentStagePlan?.approved||projectCreateFlowBusy" in APP and '개발 계획 승인 후 프로젝트 생성' in APP and 'developmentPlanApproved={Boolean(developmentStagePlan?.approved)}' in APP,
  'smart create flow': 'className="create-project-cta" onClick={createAgentProjectSmart}' in APP,
  'chat stage decision': APP.count('builder-development-plan-inline') >= 2 and '개발 Stage 검토' in APP,
  'design summary': 'function AgentDesignSummaryPanel' in APP and 'Agent 설계 요약' in APP,
  'workflow completion checks': 'development-stage-workflow-checks' in APP and 'Checkpoint' in APP and 'Stage Test' in APP,
  'stage editor css': 'v5.457 New Agent Development Plan UX' in CSS and '.development-stage-editor{' in CSS and '.design-plan-tabs-card{' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.457 contract failed: '+', '.join(failed))
print(f"v5.457 contracts: {len(checks)}/{len(checks)} PASS")
