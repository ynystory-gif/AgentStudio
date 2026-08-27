import { useEffect, useState } from 'react'
import { AgentStudioApiError, api, runtimeInfo } from '../../api'

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

export function PdfViewer({
  filePath = '',
  projectRoot = '',
  revision = 0,
  page = 0,
  searchQuery = '',
  navigationToken = 0,
  matchSnippet = '',
}: BinaryViewerProps) {
  const apiBase = runtimeInfo().apiBase
  const baseSrc = `${apiBase}/files/pdf?root=${encodeURIComponent(projectRoot)}&relative_path=${encodeURIComponent(filePath)}&v=${encodeURIComponent(String(revision))}`
  // When a Unified Find result is clicked, the page number is authoritative.
  // Passing #search together with #page lets Chromium's native PDF viewer run a
  // document-wide search and it can override the requested page, making every
  // result appear to jump to the same occurrence. Keep navigation page-only.
  const targetPage = Number(page) > 0 ? Math.max(1, Math.trunc(Number(page))) : 0
  const fragment = targetPage > 0
    ? `page=${targetPage}`
    : (String(searchQuery || '').trim() ? `search=${encodeURIComponent(String(searchQuery || '').trim())}` : '')
  const src = fragment ? `${baseSrc}#${fragment}` : baseSrc
  const displayMatchSnippet = String(matchSnippet || '').replace(/\s+/g, ' ').trim().slice(0, 180)

  return (
    <div className="pdf-viewer-shell">
      <div className="pdf-viewer-toolbar">
        <div>
          <strong>PDF 미리보기</strong>
          <span>{filePath}</span>
        </div>
        <small>
          {targetPage > 0
            ? `통합 찾기 결과 · 페이지 ${targetPage}${displayMatchSnippet ? ` · ${displayMatchSnippet}` : ''}`
            : 'PDF는 바이너리 파일이므로 코드 편집기 대신 브라우저 PDF Viewer로 표시됩니다.'}
        </small>
      </div>
      <iframe
        key={`${filePath}:${revision}:${page}:${searchQuery}:${navigationToken}`}
        className="pdf-viewer-frame"
        src={src}
        title={`PDF 미리보기 - ${filePath || '문서'}`}
      />
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
  const apiBase = runtimeInfo().apiBase
  const [previewState, setPreviewState] = useState<PresentationPreviewState>(initialPresentationPreviewState)
  const [refreshNonce, setRefreshNonce] = useState(0)

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
    }).then(result => {
      if (cancelled) return
      setPreviewState({
        loading: false,
        error: '',
        converter: result?.converter || '',
        cacheHit: Boolean(result?.cache_hit),
        sourceSha256: result?.source_sha256 || '',
        attempts: [],
      })
    }).catch(error => {
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

  const src = previewState.error || previewState.loading
    ? ''
    : `${apiBase}/files/presentation/pdf?root=${encodeURIComponent(projectRoot)}&relative_path=${encodeURIComponent(filePath)}&v=${encodeURIComponent(`${revision}:${previewState.sourceSha256}`)}`

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
            onClick={() => setRefreshNonce(value => value + 1)}
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
              {previewState.attempts.map((attempt, index) => (
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
      ) : (
        <iframe
          key={`${filePath}:${revision}:${previewState.sourceSha256}`}
          className="pdf-viewer-frame"
          src={src}
          title={`PowerPoint 미리보기 - ${filePath || '프레젠테이션'}`}
        />
      )}
    </div>
  )
}
