from pathlib import Path

root = Path(__file__).resolve().parents[1]
renderer = (root / 'frontend/src/components/notebook/NotebookRenderers.tsx').read_text(encoding='utf-8')
app = (root / 'frontend/src/App.jsx').read_text(encoding='utf-8')
routes = (root / 'backend/app/api/routes.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.395'" in app,
    'backend version': '"version": "5.395"' in routes,
    'raw img token': '<img\\b[^>]*\\/?>' in renderer,
    'html img parser': 'parseNotebookHtmlImageTag' in renderer,
    'safe image source': 'notebookSafeImageSource' in renderer,
    'http whitelist': '/^https?:\\/\\//i.test(source)' in renderer,
    'javascript not whitelisted': 'javascript:' not in renderer,
    'no referrer remote image': 'referrerPolicy="no-referrer"' in renderer,
    'image load fallback': '이미지를 불러오지 못했습니다.' in renderer,
    'markdown image preserved': "value.startsWith('![')" in renderer,
    'attachment image preserved': 'notebookAttachmentDataUrl' in renderer,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit(f'v5.395 contract failed: {failed}')
print(f'v5.395 contract PASS {len(checks)}/{len(checks)}')
