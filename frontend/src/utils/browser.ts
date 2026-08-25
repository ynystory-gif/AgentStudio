const ANSI_ESCAPE_RE = /\x1B(?:[@-_][0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1B\\))/g
const URL_RE = /https?:\/\/[^\s<>'"`]+/gi

function stripTrailingUrlPunctuation(value: string): string {
  return value.replace(/[),.;\]}]+$/g, '')
}

export function normalizeBrowserUrl(value: string): string {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : `http://${raw}`
  try {
    const parsed = new URL(withScheme)
    if (parsed.hostname === '0.0.0.0' || parsed.hostname === '::' || parsed.hostname === '[::]') {
      parsed.hostname = '127.0.0.1'
    }
    return parsed.toString()
  } catch {
    return withScheme
  }
}

export function isLocalDevelopmentUrl(value: string): boolean {
  try {
    const parsed = new URL(normalizeBrowserUrl(value))
    const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, '')
    if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || host === '::1') return true
    if (/^10\./.test(host)) return true
    if (/^192\.168\./.test(host)) return true
    const match = host.match(/^172\.(\d+)\./)
    if (match) {
      const second = Number(match[1])
      return second >= 16 && second <= 31
    }
    return false
  } catch {
    return false
  }
}

export function extractLocalDevelopmentUrls(text: string): string[] {
  const clean = String(text || '').replace(ANSI_ESCAPE_RE, '')
  const found = clean.match(URL_RE) || []
  const unique = new Set<string>()
  for (const candidate of found) {
    const normalized = normalizeBrowserUrl(stripTrailingUrlPunctuation(candidate))
    if (normalized && isLocalDevelopmentUrl(normalized)) unique.add(normalized)
  }
  return [...unique]
}

export function browserTitleForUrl(value: string): string {
  if (!value) return 'Chrome'
  try {
    const parsed = new URL(normalizeBrowserUrl(value))
    return parsed.port ? `${parsed.hostname}:${parsed.port}` : parsed.hostname || 'Browser'
  } catch {
    return 'Browser'
  }
}

export function browserFrameUrl(value: string, sessionId: string, apiBase: string): string {
  const normalized = normalizeBrowserUrl(value)
  if (!normalized) return ''
  if (isLocalDevelopmentUrl(normalized)) return normalized
  try {
    const parsed = new URL(normalized)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return normalized
    const base = String(apiBase || '').replace(/\/$/, '')
    const session = encodeURIComponent(String(sessionId || 'default'))
    const scheme = parsed.protocol.slice(0, -1)
    const netloc = encodeURIComponent(parsed.host)
    return `${base}/web-proxy/${session}/${scheme}/${netloc}${parsed.pathname || '/'}${parsed.search}${parsed.hash}`
  } catch {
    return normalized
  }
}

export function usesBackendBrowserProxy(value: string): boolean {
  const normalized = normalizeBrowserUrl(value)
  return !!normalized && !isLocalDevelopmentUrl(normalized)
}
