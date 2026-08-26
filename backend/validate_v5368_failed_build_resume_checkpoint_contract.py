from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
PS1=(ROOT/'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')

def require(ok,msg):
    if not ok:
        raise SystemExit('FAIL v5.368: '+msg)

require("AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,'frontend version')
require('version="5.368"' in MAIN or "version='5.368'" in MAIN,'backend version')
require('"version": "5.368"' in ROUTES,'health version')
require('$FallbackAgentStudioVersion = "5.368"' in PS1,'launcher version')
require('/workflow/design-checkpoint' in ROUTES,'persistent design checkpoint endpoints')
require('agentstudio_design_checkpoint.json' in ROUTES,'project-folder checkpoint file')
require('PROJECT_DIAGNOSTICS' in ROUTES,'legacy diagnostics fallback')
require('restoredBuildResume' in APP,'restored build resume state')
require('previous_build_state:(()=>{' in APP,'restored previous build state binding')
require('resume_context:restoredBuildResume' in APP,'resume context passed to Agent Factory')
require('이전 설계/개발 기록 이어서 불러오기' in APP,'resume UX')
require('saveRequirementDraft(completedResume)' in APP,'completed/failure build persistence')
require('saveRequirementDraft(failedResume)' in APP,'exception failure persistence')
print('PASS v5.368 Failed Build Resume Checkpoint contract')
