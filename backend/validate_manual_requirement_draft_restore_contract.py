from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')

checks = {
    'frontend version 5.338': "AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,
    'path selection no automatic restore': "프로젝트 경로만 선택한 상태에서는 과거 대화를 자동으로 불러오지 않습니다." in APP,
    'explicit previous draft restore action': '이전 요구사항 이어서 불러오기' in APP,
    'keep current interview action': '현재 인터뷰 유지' in APP,
    'draft candidate state': 'requirementDraftCandidate' in APP,
    'draft decision pending state': 'requirementDraftDecisionPending' in APP,
    'autosave paused while decision pending': 'requirementDraftDecisionPendingRef.current' in APP and 'return false' in APP,
    'legacy flattened code dump detection': 'looksLikeFlattenedDump' in APP and 'inlineCodeSignals' in APP,
    'legacy assistant draft sanitized on restore': "item?.role==='assistant'" in APP and 'protectInterviewAssistantAnswer(item?.content' in APP,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[manual-draft-restore] {name}: {'OK' if ok else 'FAIL'}")

if failed:
    raise SystemExit('contract failed: ' + ', '.join(failed))
print('[manual-draft-restore] PASS')
