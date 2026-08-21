import type { TerminalClientMessage, TerminalServerMessage } from '../types/terminal'

export const parseTerminalServerMessage = (raw: unknown): TerminalServerMessage => {
  const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { type: 'unknown', raw: parsed }
  }

  const type = (parsed as { type?: unknown }).type
  if (typeof type !== 'string' || !type.trim()) {
    return { type: 'unknown', raw: parsed }
  }

  return parsed as TerminalServerMessage
}

export const serializeTerminalClientMessage = (message: TerminalClientMessage): string =>
  JSON.stringify(message)

export const terminalCellWidth = (text = ''): number => {
  const clean = String(text || '').replace(/\x1b\[[0-?]*[ -\/]*[@-~]/g, '')
  let width = 0

  for (const ch of clean) {
    const code = ch.codePointAt(0) ?? 0
    if (ch === '\t') {
      width += 4 - (width % 4)
      continue
    }

    const isWide = (
      (code >= 0x1100 && code <= 0x115f)
      || (code >= 0x2329 && code <= 0x232a)
      || (code >= 0x2e80 && code <= 0xa4cf && code !== 0x303f)
      || (code >= 0xac00 && code <= 0xd7a3)
      || (code >= 0xf900 && code <= 0xfaff)
      || (code >= 0xfe10 && code <= 0xfe19)
      || (code >= 0xfe30 && code <= 0xfe6f)
      || (code >= 0xff00 && code <= 0xff60)
      || (code >= 0xffe0 && code <= 0xffe6)
      || (code >= 0x1f300 && code <= 0x1faff)
    )

    width += isWide ? 2 : 1
  }

  return width
}

export const terminalLongestLineWidth = (text = ''): number => Math.max(
  0,
  ...String(text || '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .map(terminalCellWidth),
)

export interface TerminalPreviousCharacter {
  text: string
  start: number
}

export interface TerminalNextCharacter {
  text: string
  end: number
}

export const terminalPreviousCharacter = (value: string, cursor: number): TerminalPreviousCharacter => {
  if (cursor <= 0) return { text: '', start: 0 }
  const before = value.slice(0, cursor)
  const chars = Array.from(before)
  const text = chars[chars.length - 1] || ''
  return { text, start: cursor - text.length }
}

export const terminalNextCharacter = (value: string, cursor: number): TerminalNextCharacter => {
  if (cursor >= value.length) return { text: '', end: value.length }
  const text = Array.from(value.slice(cursor))[0] || ''
  return { text, end: cursor + text.length }
}
