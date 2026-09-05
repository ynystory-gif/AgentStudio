from pathlib import Path

root=Path(__file__).resolve().parents[1]
app=(root/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
comp=(root/'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx').read_text(encoding='utf-8')
model=(root/'frontend/src/features/prompt-tool-studio/model.ts').read_text(encoding='utf-8')
service=(root/'frontend/src/features/prompt-tool-studio/service.ts').read_text(encoding='utf-8')
backend=(root/'backend/app/services/prompt_tool_studio_service.py').read_text(encoding='utf-8')
routes=(root/'backend/app/api/routes.py').read_text(encoding='utf-8')
css=(root/'frontend/src/styles.css').read_text(encoding='utf-8')
checks={
 'version':"AGENTSTUDIO_FRONTEND_VERSION='5.579'" in app and 'version="5.579"' in (root/'backend/app/main.py').read_text(encoding='utf-8'),
 'provider_binding':'provider={provider}' in app,
 'ai_endpoint':'/prompt-tool-studio/analyze' in routes and 'analyze_prompt_tool_input' in backend and "LLMTask.REQUIREMENTS_ANALYSIS" in backend,
 'semantic_split':'splitSemanticUnits' in model and 'semantic_units' in backend,
 'pending_question':'inferPendingQuestion' in model and 'expectedSchema' in model,
 'context_relation':'contextRelations' in model and 'context_relations' in backend,
 'history':'StateHistory' in model and 'REPLACE' in model and '변경 History' in comp,
 'source_confidence':'sourceMessageId' in model and 'confidence' in model and 'Raw Structured Output' in comp,
 'validation':'validate(' in model and 'Validation' in comp and 'conflicts' in model,
 'tool_editor':'ToolEditor' in comp and 'Input Schema' in comp and 'Output Schema' in comp and 'Permission' in comp and 'Timeout' in comp and 'Retry' in comp,
 'tool_bidirectional':'ToolSourceEditor' in comp and 'Visual에 적용' in comp,
 'tool_usage':'사용 위치' in comp,
 'routing_editor':'RoutingEditor' in comp and 'Intent Router' in comp and 'LangGraph State' in comp,
 'tests':'Full Agent Test' in comp and 'Input / Extraction / Validation 테스트' in comp,
 'prompt_versions':'Prompt Version' in comp and '버전 저장' in comp,
 'negative_prompt':'Negative Prompt' in comp and 'Must Not과 별도' in comp,
 'recommend_impact':'영향:' in comp and 'stateOverrides' in comp,
 'details':'상세 분석' in comp and 'Trace' in comp,
 'independent_scroll':'.pts-tool-scroll' in css and '.pts-test .pts-scroll' in css,
 'local_persistence':"agentstudio.promptToolStudio.v2" in comp,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
if failed: raise SystemExit('FAILED: '+', '.join(failed))
print('v5.579 Prompt & Tool Studio phase 2 validation: PASS')
