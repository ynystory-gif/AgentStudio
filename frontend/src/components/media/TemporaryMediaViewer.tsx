import React, { useMemo } from 'react'

type Props = {
  url: string
  title?: string
  onClose?: () => void
}

function youtubeVideoId(rawUrl: string): string {
  const value = String(rawUrl || '').trim()
  if (!value) return ''
  try {
    const parsed = new URL(value)
    const host = parsed.hostname.replace(/^www\./, '').toLowerCase()
    if (host === 'youtu.be') return parsed.pathname.split('/').filter(Boolean)[0] || ''
    if (host.endsWith('youtube.com')) {
      if (parsed.pathname === '/watch') return parsed.searchParams.get('v') || ''
      const parts = parsed.pathname.split('/').filter(Boolean)
      if (parts[0] === 'shorts' || parts[0] === 'embed' || parts[0] === 'live') return parts[1] || ''
    }
  } catch {
    return ''
  }
  return ''
}

function directVideoUrl(rawUrl: string): boolean {
  return /\.(mp4|webm|ogg|mov)(?:[?#].*)?$/i.test(String(rawUrl || '').trim())
}

export function TemporaryMediaViewer({ url, title = '외부 미디어', onClose }: Props) {
  const youtubeId = useMemo(() => youtubeVideoId(url), [url])
  const isDirectVideo = useMemo(() => directVideoUrl(url), [url])
  const embedUrl = youtubeId ? `https://www.youtube.com/embed/${encodeURIComponent(youtubeId)}?rel=0` : ''

  return (
    <div className="temporary-media-viewer">
      <div className="temporary-media-viewer-head">
        <div>
          <strong>▶ {title}</strong>
          <small>임시 미디어 탭 · 프로젝트 파일은 생성하지 않습니다.</small>
        </div>
        <div>
          <a href={url} target="_blank" rel="noreferrer">브라우저에서 열기</a>
          {onClose && <button type="button" onClick={onClose}>×</button>}
        </div>
      </div>
      <div className="temporary-media-viewer-body">
        {youtubeId ? (
          <iframe
            src={embedUrl}
            title={title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        ) : isDirectVideo ? (
          <video src={url} controls playsInline />
        ) : (
          <div className="temporary-media-viewer-unsupported">
            <strong>이 URL은 직접 영상 재생 형식으로 확인되지 않았습니다.</strong>
            <p>YouTube URL 또는 mp4/webm/ogg 직접 영상 URL을 입력하세요.</p>
            <a href={url} target="_blank" rel="noreferrer">외부 브라우저에서 열기</a>
          </div>
        )}
      </div>
      <div className="temporary-media-viewer-foot">
        <span>영상 재생과 녹음 세션은 분리되어 있어 코드/Workflow 화면으로 이동해도 녹음은 계속됩니다.</span>
        <span>YouTube 음성을 STT로 받으려면 메모 → 실시간 기록 → 화면/시스템 오디오 → 녹음 시작 후 Chrome 탭을 선택하고 “탭 오디오 공유”를 켜세요. 오디오 Track이 없으면 종료 후 보정에서도 텍스트가 생성되지 않습니다.</span>
      </div>
    </div>
  )
}
