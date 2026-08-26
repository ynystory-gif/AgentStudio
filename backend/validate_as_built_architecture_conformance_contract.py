from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.as_built_architecture import build_as_built_architecture, compare_architectures

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / 'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
ROUTER = (ROOT / 'backend/app/services/model_router.py').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
PANELS = (ROOT / 'frontend/src/components/architecture/ArchitecturePanels.tsx').read_text(encoding='utf-8')
POLICY = (ROOT / 'backend/app/data/agent_factory/agent_factory_workflow_policy.json').read_text(encoding='utf-8')

checks = {
    'frontend version 5.341': "AGENTSTUDIO_FRONTEND_VERSION='5.356'" in APP,
    'as-built workflow node': '"as_built_architecture"' in WORKFLOW and 'as_built_architecture_node' in WORKFLOW,
    'conformance workflow node': '"architecture_conformance"' in WORKFLOW and 'architecture_conformance_node' in WORKFLOW,
    'conformance repair route': 'ARCHITECTURE_REPAIR_READY' in WORKFLOW and 'architecture_repair_iteration' in WORKFLOW,
    'completion review gate': 'Architecture Conformance Gate 미통과' in WORKFLOW,
    'high performance task': 'ARCHITECTURE_CONFORMANCE = "architecture_conformance"' in ROUTER,
    'design panel': '<GeneratedAgentArchitecturePanel report={r} />' in APP,
    'as-built panel': '<AsBuiltAgentArchitecturePanel report={r} />' in APP,
    'conformance panel': '<ArchitectureConformancePanel report={r} />' in APP,
    'conformance UI score': 'DESIGN ↔ AS-BUILT CONFORMANCE GATE' in PANELS,
    'policy completion gate': 'architecture_conformance_pass' in POLICY,
}

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / 'backend/app').mkdir(parents=True)
    (root / 'frontend/src').mkdir(parents=True)
    (root / 'backend/app/main.py').write_text(
        'from fastapi import FastAPI\nfrom langgraph.graph import StateGraph\napp=FastAPI()\n@app.get("/health")\ndef health(): return {"ok": True}\n',
        encoding='utf-8',
    )
    (root / 'frontend/src/App.jsx').write_text(
        'import React from "react"; export default function App(){return <div>ok</div>}',
        encoding='utf-8',
    )
    design = {
        'components': [{'name': 'Backend API'}, {'name': 'Frontend UI'}],
        'interfaces': ['HTTP API', 'React UI'],
        'state': ['LangGraph State'],
        'persistence': [],
        'security': [],
    }
    file_plan = {
        'component_file_map': [
            {'component': 'Backend API', 'files': ['backend/app/main.py']},
            {'component': 'Frontend UI', 'files': ['frontend/src/App.jsx']},
        ],
        'new_files': [
            {'path': 'backend/app/main.py', 'required': True},
            {'path': 'frontend/src/App.jsx', 'required': True},
        ],
    }
    actual = build_as_built_architecture(str(root), design, file_plan)
    passing = compare_architectures(design, actual, file_plan)
    checks['deterministic PASS score'] = passing.get('ok') is True and float(passing.get('score') or 0) >= 85

    (root / 'frontend/src/App.jsx').unlink()
    broken = build_as_built_architecture(str(root), design, file_plan)
    failing = compare_architectures(design, broken, file_plan)
    checks['missing file blocks gate'] = failing.get('ok') is False and int(failing.get('critical_count') or 0) >= 1

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[v5.341-architecture-contract] {name}: {'OK' if ok else 'FAIL'}")
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
print('[v5.341-architecture-contract] PASS')
