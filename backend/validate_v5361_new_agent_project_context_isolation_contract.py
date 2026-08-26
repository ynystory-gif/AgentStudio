from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')


def require(cond,msg):
    if not cond:
        raise SystemExit('v5.368 contract failed: '+msg)

require("AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,'frontend version')
require('version="5.368"' in MAIN or "version='5.368'" in MAIN,'backend version')
require('"version": "5.368"' in ROUTES,'health version')
require('const projectContextEpochRef=useRef(0)' in APP,'project context epoch ref')
require('projectContextEpochRef.current+=1' in APP,'new Agent invalidates pending project work')
require('const loadContextEpoch=++projectContextEpochRef.current' in APP,'project load creates new context epoch')
require('if(projectContextEpochRef.current!==requestContextEpoch) return null' in APP,'adaptive stale response guard')
require("setLoadedProjectAnalysis(null)" in APP,'new Agent clears loaded project analysis')
require("setWorkflowReq('')" in APP,'new Agent clears stale workflow request')
require('setConfirmedInterviewRequirements({})' in APP,'new Agent clears prior confirmed requirements')
require("setDbErdReport(null)" in APP,'new Agent clears DB ERD')
require("setLiveDatabasePreview(null)" in APP,'new Agent clears live DB design')
require("setAnalysis(null)" in APP,'new Agent clears analysis report')
require("setWorkflowView('TARGET')" in APP,'new Agent opens target workflow')
require('const adaptive=selectedProjectId' in APP,'report adaptive fallback gated by selected project')
require("(selectedProjectId?loadedProjectAnalysis?.adaptive_report?.workflow?.name:null)" in APP,'workflow title fallback gated')
require("(selectedProjectId?loadedProjectAnalysis?.adaptive_report?.workflow:null)" in APP,'workflow diagram fallback gated')
print('PASS v5.368 New Agent Project Context Isolation contract')
