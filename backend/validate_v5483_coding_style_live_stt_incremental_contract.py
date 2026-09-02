from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MEMO = (ROOT / 'frontend/src/components/memo/ProjectMemoPanel.tsx').read_text(encoding='utf-8')
MEDIA = (ROOT / 'frontend/src/components/media/MediaSessionProvider.tsx').read_text(encoding='utf-8')
STT = (ROOT / 'backend/app/services/live_stt_service.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
README = (ROOT / 'README_V5_483.md').read_text(encoding='utf-8')

passed = 0
failed = 0

def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f'[PASS] {name}')
    else:
        failed += 1
        print(f'[FAIL] {name}')

check('frontend version 5.483', "AGENTSTUDIO_FRONTEND_VERSION='5.483'" in APP)
check('backend version 5.483', 'version="5.483"' in MAIN)
check('health version 5.483', '"version": "5.483"' in ROUTES)
check('presentation version 5.483', '            "5.483",' in ROUTES)
check('codex client version 5.483', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.483"' in CODEX)
check('health build marker', '+CodingStylePanelPolish+LiveTranscriptProvisionalImmediateRender+TimeRangeRefinedReplacement+TranscriptCollectionRefineCompleteStatus' in ROUTES)

check('coding style still has ten options', APP.count("'이름 · 타입']") >= 6 and APP.count("'구조 · Notebook']") >= 4)
check('coding style has grouped descriptions', '읽기 쉬운 이름과 타입 안정성을 유지합니다.' in APP and 'Notebook과 반복 로직의 구조를 일관되게 정리합니다.' in APP)
check('coding style has select all action', '>전체 선택</button>' in APP)
check('coding style has compact default action', '>기본값</button>' in APP)
check('coding style has close action', "removeAttribute('open')" in APP)
check('coding style popup uses fixed viewport overlay', '.agent-coding-style-menu[open] .agent-coding-style-popover' in CSS and 'position:fixed;' in CSS and 'transform:translateY(-50%);' in CSS)
check('coding style popup keeps two logical columns', '.agent-coding-style-groups{grid-template-columns:1fr 1fr;gap:10px;}' in CSS)
check('coding style group title has description styling', '.agent-coding-style-group-title>small' in CSS)

check('summary endpoint preserved', '@router.post("/media-stt/summarize")' in ROUTES)
check('summary button moved into transcript head', 'project-live-transcript-head-actions' in MEMO and "'✦ 요약정리'" in MEMO)
check('summary still includes current transcript text', "String(mediaSession.transcriptText || '').trim()" in MEMO)
check('summary result UI preserved', 'Transcript 요약정리' in MEMO and 'project-live-summary-body' in MEMO)

check('transcript stage type exists', "type TranscriptStage = 'IDLE' | 'COLLECTING' | 'REFINING' | 'COMPLETED' | 'ERROR'" in MEDIA)
check('transcript stage exposed by context', 'transcriptStage: TranscriptStage' in MEDIA and 'transcriptStage,' in MEDIA)
check('three-stage UI is rendered', '1</b> 수집 중' in MEMO and '2</b> 보정 중' in MEMO and '3</b> 완료' in MEMO)
check('three-stage UI styling exists', '.project-live-stage-flow' in CSS and 'active.collecting' in CSS and 'active.refining' in CSS and 'active.completed' in CSS)

check('backend partial carries time-ranged provisional segment', '"provisional": True' in STT and '"segment": partial_segment' in STT and 'partial_start_ms' in STT and 'partial_end_ms' in STT)
check('frontend provisional segment state exists', 'const [interimSegment, setInterimSegment]' in MEDIA)
check('frontend partial event creates provisional segment immediately', "if (type === 'partial')" in MEDIA and 'provisional: true' in MEDIA and 'setInterimSegment(provisional)' in MEDIA)
check('provisional segment included in transcript text', 'formatTranscript(transcriptSegments, interimText, interimSegment)' in MEDIA)
check('provisional UI shows real time and collecting state', 'mediaSession.interimSegment.offsetMs' in MEMO and '<em>수집 중</em>' in MEMO)
check('live committed segments show collected state', "segment.refined ? '보정 완료' : '수집됨'" in MEMO)

check('backend refined event supplies replacement coverage', '"rangeStartMs": 0' in STT and '"rangeEndMs": duration_ms' in STT)
check('frontend range replacement helper exists', 'function replaceTranscriptRange(' in MEDIA)
check('refined event uses range replacement rather than blind overwrite', 'const nextSegments = replaceTranscriptRange(' in MEDIA and 'transcriptSegmentsRef.current,' in MEDIA)
check('refined result clears provisional segment', "setInterimSegment(null)" in MEDIA)
check('refined result persists merged replacement', 'persistTranscriptSnapshot({ segments: nextSegments })' in MEDIA)

check('release README documents requested incremental behavior', 'v5.482' in README and '요약정리' in README and '수집 중 → 보정 중 → 완료' in README and '임시 Segment' in README)

print(f'\nTOTAL: {passed} PASS / {failed} FAIL')
raise SystemExit(1 if failed else 0)
