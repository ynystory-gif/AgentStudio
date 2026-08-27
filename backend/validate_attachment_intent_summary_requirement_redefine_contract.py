from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
REQ = (ROOT / 'backend' / 'app' / 'services' / 'requirements_agent.py').read_text(encoding='utf-8')
STYLE = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')

checks = {
    'frontend version 5.338': "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
    'automatic attachment intent summary endpoint': '/chat/interview/attachments/summary' in ROUTES,
    'summary uses requirements provider router': 'summarize_attachment_requirements' in ROUTES and 'LLMTask.REQUIREMENTS_ANALYSIS' in REQ,
    'summary output contract': all(x in REQ for x in ['만들고자 하는 내용','핵심 기능','입력 / 데이터','기술 / 연동','추가 확인이 필요한 항목']),
    'raw attachment echo protected': '_looks_like_attachment_echo' in REQ and '파일 원문' in REQ,
    'frontend auto summary after attachment preparation': "api('/chat/interview/attachments/summary'" in APP and 'interviewAttachmentSummaryBusy' in APP,
    'summary card shown to user': '첨부 파일 AI 정리' in APP and 'attachment-ai-summary-card' in STYLE,
    'summary becomes session context': 'setInterviewAttachmentMemory' in APP and 'attachment_summary:interviewAttachmentSummary' in APP,
    'restored conversation individual delete': 'removeRequirementConversationTurn' in APP and '사용자 답변' in APP,
    'full previous content reset': 'clearRestoredRequirementContent' in APP and '지난 내용 전체 삭제 후 재정의' in APP,
    'requirement manual redefine': 'requirementManualOverrides' in APP and 'saveRequirementRedefinition' in APP and '요구사항 항목 재정의' in APP,
    'workflow invalidated after requirement edit': 'invalidateRequirementWorkflowAfterEdit' in APP and "setAgentBuildStage('REQUIREMENTS')" in APP,
    'manual override included in workflow prompt': '사용자가 직접 재정의한 최신 요구사항 - 이전 대화보다 우선' in APP,
    'draft persists summary and overrides': 'manual_requirement_overrides:requirementManualOverrides' in APP and 'attachment_summary_files' in APP,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[v5.338-contract] {name}: {'OK' if ok else 'FAIL'}")
if failed:
    raise SystemExit('contract failed: ' + ', '.join(failed))
print('[v5.338-contract] PASS')
