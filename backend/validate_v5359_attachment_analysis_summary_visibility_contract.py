from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
REQ = (ROOT / 'backend' / 'app' / 'services' / 'requirements_agent.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,
    'backend version': 'version="5.368"' in MAIN or "version='5.368'" in MAIN,
    'health version': '"version": "5.368"' in ROUTES,
    'summary component': 'function AttachmentAnalysisSummaryCard' in APP,
    'summary parser': 'parseAttachmentSummarySections' in APP,
    'sidebar summary': 'compact={true}' in APP,
    'normal chat summary binding': "result?.attachment_summary" in APP,
    'backend display summary helper': 'build_attachment_requirements_display_summary' in REQ,
    'backend summary response': '"attachment_summary": attachment_summary' in ROUTES,
    'summary css': '.attachment-ai-summary-card' in CSS,
    'draft keeps summary': 'attachment_summary:interviewAttachmentSummary' in APP,
    'draft keeps files': 'attachment_summary_files:interviewAttachmentSummaryFiles' in APP,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.368 contract failed: ' + ', '.join(failed))
print('PASS v5.368 Attachment Analysis Summary Visibility contract')
