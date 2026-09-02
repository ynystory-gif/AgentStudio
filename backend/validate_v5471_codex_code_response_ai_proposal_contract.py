from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CODEX_PANEL = (ROOT / 'frontend/src/components/codex/CodexPanel.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX_SERVICE = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []
def check(name, ok):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

check('frontend version 5.471', "AGENTSTUDIO_FRONTEND_VERSION='5.471'" in APP)
check('backend version 5.471', 'version="5.471"' in MAIN)
check('health route version 5.471', '"version": "5.471"' in ROUTES)
check('Codex client version 5.471', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.471"' in CODEX_SERVICE)
check('build marker', 'CodexCodeResponseAiProposalRouting' in ROUTES)
check('Codex code response parser exists', 'function parseCodexCodeProposal' in CODEX_PANEL)
check('parser requires fenced code', "source.includes('```')" in CODEX_PANEL)
check('parser preserves explanation block', "type: 'explanation'" in CODEX_PANEL)
check('parser preserves code block', "type: 'code'" in CODEX_PANEL)
check('Codex proposal callback prop exists', 'onCodeProposal?: (proposal: CodexCodeProposal) => void' in CODEX_PANEL)
check('completed code response routed to proposal', 'parsedProposal && onCodeProposal' in CODEX_PANEL and 'onCodeProposal({' in CODEX_PANEL)
check('non-code response remains transcript', "setTranscript(prev => prev.map(row => row.id === activeId ? { ...row, text } : row))" in CODEX_PANEL)
check('code response removed from transcript', 'prev.filter(row => row.id !== activeId)' in CODEX_PANEL)
check('Codex registration notice remains', '코드가 포함된 답변을 AI 변경 제안으로 등록했습니다.' in CODEX_PANEL)
check('question preserved', 'lastSubmittedQuestionRef.current = text' in CODEX_PANEL)
check('App registers Codex proposal', 'registerCodexCodeProposal=React.useCallback' in APP)
check('App switches to proposal tab', "setCodeRightPanelTab('PROPOSAL')" in APP)
check('Codex panel callback connected', 'onCodeProposal={registerCodexCodeProposal}' in APP)
check('multi-block proposal rendered', "proposalType==='codex_blocks'" in APP and 'codeEditProposal.blocks.map' in APP)
check('code block numbering rendered', '코드 {codeIndex}/{Number(codeEditProposal.codeBlockCount||0)}' in APP)
check('code copy button rendered', '>코드 복사</button>' in APP)
check('explanation/code CSS exists', '.codex-proposal-explanation' in CSS and '.codex-proposal-code-block' in CSS)

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.471 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.471 Codex code response AI proposal contract: ALL PASS ({len(checks)}/{len(checks)})')
