from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
PS1 = (ROOT / 'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8-sig')
DOC = (ROOT / 'docs' / 'ATTACHMENT_ANALYSIS_RESIZABLE_SCROLL_PANEL_V5363.md').read_text(encoding='utf-8')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit('v5.371 contract failed: ' + message)


require("AGENTSTUDIO_FRONTEND_VERSION='5.371'" in APP, 'frontend version')
require('version="5.371"' in MAIN or "version='5.371'" in MAIN, 'backend version')
require('"version": "5.371"' in ROUTES, 'health version')
require('$FallbackAgentStudioVersion = "5.371"' in PS1, 'SYSTEM_ADMIN fallback version')
require('ResizableAttachmentAnalysisPanel' in ROUTES, 'health build marker')

require('attachment-ai-summary-scroll' in APP, 'single internal scroll surface missing')
require('attachment-ai-summary-resize-handle' in APP, 'resize handle missing')
require('onPointerDown={beginPanelResize}' in APP, 'pointer resize start binding missing')
require('onPointerMove={movePanelResize}' in APP, 'pointer resize move binding missing')
require('onPointerUp={endPanelResize}' in APP, 'pointer resize end binding missing')
require('onDoubleClick={resetPanelHeight}' in APP, 'double-click reset missing')
require("agentstudio.attachmentAnalysisSummaryHeight" in APP, 'persisted panel height missing')
require('기본 높이' in APP, 'default height action missing')
require('내부 스크롤 · 아래 조절선을 드래그해 높이 변경' in APP, 'resize guidance missing')

require('.attachment-ai-summary-card.resizable' in CSS, 'resizable full-card CSS missing')
require('max-height:72vh' in CSS, 'viewport height guard missing')
require('min-height:180px' in CSS, 'minimum height guard missing')
require('overflow-y:auto' in CSS, 'internal vertical scroll missing')
require('cursor:ns-resize' in CSS, 'resize cursor missing')
require('.attachment-ai-summary-card.resizable .attachment-requirement-list' in CSS and 'max-height:none' in CSS, 'nested requirement scroll removal missing')
require('Compact Sidebar Summary' in DOC, 'documentation incomplete')

print('PASS v5.371 Attachment Analysis Resizable Scroll Panel contract')
