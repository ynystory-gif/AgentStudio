import React, { type ReactNode } from 'react'
import type { NotebookAttachments, NotebookOutputData } from '../../types/notebook'
import './NotebookOutputStatus.css'

export interface NotebookMarkdownProps {
  text?: string | null
  attachments?: NotebookAttachments
}

export interface NotebookOutputProps {
  output?: NotebookOutputData | null
}

export function notebookSourceToText(source: unknown): string {
  if (Array.isArray(source)) return source.join('')
  return String(source ?? '')
}

function notebookAttachmentDataUrl(attachments: NotebookAttachments, name: string): string {
  const key = decodeURIComponent(String(name || '').replace(/^attachment:/i, ''))
  const item = attachments && typeof attachments === 'object' ? attachments[key] : null
  if (!item || typeof item !== 'object') return ''

  const preferred = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml']
  const mime = preferred.find(type => item[type] !== undefined)
    || Object.keys(item).find(type => String(type).startsWith('image/'))

  if (!mime) return ''
  const raw = notebookSourceToText(item[mime])
  if (!raw) return ''

  if (mime === 'image/svg+xml') {
    const trimmed = raw.trim()
    if (trimmed.startsWith('<svg') || trimmed.startsWith('<?xml')) {
      return `data:${mime};charset=utf-8,${encodeURIComponent(raw)}`
    }
  }

  return `data:${mime};base64,${raw.replace(/\s/g, '')}`
}

interface NotebookInlineImageProps {
  src: string
  alt?: string
  title?: string
  sourceLabel?: string
}

function decodeNotebookHtmlAttribute(value: string): string {
  return String(value || '')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
}

function NotebookInlineImage({ src, alt = '', title = '', sourceLabel = '' }: NotebookInlineImageProps) {
  const [failed, setFailed] = React.useState(false)
  if (failed) {
    return (
      <span className="notebook-attachment-missing notebook-remote-image-failed" title={src}>
        ⚠ 이미지를 불러오지 못했습니다.{' '}
        <a href={src} target="_blank" rel="noreferrer">
          {sourceLabel || alt || '이미지 URL 열기'}
        </a>
      </span>
    )
  }
  return (
    <img
      className="notebook-markdown-inline-image"
      alt={alt || 'Notebook image'}
      title={title || undefined}
      src={src}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  )
}

function notebookSafeImageSource(rawSource: string, attachments: NotebookAttachments): string {
  const source = decodeNotebookHtmlAttribute(String(rawSource || '').trim())
  if (!source) return ''
  if (/^attachment:/i.test(source)) return notebookAttachmentDataUrl(attachments, source)
  if (/^https?:\/\//i.test(source)) return source

  // Jupyter/Markdown generators may embed images directly as data URIs.
  // Some notebooks wrap the very long base64 payload across source lines, and
  // NotebookMarkdown joins those lines with spaces before inline rendering.
  // Normalize whitespace only for a whitelisted image data URI instead of
  // rejecting it or rendering the raw base64 text into the notebook.
  const dataImage = source.match(
    /^(data:image\/(?:png|jpe?g|gif|webp|svg\+xml);(?:base64|charset=utf-8),)([\s\S]*)$/i,
  )
  if (dataImage) {
    const prefix = dataImage[1] || ''
    const payload = dataImage[2] || ''
    return `${prefix}${payload.replace(/\s/g, '')}`
  }
  return ''
}

function parseNotebookHtmlImageTag(
  value: string,
  attachments: NotebookAttachments,
): { src: string; alt: string; title: string } | null {
  if (!/^<img\b[^>]*\/?>$/i.test(value.trim())) return null
  const attributes: Record<string, string> = {}
  const body = value.trim().replace(/^<img\b/i, '').replace(/\/?>$/, '')
  const attrPattern = /([a-zA-Z_:][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/g
  let match: RegExpExecArray | null
  while ((match = attrPattern.exec(body))) {
    attributes[String(match[1] || '').toLowerCase()] = decodeNotebookHtmlAttribute(match[2] ?? match[3] ?? match[4] ?? '')
  }
  const src = notebookSafeImageSource(attributes.src || '', attachments)
  if (!src) return null
  return {
    src,
    alt: attributes.alt || '',
    title: attributes.title || '',
  }
}

function renderNotebookInline(
  text: unknown,
  keyPrefix = 'inline',
  attachments: NotebookAttachments = {},
): ReactNode[] {
  const source = String(text ?? '')
  // Notebook Markdown commonly contains raw HTML <img> tags. Render only a
  // tightly-whitelisted image tag here; arbitrary raw HTML remains escaped.
  const token = /(<img\b[^>]*\/?>|!\[[^\]]*\]\s*\((?:attachment:[^)]+|https?:\/\/[^)\s]+|data:image\/(?:png|jpe?g|gif|webp|svg\+xml);(?:base64|charset=utf-8),[^)]*)\)|`[^`]*`|\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/gi
  const nodes: ReactNode[] = []
  let last = 0
  let match: RegExpExecArray | null
  let index = 0

  while ((match = token.exec(source))) {
    if (match.index > last) nodes.push(source.slice(last, match.index))
    const value = match[0]
    const key = `${keyPrefix}-${index++}`

    if (/^<img\b/i.test(value)) {
      const image = parseNotebookHtmlImageTag(value, attachments)
      if (image) {
        nodes.push(
          <NotebookInlineImage
            key={key}
            src={image.src}
            alt={image.alt}
            title={image.title}
            sourceLabel={image.alt}
          />,
        )
      } else {
        // Unsupported/unsafe raw HTML remains visible as text instead of being
        // injected into the DOM.
        nodes.push(value)
      }
    } else if (value.startsWith('![')) {
      const image = value.match(
        /^!\[([^\]]*)\]\s*\((attachment:[^)]+|https?:\/\/[^)\s]+|data:image\/(?:png|jpe?g|gif|webp|svg\+xml);(?:base64|charset=utf-8),[^)]*)\)$/i,
      )
      if (image) {
        const target = image[2] ?? ''
        const src = notebookSafeImageSource(target, attachments)
        if (src) {
          nodes.push(
            <NotebookInlineImage
              key={key}
              src={src}
              alt={image[1] || 'Notebook attachment'}
              sourceLabel={image[1] || target}
            />,
          )
        } else {
          nodes.push(
            <span key={key} className="notebook-attachment-missing" title={target}>
              ⚠ 첨부 이미지를 찾을 수 없습니다: {image[1] || target}
            </span>,
          )
        }
      } else {
        nodes.push(value)
      }
    } else if (value.startsWith('`')) {
      nodes.push(<code key={key}>{value.slice(1, -1)}</code>)
    } else if (value.startsWith('**')) {
      nodes.push(<strong key={key}>{value.slice(2, -2)}</strong>)
    } else if (value.startsWith('[')) {
      const link = value.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/)
      if (link) {
        nodes.push(
          <a key={key} href={link[2]} target="_blank" rel="noreferrer">
            {link[1]}
          </a>,
        )
      } else {
        nodes.push(value)
      }
    } else {
      nodes.push(value)
    }

    last = match.index + value.length
  }

  if (last < source.length) nodes.push(source.slice(last))
  return nodes
}

export function NotebookMarkdown({ text, attachments = {} }: NotebookMarkdownProps) {
  const lines = String(text || '').replace(/\r\n|\r/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let i = 0
  let blockKey = 0

  const isBlockStart = (line: string, index: number): boolean => {
    const trimmed = line.trim()
    if (!trimmed) return true
    if (/^```/.test(trimmed)) return true
    if (/^#{1,6}\s+/.test(trimmed)) return true
    if (/^>\s?/.test(trimmed)) return true
    if (/^[-*+]\s+/.test(trimmed)) return true
    if (/^\d+[.)]\s+/.test(trimmed)) return true
    if (/^([-*_])(?:\s*\1){2,}\s*$/.test(trimmed)) return true
    const next = lines[index + 1] || ''
    if (trimmed.includes('|') && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(next)) return true
    return false
  }

  while (i < lines.length) {
    const raw = lines[i] ?? ''
    const trimmed = raw.trim()
    if (!trimmed) {
      i += 1
      continue
    }

    const fence = trimmed.match(/^```\s*([^\s`]*)/)
    if (fence) {
      const language = fence[1] || ''
      const codeLines: string[] = []
      i += 1
      while (i < lines.length && !/^```/.test((lines[i] ?? '').trim())) {
        codeLines.push(lines[i] ?? '')
        i += 1
      }
      if (i < lines.length) i += 1
      blocks.push(
        <pre className="notebook-markdown-code" key={`md-${blockKey++}`}>
          <code data-language={language}>{codeLines.join('\n')}</code>
        </pre>,
      )
      continue
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      const level = Math.min(6, heading[1]?.length || 1)
      const key = `md-${blockKey++}`
      const content = renderNotebookInline(heading[2] || '', `h-${blockKey}`, attachments)
      const headingNode = level === 1 ? <h1 key={key}>{content}</h1>
        : level === 2 ? <h2 key={key}>{content}</h2>
          : level === 3 ? <h3 key={key}>{content}</h3>
            : level === 4 ? <h4 key={key}>{content}</h4>
              : level === 5 ? <h5 key={key}>{content}</h5>
                : <h6 key={key}>{content}</h6>
      blocks.push(headingNode)
      i += 1
      continue
    }

    if (trimmed.includes('|') && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i + 1] || '')) {
      const splitRow = (line: string): string[] => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim())
      const headers = splitRow(raw)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && (lines[i] ?? '').trim() && (lines[i] ?? '').includes('|')) {
        rows.push(splitRow(lines[i] ?? ''))
        i += 1
      }
      blocks.push(
        <div className="notebook-markdown-table-wrap" key={`md-${blockKey++}`}>
          <table className="notebook-markdown-table">
            <thead>
              <tr>
                {headers.map((cell, idx) => (
                  <th key={idx}>{renderNotebookInline(cell, `th-${blockKey}-${idx}`, attachments)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {headers.map((_, cellIndex) => (
                    <td key={cellIndex}>
                      {renderNotebookInline(row[cellIndex] || '', `td-${blockKey}-${rowIndex}-${cellIndex}`, attachments)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    if (/^>\s?/.test(trimmed)) {
      const quote: string[] = []
      while (i < lines.length && /^\s*>\s?/.test(lines[i] ?? '')) {
        quote.push((lines[i] ?? '').replace(/^\s*>\s?/, ''))
        i += 1
      }
      blocks.push(
        <blockquote key={`md-${blockKey++}`}>
          {quote.map((line, idx) => (
            <React.Fragment key={idx}>
              {renderNotebookInline(line, `q-${blockKey}-${idx}`, attachments)}
              {idx < quote.length - 1 && <br />}
            </React.Fragment>
          ))}
        </blockquote>,
      )
      continue
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i] ?? '')) {
        items.push((lines[i] ?? '').replace(/^\s*[-*+]\s+/, ''))
        i += 1
      }
      blocks.push(
        <ul key={`md-${blockKey++}`}>
          {items.map((item, idx) => (
            <li key={idx}>{renderNotebookInline(item, `ul-${blockKey}-${idx}`, attachments)}</li>
          ))}
        </ul>,
      )
      continue
    }

    if (/^\d+[.)]\s+/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i] ?? '')) {
        items.push((lines[i] ?? '').replace(/^\s*\d+[.)]\s+/, ''))
        i += 1
      }
      blocks.push(
        <ol key={`md-${blockKey++}`}>
          {items.map((item, idx) => (
            <li key={idx}>{renderNotebookInline(item, `ol-${blockKey}-${idx}`, attachments)}</li>
          ))}
        </ol>,
      )
      continue
    }

    if (/^([-*_])(?:\s*\1){2,}\s*$/.test(trimmed)) {
      blocks.push(<hr key={`md-${blockKey++}`} />)
      i += 1
      continue
    }

    const paragraph = [trimmed]
    i += 1
    while (i < lines.length && (lines[i] ?? '').trim() && !isBlockStart(lines[i] ?? '', i)) {
      paragraph.push((lines[i] ?? '').trim())
      i += 1
    }
    blocks.push(
      <p key={`md-${blockKey++}`}>
        {renderNotebookInline(paragraph.join(' '), `p-${blockKey}`, attachments)}
      </p>,
    )
  }

  return <div className="notebook-markdown-rendered">{blocks}</div>
}

interface SmoothNotebookOutputImageProps {
  src: string
}

function SmoothNotebookOutputImage({ src }: SmoothNotebookOutputImageProps) {
  const [displaySrc, setDisplaySrc] = React.useState(src)

  React.useEffect(() => {
    if (!src || src === displaySrc) return

    let cancelled = false
    const loader = new Image()
    loader.decoding = 'async'

    const commit = async () => {
      try {
        if (typeof loader.decode === 'function') await loader.decode()
      } catch {
        // onload already confirms the image is usable; decode() is optional.
      }
      if (!cancelled) setDisplaySrc(src)
    }

    loader.onload = () => { void commit() }
    loader.onerror = () => {
      // Preserve normal browser error behavior, but never blank the old frame
      // while a new streaming image is still loading.
      if (!cancelled) setDisplaySrc(src)
    }
    loader.src = src

    return () => {
      cancelled = true
      loader.onload = null
      loader.onerror = null
    }
  }, [src, displaySrc])

  return (
    <img
      alt="Notebook output"
      src={displaySrc}
      decoding="async"
      className="notebook-output-rich-image"
    />
  )
}

const NOTEBOOK_WARNING_TYPE_PATTERN = /\b(?:DeprecationWarning|PendingDeprecationWarning|FutureWarning|UserWarning|RuntimeWarning|SyntaxWarning|ResourceWarning|ImportWarning|UnicodeWarning|BytesWarning|EncodingWarning)\b/g
const NOTEBOOK_WARNING_TYPE_TEST = /\b(?:DeprecationWarning|PendingDeprecationWarning|FutureWarning|UserWarning|RuntimeWarning|SyntaxWarning|ResourceWarning|ImportWarning|UnicodeWarning|BytesWarning|EncodingWarning)\b/

function notebookWarningInfo(text: string): { count: number; types: string[] } | null {
  const source = String(text || '')
  const matches = Array.from(source.matchAll(NOTEBOOK_WARNING_TYPE_PATTERN))
  if (!matches.length || !NOTEBOOK_WARNING_TYPE_TEST.test(source)) return null
  const types = Array.from(new Set(matches.map(match => String(match[0] || '').trim()).filter(Boolean)))
  return { count: Math.max(1, matches.length), types }
}

function NotebookWarningOutput({ text }: { text: string }) {
  const info = notebookWarningInfo(text)
  if (!info) return <pre className="notebook-output-stream stderr">{text}</pre>
  const countLabel = `경고 ${info.count}개`
  const typeLabel = info.types.length ? info.types.join(', ') : 'Python Warning'
  return (
    <details className="notebook-output-warning">
      <summary>
        <span className="notebook-output-warning-title">⚠ {countLabel}</span>
        <span className="notebook-output-warning-type">{typeLabel}</span>
        <span className="notebook-output-warning-action">자세히 보기</span>
      </summary>
      <pre className="notebook-output-stream warning">{text}</pre>
    </details>
  )
}

export function NotebookOutput({ output }: NotebookOutputProps) {
  if (!output) return null
  const outputType = String(output.output_type || '')

  if (outputType === 'stream') {
    const streamText = notebookSourceToText(output.text)
    if (output.name === 'stderr') {
      // v5.490: Python warnings are successful execution diagnostics, not failures.
      // Keep actual output_type='error' exceptions red while warnings are shown
      // as a compact yellow disclosure and ordinary stderr stays neutral.
      return <NotebookWarningOutput text={streamText} />
    }
    return <pre className="notebook-output-stream">{streamText}</pre>
  }

  if (outputType === 'error') {
    const trace = Array.isArray(output.traceback)
      ? output.traceback.join('\n')
      : String(output.traceback || '')
    const fallback = `${output.ename || 'Error'}${output.evalue ? `: ${String(output.evalue)}` : ''}`
    return <pre className="notebook-output-stream error">{trace || fallback}</pre>
  }

  if (outputType === 'display_data' || outputType === 'execute_result') {
    const data = output.data || {}
    const image = notebookSourceToText(data['image/png'])
    if (image) {
      const imageSrc = `data:image/png;base64,${image.replace(/\s/g, '')}`
      return (
        <div className="notebook-output-rich">
          <SmoothNotebookOutputImage src={imageSrc} />
        </div>
      )
    }

    const plain = notebookSourceToText(
      data['text/plain'] || data['application/json'] || data['text/markdown'] || data['text/html'],
    )
    return plain ? <pre className="notebook-output-stream">{plain}</pre> : null
  }

  return <pre className="notebook-output-stream">{JSON.stringify(output, null, 2)}</pre>
}
