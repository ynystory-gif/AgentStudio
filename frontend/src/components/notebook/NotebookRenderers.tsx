import React, { type ReactNode } from 'react'
import type { NotebookAttachments, NotebookOutputData } from '../../types/notebook'

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

function renderNotebookInline(
  text: unknown,
  keyPrefix = 'inline',
  attachments: NotebookAttachments = {},
): ReactNode[] {
  const source = String(text ?? '')
  const token = /(!\[[^\]]*\]\((?:attachment:[^)]+|https?:\/\/[^)\s]+)\)|`[^`]*`|\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g
  const nodes: ReactNode[] = []
  let last = 0
  let match: RegExpExecArray | null
  let index = 0

  while ((match = token.exec(source))) {
    if (match.index > last) nodes.push(source.slice(last, match.index))
    const value = match[0]
    const key = `${keyPrefix}-${index++}`

    if (value.startsWith('![')) {
      const image = value.match(/^!\[([^\]]*)\]\((attachment:[^)]+|https?:\/\/[^)\s]+)\)$/)
      if (image) {
        const target = image[2] ?? ''
        const src = target.startsWith('attachment:')
          ? notebookAttachmentDataUrl(attachments, target)
          : target
        if (src) {
          nodes.push(
            <img
              key={key}
              className="notebook-markdown-inline-image"
              alt={image[1] || 'Notebook attachment'}
              src={src}
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

export function NotebookOutput({ output }: NotebookOutputProps) {
  if (!output) return null
  const outputType = String(output.output_type || '')

  if (outputType === 'stream') {
    return (
      <pre className={output.name === 'stderr' ? 'notebook-output-stream error' : 'notebook-output-stream'}>
        {notebookSourceToText(output.text)}
      </pre>
    )
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
      return (
        <div className="notebook-output-rich">
          <img alt="Notebook output" src={`data:image/png;base64,${image.replace(/\s/g, '')}`} />
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
