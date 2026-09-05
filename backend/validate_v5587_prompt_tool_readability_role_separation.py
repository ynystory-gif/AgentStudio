from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
checks = {
    'frontend/src/app/App.tsx': ["AGENTSTUDIO_FRONTEND_VERSION='5.587'", 'Agent 실행 정책', '세부 Registry / 기존 Agent 호환 설정', "onOpenStudio={()=>changeDesignCenterTab('STUDIO')}",],
    'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx': ['pts-ai-recommend-badge', 'Studio 버전 저장', 'Agent 설계에 적용'],
    'frontend/src/styles.css': ['v5.587 readability + Prompt/Tool responsibility separation', '.pts-head>.pts-head-actions', '.tool-prompt-studio-summary'],
    'backend/app/api/routes.py': ['"version": "5.587"'],
    'backend/app/main.py': ['version="5.587"'],
}
for rel, tokens in checks.items():
    text = (root / rel).read_text(encoding='utf-8')
    for token in tokens:
        assert token in text, f'{rel}: missing {token}'

for css in (root / 'frontend/src').rglob('*.css'):
    text = css.read_text(encoding='utf-8')
    for match in re.finditer(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', text, re.I):
        assert float(match.group(1)) >= 13, f'{css}: font-size {match.group(1)}px'
    for match in re.finditer(r'\bfont\s*:\s*([^;{}]*?)(\d+(?:\.\d+)?)px', text, re.I):
        assert float(match.group(2)) >= 13, f'{css}: font shorthand {match.group(2)}px'
print('[PASS] v5.587 Prompt & Tool Studio readability / role separation contracts')
