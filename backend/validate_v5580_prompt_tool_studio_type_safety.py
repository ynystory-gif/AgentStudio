from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
comp=(root/'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx').read_text(encoding='utf-8')
model=(root/'frontend/src/features/prompt-tool-studio/model.ts').read_text(encoding='utf-8')
main=(root/'backend/app/main.py').read_text(encoding='utf-8')
checks={
 'version': "AGENTSTUDIO_FRONTEND_VERSION='5.580'" in app and 'version="5.580"' in main,
 'legacy_chat_bridge': 'type StudioChatInput={role?:unknown;content?:unknown;turn_type?:unknown}' in comp and 'useMemo<StudioChatMessage[]>' in comp and 'String(m?.content??' in comp,
 'normalized_state': 'buildState(studioChat)' in comp and 'detectAgentMediaType(studioChat)' in comp,
 'safe_latest': ".at(-1)?.content??''" in comp,
 'safe_missing': 'const nextMissing=missing.at(0)' in comp and 'nextMissing.label' in comp,
 'safe_tab_label': 'x.charAt(0)+x.slice(1).toLowerCase()' in comp,
 'safe_port_groups': 'const frontPort=ports.at(0)?.[1]' in model and 'const backPort=bp.at(0)?.[1]' in model and 'const genericPort=generic?.[1]' in model,
 'safe_pending_tuple': "if(found)return {id:found[1],question:q,expectedSchema:found[2]}" in model,
 'phase2_preserved': 'ToolEditor' in comp and 'RoutingEditor' in comp and 'Raw Structured Output' in comp and 'Negative Prompt' in comp,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
if failed: raise SystemExit('FAILED: '+', '.join(failed))
print('v5.580 Prompt & Tool Studio type safety regression validation: PASS')
