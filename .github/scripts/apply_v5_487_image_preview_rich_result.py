from pathlib import Path
import re

# ---------- frontend/src/utils/editor.ts ----------
editor = Path('frontend/src/utils/editor.ts')
text = editor.read_text(encoding='utf-8')

if 'export function isImageFile' not in text:
    marker = "export const isBinaryPreviewFile = (filePath = ''): boolean => isPdfFile(filePath) || isPresentationFile(filePath)"
    if marker not in text:
        raise SystemExit('editor binary-preview marker not found')
    replacement = """export function isImageFile(filePath = ''): boolean {
  const ext = String(filePath || '').trim().toLowerCase().split('.').pop() || ''
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'avif'].includes(ext)
}

export const isBinaryPreviewFile = (filePath = ''): boolean =>
  isPdfFile(filePath) || isPresentationFile(filePath) || isImageFile(filePath)"""
    text = text.replace(marker, replacement, 1)
editor.write_text(text, encoding='utf-8')

# ---------- frontend/src/components/viewers/DocumentViewers.tsx ----------
viewer = Path('frontend/src/components/viewers/DocumentViewers.tsx')
text = viewer.read_text(encoding='utf-8')
if 'export function ImageViewer' not in text:
    insertion_marker = 'export function PdfViewer({' 
    if insertion_marker not in text:
        raise SystemExit('PdfViewer marker not found')
    image_viewer = r'''export function ImageViewer({ filePath = '', projectRoot = '', revision = 0 }: BinaryViewerProps) {
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [previewLoading, setPreviewLoading] = useState(true)
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 })
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    let cancelled = false
    let objectUrl = ''
    setPreviewLoading(true)
    setPreviewError('')
    setPreviewUrl('')
    setNaturalSize({ width: 0, height: 0 })
    setZoom(1)

    const params = new URLSearchParams({
      root: String(projectRoot || ''),
      relative_path: String(filePath || ''),
      v: String(revision),
    })

    apiFetch(`/files/image?${params.toString()}`)
      .then(response => response.blob())
      .then(blob => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setPreviewUrl(objectUrl)
        setPreviewLoading(false)
      })
      .catch(error => {
        if (cancelled) return
        setPreviewLoading(false)
        setPreviewError(error instanceof Error ? error.message : String(error || '이미지 미리보기를 불러오지 못했습니다.'))
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [filePath, projectRoot, revision])

  const zoomPercent = Math.round(zoom * 100)
  const changeZoom = (delta: number) => setZoom(value => Math.min(5, Math.max(0.1, Number((value + delta).toFixed(2)))))

  return (
    <div className="image-viewer-shell">
      <div className="image-viewer-toolbar">
        <div>
          <strong>이미지 미리보기</strong>
          <span>{filePath}</span>
        </div>
        <div className="image-viewer-actions">
          {naturalSize.width > 0 && naturalSize.height > 0 && (
            <small>{naturalSize.width} × {naturalSize.height}px</small>
          )}
          <button type="button" onClick={() => changeZoom(-0.1)} disabled={zoom <= 0.1} title="축소">−</button>
          <button type="button" onClick={() => setZoom(1)} title="원본 배율">{zoomPercent}%</button>
          <button type="button" onClick={() => changeZoom(0.1)} disabled={zoom >= 5} title="확대">＋</button>
          <button type="button" onClick={() => setZoom(1)} title="배율 초기화">↺</button>
        </div>
      </div>
      {previewLoading ? (
        <div className="presentation-viewer-message">
          <strong>이미지 불러오는 중...</strong>
          <span>프로젝트 이미지를 Backend에서 인증 후 읽고 있습니다.</span>
        </div>
      ) : previewError ? (
        <div className="presentation-viewer-message error">
          <strong>이미지 파일을 열 수 없습니다.</strong>
          <span>{previewError}</span>
          <small>파일 형식과 프로젝트 경로 등록 상태를 확인해 주세요.</small>
        </div>
      ) : (
        <div className="image-viewer-canvas">
          <img
            key={`${filePath}:${revision}:${previewUrl}`}
            src={previewUrl}
            alt={filePath || '프로젝트 이미지'}
            decoding="async"
            draggable={false}
            style={{ width: naturalSize.width ? `${naturalSize.width * zoom}px` : 'auto' }}
            onLoad={event => {
              setNaturalSize({
                width: event.currentTarget.naturalWidth || 0,
                height: event.currentTarget.naturalHeight || 0,
              })
            }}
          />
        </div>
      )}
    </div>
  )
}

'''
    text = text.replace(insertion_marker, image_viewer + insertion_marker, 1)
viewer.write_text(text, encoding='utf-8')

# ---------- frontend/src/App.jsx ----------
app = Path('frontend/src/App.jsx')
text = app.read_text(encoding='utf-8')
text = text.replace(
    "import { PdfViewer, PresentationViewer } from './components/viewers/DocumentViewers'",
    "import { ImageViewer, PdfViewer, PresentationViewer } from './components/viewers/DocumentViewers'",
    1,
)
old_utils = "isDatabaseDiagramFile, isNotebookFile, isPdfFile, isPresentationFile"
new_utils = "isDatabaseDiagramFile, isImageFile, isNotebookFile, isPdfFile, isPresentationFile"
if old_utils in text and 'isImageFile, isNotebookFile' not in text:
    text = text.replace(old_utils, new_utils, 1)

# Insert an ImageViewer branch immediately before every real PdfViewer branch.
# Copy the existing PdfViewer props so root/path/revision semantics stay identical
# for primary and split editor panes without duplicating App-specific variable names.
pattern = re.compile(r"isPdfFile\(([^()]+)\)\s*\?\s*(<PdfViewer\b[\s\S]*?\s/>)")

def add_image_branch(match: re.Match) -> str:
    path_expr = match.group(1)
    pdf_tag = match.group(2)
    image_tag = pdf_tag.replace('<PdfViewer', '<ImageViewer', 1)
    return f"isImageFile({path_expr}) ? {image_tag} : isPdfFile({path_expr}) ? {pdf_tag}"

if 'isImageFile(' not in text[text.find('function IDE()'):]:
    text, count = pattern.subn(add_image_branch, text)
    if count < 1:
        raise SystemExit('App PdfViewer render branch not found')

text = text.replace("const AGENTSTUDIO_FRONTEND_VERSION='5.486'", "const AGENTSTUDIO_FRONTEND_VERSION='5.487'", 1)
app.write_text(text, encoding='utf-8')

# ---------- frontend/src/styles.css ----------
styles = Path('frontend/src/styles.css')
css = styles.read_text(encoding='utf-8')
if '/* v5.487 Project image viewer */' not in css:
    css += r'''

/* v5.487 Project image viewer */
.image-viewer-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #0b1117;
}

.image-viewer-toolbar {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 12px;
  border-bottom: 1px solid rgba(124, 158, 185, 0.2);
  background: #111a23;
}

.image-viewer-toolbar > div:first-child {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.image-viewer-toolbar strong {
  flex: 0 0 auto;
}

.image-viewer-toolbar span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #aebdca;
}

.image-viewer-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 5px;
}

.image-viewer-actions small {
  margin-right: 5px;
  color: #8fa3b5;
}

.image-viewer-actions button {
  min-width: 30px;
  height: 28px;
}

.image-viewer-canvas {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px;
  background-color: #0a0f14;
  background-image:
    linear-gradient(45deg, rgba(255,255,255,0.025) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(255,255,255,0.025) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.025) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.025) 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
}

.image-viewer-canvas img {
  display: block;
  max-width: none;
  height: auto;
  object-fit: contain;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.35);
  user-select: none;
}
'''
styles.write_text(css, encoding='utf-8')

# ---------- backend/app/api/routes.py ----------
routes = Path('backend/app/api/routes.py')
text = routes.read_text(encoding='utf-8')
if 'import mimetypes\n' not in text:
    text = text.replace('import asyncio\nimport json\n', 'import asyncio\nimport json\nimport mimetypes\n', 1)

image_suffix_decl = '''\n_PROJECT_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".avif"}\n\n'''
if '_PROJECT_IMAGE_SUFFIXES' not in text:
    text = text.replace('router = APIRouter()\n', 'router = APIRouter()\n' + image_suffix_decl, 1)

# Guard project-relative text readers against raster binary files.
pdf_guard = '''    if target.suffix.casefold() == ".pdf":\n        raise HTTPException(\n            status_code=415,\n            detail={\n                "code": "PDF_BINARY_VIEWER_REQUIRED",\n'''
image_guard = '''    if target.suffix.casefold() in _PROJECT_IMAGE_SUFFIXES:\n        raise HTTPException(\n            status_code=415,\n            detail={\n                "code": "IMAGE_BINARY_VIEWER_REQUIRED",\n                "message": "이미지는 텍스트 파일이 아닙니다. /api/files/image Viewer를 사용하세요.",\n            },\n        )\n'''
if text.count('"IMAGE_BINARY_VIEWER_REQUIRED"') < 2:
    positions = []
    start = 0
    while True:
        idx = text.find(pdf_guard, start)
        if idx < 0:
            break
        positions.append(idx)
        start = idx + len(pdf_guard)
    # Only /files/read and /files/content have this exact project-relative guard.
    # Insert before their PDF guards. Avoid touching unrelated route bodies if more occur.
    inserted = 0
    offset = 0
    for idx in positions:
        adjusted = idx + offset
        # Nearby route name must be project_file_read or project_file_content.
        context = text[max(0, adjusted - 1400):adjusted]
        if 'def project_file_read' not in context and 'def project_file_content' not in context:
            continue
        text = text[:adjusted] + image_guard + text[adjusted:]
        offset += len(image_guard)
        inserted += 1
    if inserted < 2:
        raise SystemExit(f'expected 2 project text image guards, inserted {inserted}')

image_endpoint_marker = '@router.get("/files/pdf")\nasync def project_pdf_view'
if '@router.get("/files/image")' not in text:
    marker_index = text.find(image_endpoint_marker)
    if marker_index < 0:
        raise SystemExit('PDF endpoint marker not found')
    image_endpoint = r'''@router.get("/files/image")
async def project_image_view(root: str = Query(...), relative_path: str = Query(...)):
    """등록 프로젝트 안의 이미지 파일을 인증된 inline binary 응답으로 전송합니다."""
    project_root = Path(str(root or "")).expanduser().resolve()
    relative = str(relative_path or "").strip()
    if not relative:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")

    try:
        await get_file_meta(str(project_root), relative)
    except PermissionError as exc:
        restored = await ensure_persisted_project_root(str(project_root))
        if not restored.get("registered"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PROJECT_ROOT_NOT_ALLOWED",
                    "message": str(exc),
                    "project_root": str(project_root),
                    "recovery": restored,
                },
            ) from exc
        await get_file_meta(str(project_root), relative)

    target = (project_root / Path(relative.replace("\\", "/"))).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="프로젝트 밖의 이미지는 열 수 없습니다.") from exc

    suffix = target.suffix.casefold()
    if suffix not in _PROJECT_IMAGE_SUFFIXES:
        raise HTTPException(status_code=415, detail="지원하는 이미지 형식이 아닙니다.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"이미지 파일을 찾을 수 없습니다: {target}")

    media_type = mimetypes.guess_type(target.name)[0] or {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
        ".avif": "image/avif",
    }.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(target),
        media_type=media_type,
        filename=target.name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


'''
    text = text[:marker_index] + image_endpoint + text[marker_index:]

text = text.replace('return {"ok": True, "name": "THEANOVA AgentStudio", "version": "5.483",', 'return {"ok": True, "name": "THEANOVA AgentStudio", "version": "5.487",', 1)
routes.write_text(text, encoding='utf-8')

# ---------- backend/app/services/python_execution_service.py ----------
worker = Path('backend/app/services/python_execution_service.py')
text = worker.read_text(encoding='utf-8')
old = '''                          result = _agentstudio_execute_compiled(expression_compiled, namespace)\n                          if result is not None:\n                              print(repr(result))\n'''
new = '''                          result = _agentstudio_execute_compiled(expression_compiled, namespace)\n                          if result is not None:\n                              if notebook_mode:\n                                  rich_data, rich_metadata = _agentstudio_notebook_mime_bundle(result)\n                                  _agentstudio_emit_notebook_event({\n                                      "event": "display_data",\n                                      "output": {\n                                          "output_type": "execute_result",\n                                          "data": rich_data,\n                                          "metadata": rich_metadata,\n                                      },\n                                  })\n                              else:\n                                  print(repr(result))\n'''
if '_agentstudio_notebook_mime_bundle(result)' not in text:
    if old not in text:
        raise SystemExit('last-expression repr marker not found')
    text = text.replace(old, new, 1)
worker.write_text(text, encoding='utf-8')

print('v5.487 patch applied')
