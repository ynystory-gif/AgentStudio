from pathlib import Path
root=Path(__file__).resolve().parents[1]
css=(root/'frontend/src/styles.css').read_text(encoding='utf-8')
app=(root/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
checks={
 'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.518'" in app,
 'codex visible border': '.codex-selectors select{' in css and 'border:1px solid #344b60' in css,
 'codex footer divider': 'border-top:1px solid rgba(95,125,151,.18)' in css,
 'transcript column header': '.project-live-transcript-head{' in css and 'flex-direction:column' in css,
 'transcript keep-all': 'word-break:keep-all' in css,
 'transcript vertical scroll': 'overflow-y:scroll' in css and 'scrollbar-gutter:stable' in css,
}
failed=[name for name,ok in checks.items() if not ok]
for name,ok in checks.items(): print(f"[v5.518] {name}: {'PASS' if ok else 'FAIL'}")
if failed: raise SystemExit('failed: '+', '.join(failed))
