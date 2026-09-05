from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
comp=(root/'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx').read_text(encoding='utf-8')
css=(root/'frontend/src/styles.css').read_text(encoding='utf-8')
checks={
 'version':"AGENTSTUDIO_FRONTEND_VERSION='5.578'" in app,
 'central_tabs':'design-center-tabs' in app and 'Prompt &amp; Tool Studio' in app,
 'right_panel_preserved':'workspace-info-panel' in app and "workspaceTab==='DESIGN'" in app,
 'studio_5_tabs':all(x in comp for x in ["'INPUT'","'PROMPT'","'TOOL'","'ROUTING'","'TEST'"]),
 'multi_label':all(x in comp for x in ['QUESTION','ANSWER','REQUEST','CORRECTION','CONFIRMATION']),
 'state_status':all(x in comp for x in ['CONFIRMED','CANDIDATE','MISSING','RECOMMENDED','CHANGED','CONFLICT']),
 'prompt_modes':all(x in comp for x in ['VISUAL','TEXT','COMPILED','Must Do','Must Not Do']),
 'response':'Response Plan' in comp and 'Response Preview' in comp,
 'recommend':'AI 추천' in comp and '적용' in comp and '무시' in comp,
 'scroll':'.pts-scroll' in css and 'overflow:auto' in css,
 'state_persistence':'localStorage' in comp and 'agentstudio.designCenterTab' in app,
}
failed=[k for k,v in checks.items() if not v]
for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
if failed: raise SystemExit('FAILED: '+', '.join(failed))
print('v5.578 Prompt & Tool Studio validation: PASS')
