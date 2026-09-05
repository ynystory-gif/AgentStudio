import { useEffect, useState } from 'react'
import { AgentStudioApiError, api, apiFetch } from '../../../api'

export interface BinaryViewerProps {
  filePath?: string
  projectRoot?: string
  revision?: number | string
  page?: number
  searchQuery?: string
  navigationToken?: number | string
  matchSnippet?: string
}

interface PresentationAttempt {
  converter?: string
  reason?: string
  output?: unknown
}

interface PresentationPrepareResponse {
  converter?: string
  cache_hit?: boolean
  source_sha256?: string
}

interface PresentationErrorDetail {
  message?: unknown
  attempts?: PresentationAttempt[]
}

interface PresentationErrorPayload {
  detail?: string | PresentationErrorDetail
}

interface PresentationPreviewState {
  loading: boolean
  error: string
  converter: string
  cacheHit: boolean
  sourceSha256: string
  attempts: PresentationAttempt[]
}

const initialPresentationPreviewState = (): PresentationPreviewState => ({
  loading: true,
  error: '',
  converter: '',
  cacheHit: false,
  sourceSha256: '',
  attempts: [],
})

export function ImageViewer({ filePath = '', projectRoot = '', revision = 0 }: BinaryViewerProps) {
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
      .then((response: LegacyValue) => response.blob())
      .then((blob: LegacyValue) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setPreviewUrl(objectUrl)
        setPreviewLoading(false)
      })
      .catch((error: LegacyValue) => {
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
  const changeZoom = (delta: number) => setZoom((value: LegacyValue) => Math.min(5, Math.max(0.1, Number((value + delta).toFixed(2)))))

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
            onLoad={(event: LegacyValue) => {
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

export function PdfViewer({
  filePath = '',
  projectRoot = '',
  revision = 0,
  page = 0,
  searchQuery = '',
  navigationToken = 0,
  matchSnippet = '',
}: BinaryViewerProps) {
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [previewLoading, setPreviewLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let objectUrl = ''
    setPreviewLoading(true)
    setPreviewError('')
    setPreviewUrl('')

    const params = new URLSearchParams({
      root: String(projectRoot || ''),
      relative_path: String(filePath || ''),
      v: String(revision),
    })

    // v5.438: PDF iframe navigation cannot attach the AgentStudio Bearer token.
    // Fetch the PDF through apiFetch (Authorization included), then give Chromium
    // a local blob URL. This keeps the PDF endpoint protected and avoids the
    // {"detail":"로그인이 필요합니다."} payload appearing inside the viewer.
    apiFetch(`/files/pdf?${params.toString()}`)
      .then((response: LegacyValue) => response.blob())
      .then((blob: LegacyValue) => {
        if (cancelled) return
        const pdfBlob = blob.type === 'application/pdf'
          ? blob
          : new Blob([blob], { type: 'application/pdf' })
        objectUrl = URL.createObjectURL(pdfBlob)
        setPreviewUrl(objectUrl)
        setPreviewLoading(false)
      })
      .catch((error: LegacyValue) => {
        if (cancelled) return
        setPreviewLoading(false)
        setPreviewError(error instanceof Error ? error.message : String(error || 'PDF 미리보기를 불러오지 못했습니다.'))
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [filePath, projectRoot, revision])

  // When a Unified Find result is clicked, the page number is authoritative.
  // Passing #search together with #page lets Chromium's native PDF viewer run a
  // document-wide search and it can override the requested page, making every
  // result appear to jump to the same occurrence. Keep navigation page-only.
  const targetPage = Number(page) > 0 ? Math.max(1, Math.trunc(Number(page))) : 0
  const fragment = targetPage > 0
    ? `page=${targetPage}`
    : (String(searchQuery || '').trim() ? `search=${encodeURIComponent(String(searchQuery || '').trim())}` : '')
  const src = previewUrl && fragment ? `${previewUrl}#${fragment}` : previewUrl
  const displayMatchSnippet = String(matchSnippet || '').replace(/\s+/g, ' ').trim().slice(0, 180)

  return (
    <div className="pdf-viewer-shell">
      <div className="pdf-viewer-toolbar">
        <div>
          <span>{filePath}</span>
        </div>
        <small>
          {targetPage > 0
            ? `통합 찾기 결과 · 페이지 ${targetPage}${displayMatchSnippet ? ` · ${displayMatchSnippet}` : ''}`
            : 'PDF는 인증된 Backend에서 읽어 브라우저 PDF Viewer로 안전하게 표시됩니다.'}
        </small>
      </div>
      {previewLoading ? (
        <div className="presentation-viewer-message">
          <strong>PDF 미리보기 불러오는 중...</strong>
          <span>프로젝트 PDF를 Backend에서 인증 후 읽고 있습니다.</span>
        </div>
      ) : previewError ? (
        <div className="presentation-viewer-message error">
          <strong>PDF 파일을 열 수 없습니다.</strong>
          <span>{previewError}</span>
          <small>Backend 로그인 상태와 프로젝트 경로 등록 상태를 확인해 주세요.</small>
        </div>
      ) : (
        <iframe
          key={`${filePath}:${revision}:${page}:${searchQuery}:${navigationToken}:${previewUrl}`}
          className="pdf-viewer-frame"
          src={src}
          title={`PDF 미리보기 - ${filePath || '문서'}`}
        />
      )}
    </div>
  )
}

function readPresentationError(error: unknown): { message: string; attempts: PresentationAttempt[] } {
  let message = error instanceof Error ? error.message : 'PowerPoint 미리보기 생성에 실패했습니다.'
  let attempts: PresentationAttempt[] = []

  if (error instanceof AgentStudioApiError && error.responseBody) {
    try {
      const payload = JSON.parse(error.responseBody) as PresentationErrorPayload
      const detail = payload.detail
      if (typeof detail === 'string') {
        message = detail || message
      } else if (detail && typeof detail === 'object') {
        if (detail.message !== undefined) message = String(detail.message || message)
        if (Array.isArray(detail.attempts)) attempts = detail.attempts
      }
    } catch {
      // Keep the HTTP error message when the backend did not return JSON.
    }
  }

  return { message: String(message), attempts }
}

export function PresentationViewer({ filePath = '', projectRoot = '', revision = 0 }: BinaryViewerProps) {
  const [previewState, setPreviewState] = useState<PresentationPreviewState>(initialPresentationPreviewState)
  const [refreshNonce, setRefreshNonce] = useState(0)
  const [previewPdfUrl, setPreviewPdfUrl] = useState('')
  const [previewPdfError, setPreviewPdfError] = useState('')

  useEffect(() => {
    let cancelled = false
    setPreviewState(initialPresentationPreviewState())

    api<PresentationPrepareResponse>('/files/presentation/prepare', {
      method: 'POST',
      body: JSON.stringify({
        root: projectRoot,
        relative_path: filePath,
        force: refreshNonce > 0,
      }),
    }).then((result: LegacyValue) => {
      if (cancelled) return
      setPreviewState({
        loading: false,
        error: '',
        converter: result?.converter || '',
        cacheHit: Boolean(result?.cache_hit),
        sourceSha256: result?.source_sha256 || '',
        attempts: [],
      })
    }).catch((error: LegacyValue) => {
      if (cancelled) return
      const parsed = readPresentationError(error)
      setPreviewState({
        loading: false,
        error: parsed.message,
        converter: '',
        cacheHit: false,
        sourceSha256: '',
        attempts: parsed.attempts,
      })
    })

    return () => {
      cancelled = true
    }
  }, [filePath, projectRoot, revision, refreshNonce])

  useEffect(() => {
    if (previewState.error || previewState.loading) {
      setPreviewPdfUrl('')
      setPreviewPdfError('')
      return
    }

    let cancelled = false
    let objectUrl = ''
    setPreviewPdfUrl('')
    setPreviewPdfError('')
    const params = new URLSearchParams({
      root: String(projectRoot || ''),
      relative_path: String(filePath || ''),
      v: `${revision}:${previewState.sourceSha256}`,
    })

    // Same authenticated-blob bridge as PdfViewer. A plain iframe request does
    // not carry the Bearer token used by AgentStudio authentication.
    apiFetch(`/files/presentation/pdf?${params.toString()}`)
      .then((response: LegacyValue) => response.blob())
      .then((blob: LegacyValue) => {
        if (cancelled) return
        const pdfBlob = blob.type === 'application/pdf'
          ? blob
          : new Blob([blob], { type: 'application/pdf' })
        objectUrl = URL.createObjectURL(pdfBlob)
        setPreviewPdfUrl(objectUrl)
      })
      .catch((error: LegacyValue) => {
        if (cancelled) return
        setPreviewPdfError(error instanceof Error ? error.message : String(error || 'PowerPoint PDF 미리보기를 불러오지 못했습니다.'))
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [filePath, projectRoot, revision, previewState.error, previewState.loading, previewState.sourceSha256])

  const src = previewPdfUrl

  return (
    <div className="pdf-viewer-shell presentation-viewer-shell">
      <div className="pdf-viewer-toolbar presentation-viewer-toolbar">
        <div>
          <strong>PowerPoint 미리보기</strong>
          <span>{filePath}</span>
        </div>
        <div className="presentation-viewer-status">
          {previewState.converter && (
            <span>{previewState.converter}{previewState.cacheHit ? ' · 캐시' : ''}</span>
          )}
          <small>원본 PPT/PPTX는 수정하지 않고 PDF 미리보기만 생성합니다.</small>
          <button
            type="button"
            onClick={() => setRefreshNonce((value: LegacyValue) => value + 1)}
            disabled={previewState.loading}
          >
            ↻ 새로고침
          </button>
        </div>
      </div>

      {previewState.loading ? (
        <div className="presentation-viewer-message">
          <strong>PowerPoint 미리보기 생성 중...</strong>
          <span>Microsoft PowerPoint를 우선 사용하고, 사용할 수 없으면 LibreOffice로 변환합니다.</span>
        </div>
      ) : previewState.error ? (
        <div className="presentation-viewer-message error">
          <strong>PowerPoint 미리보기를 만들 수 없습니다.</strong>
          <span>{previewState.error}</span>
          {previewState.attempts.length > 0 && (
            <div className="presentation-viewer-attempts">
              {previewState.attempts.map((attempt: LegacyValue, index: LegacyValue) => (
                <div key={`${attempt.converter || 'converter'}:${index}`}>
                  <b>{attempt.converter || '변환기'}</b>
                  <em>{attempt.reason || '변환 실패'}</em>
                  {attempt.output !== undefined && attempt.output !== null && (
                    <code>{String(attempt.output).slice(-1200)}</code>
                  )}
                </div>
              ))}
            </div>
          )}
          <small>원본 파일은 변경되지 않습니다. PowerPoint가 설치되어 있는데도 실패하면 위 변환 단계의 오류를 확인하세요.</small>
        </div>
      ) : previewPdfError ? (
        <div className="presentation-viewer-message error">
          <strong>PowerPoint PDF 미리보기를 열 수 없습니다.</strong>
          <span>{previewPdfError}</span>
          <small>Backend 인증 상태를 확인한 뒤 새로고침해 주세요.</small>
        </div>
      ) : !src ? (
        <div className="presentation-viewer-message">
          <strong>PowerPoint PDF 미리보기 불러오는 중...</strong>
          <span>변환된 PDF를 Backend에서 인증 후 읽고 있습니다.</span>
        </div>
      ) : (
        <iframe
          key={`${filePath}:${revision}:${previewState.sourceSha256}:${previewPdfUrl}`}
          className="pdf-viewer-frame"
          src={src}
          title={`PowerPoint 미리보기 - ${filePath || '프레젠테이션'}`}
        />
      )}
    </div>
  )
}
