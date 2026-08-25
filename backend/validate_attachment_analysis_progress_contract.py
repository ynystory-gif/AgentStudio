from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/ai_attachment_service.py').read_text(encoding='utf-8')
PICKER = (ROOT / 'frontend/src/components/ai/AiAttachmentPicker.tsx').read_text(encoding='utf-8')
CODEX = (ROOT / 'frontend/src/components/codex/CodexPanel.tsx').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')

checks = {
    'backend analysis job endpoint': '@router.post("/ai/attachments/analyze")' in ROUTES,
    'real extraction stages': all(token in ROUTES for token in ['파일 확인', '텍스트 추출', 'Context 준비', '준비 완료']),
    'per-file job progress payload': '"overall_progress"' in ROUTES and '"files": [dict(item) for item in rows]' in ROUTES,
    'attachment extraction cache': '_content_cache' in SERVICE and 'def prepare_attachment(' in SERVICE and 'def _prepared_content(' in SERVICE,
    'picker per-file progress UI': 'ai-attachment-progress-row' in PICKER and 'role="progressbar"' in PICKER,
    'picker waits for terminal analysis state': "status === 'SUCCESS' || status === 'FAILED'" in PICKER,
    'agent interview integration': 'analysisPurpose="Agent 설계 인터뷰 참고 파일 분석 준비"' in APP and 'setInterviewAttachmentAnalysis' in APP,
    'code editor integration': 'analysisPurpose="LLM 대화형 코드 편집 참고 파일 분석 준비"' in APP and 'setCodeEditAttachmentAnalysis' in APP,
    'codex integration': 'analysisPurpose="Codex 참고 파일 분석 준비"' in CODEX and 'setAttachmentAnalysis' in CODEX,
    'send blocked until attachment prep terminal': 'interviewAttachmentAnalysis.ready' in APP and 'codeEditAttachmentAnalysis.ready' in APP and 'attachmentAnalysis.ready' in CODEX,
    'progress styles': all(token in CSS for token in ['.ai-attachment-analysis', '.ai-attachment-file-track', '.ai-attachment-file-fill']),
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ': ' + name)
if failed:
    raise SystemExit('Attachment analysis progress contract failed: ' + ', '.join(failed))
print('ATTACHMENT_ANALYSIS_PROGRESS_CONTRACT_PASS')
