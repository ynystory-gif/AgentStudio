import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CompositionEvent, ChangeEvent } from 'react'
import { AgentStudioApiError, api, runtimeInfo } from '../../api'
import type {
  ChromiumBrowserPopup,
  ChromiumBrowserState,
  ChromiumScreencastFrame,
  ChromiumStartupDiagnostics,
  WebBrowserTab,
} from '../../types/browser'

export interface ChromiumRemoteViewportProps {
  tab: WebBrowserTab
  onRemoteState: (tabId: string, state: ChromiumBrowserState) => void
  onRemotePopup: (parentTabId: string, popup: ChromiumBrowserPopup) => void
}

const MIN_WIDTH = 320
const MIN_HEIGHT = 220

function playwrightKey(event: React.KeyboardEvent<HTMLTextAreaElement>): string {
  const modifiers: string[] = []
  if (event.ctrlKey) modifiers.push('Control')
  if (event.altKey) modifiers.push('Alt')
  if (event.shiftKey) modifiers.push('Shift')
  if (event.metaKey) modifiers.push('Meta')
  const keyMap: Record<string, string> = {
    ' ': 'Space',
    Esc: 'Escape',
  }
  const key = keyMap[event.key] || event.key
  if (!key || key === 'Process' || key === 'Unidentified') return ''
  return [...modifiers, key].join('+')
}


function browserErrorMessage(cause: unknown): string {
  if (cause instanceof AgentStudioApiError && cause.responseBody) {
    try {
      const payload = JSON.parse(cause.responseBody) as { detail?: { message?: string } | string }
      if (typeof payload.detail === 'object' && payload.detail?.message) return payload.detail.message
      if (typeof payload.detail === 'string') return payload.detail
    } catch {
      // fall through to the normal Error message
    }
  }
  return cause instanceof Error ? cause.message : String(cause)
}

function diagnosticsFromError(cause: unknown): ChromiumStartupDiagnostics | null {
  if (!(cause instanceof AgentStudioApiError) || !cause.responseBody) return null
  try {
    const payload = JSON.parse(cause.responseBody) as { detail?: { diagnostics?: ChromiumStartupDiagnostics } }
    return payload.detail?.diagnostics || null
  } catch {
    return null
  }
}

function diagnosticsText(value: ChromiumStartupDiagnostics | null): string {
  if (!value) return ''
  const lines: string[] = [
    `상태: ${value.status}`,
    `실패 단계: ${value.stage || '-'}`,
    `메시지: ${value.message || '-'}`,
    `힌트: ${value.hint || '-'}`,
    `시작: ${value.started_at || '-'}`,
    `갱신: ${value.updated_at || '-'}`,
    `진단 로그 파일: ${value.log_path || '-'}`,
    `진단 로그 존재: ${value.log_exists ? '예' : '아니오'} · ${value.log_size_bytes ?? 0} bytes`,
    `진단 로그 쓰기 오류: ${value.log_write_error || '-'}`,
    `Helper 모드: ${value.worker?.mode || '-'}`,
    `Helper PID: ${value.worker?.pid ?? '-'}`,
    `Helper EventLoop: ${value.worker?.event_loop_policy || '-'}`,
    `Helper 로그: ${value.worker?.log_path || '-'}`,
    `Helper 예외: ${value.worker?.exception_type || '-'} · ${value.worker?.exception_repr || '-'}`,
    `HTTP Proxy 설정: ${value.proxy?.http_proxy_set ? '있음' : '없음'}`,
    `HTTPS Proxy 설정: ${value.proxy?.https_proxy_set ? '있음' : '없음'}`,
    `NO_PROXY: ${value.proxy?.no_proxy || '-'}`,
    `CDP HTTP: ${value.cdp_http_url || '-'}`,
    `CDP WebSocket: ${value.cdp_ws_url || '-'}`,
    '',
    `브라우저 후보 (${value.candidates?.length || 0})`,
    ...(value.candidates || []).map((item: LegacyValue, index: LegacyValue) => `  ${index + 1}. ${item}`),
  ]
  for (const [index, attempt] of (value.attempts || []).entries()) {
    lines.push(
      '',
      `시도 ${index + 1}: ${attempt.browser || '-'}`,
      `  실행 파일: ${attempt.executable || '-'}`,
      `  PID: ${attempt.pid ?? '-'}`,
      `  ExitCode: ${attempt.exit_code ?? '-'}`,
      `  Runtime Profile: ${attempt.runtime_profile_dir || '-'}`,
      `  Startup Log: ${attempt.startup_log_path || '-'}`,
      `  Archived Startup Log: ${attempt.startup_log_archived_path || '-'}`,
      `  DevToolsActivePort: ${attempt.devtools_active_port_exists ? '생성됨' : '없음'}`,
      `  ActivePort 내용: ${attempt.devtools_active_port || '-'}`,
      `  CDP HTTP: ${attempt.cdp_http_url || '-'}`,
      `  CDP WebSocket: ${attempt.cdp_ws_url || '-'}`,
      `  마지막 오류: ${attempt.last_error || '-'}`,
      '  실행 명령:',
      `    ${(attempt.command || []).join(' ') || '-'}`,
      '  Chrome startup log tail:',
      attempt.startup_log_tail ? attempt.startup_log_tail.split(/\r?\n/).map((line: LegacyValue) => `    ${line}`).join('\n') : '    (내용 없음)',
    )
  }
  return lines.join('\n')
}

function isControlKey(event: React.KeyboardEvent<HTMLTextAreaElement>): boolean {
  return event.ctrlKey
    || event.altKey
    || event.metaKey
    || event.key.length !== 1
    || ['Enter', 'Tab', 'Backspace', 'Delete', 'Escape'].includes(event.key)
}

export function ChromiumRemoteViewport({
  tab,
  onRemoteState,
  onRemotePopup,
}: ChromiumRemoteViewportProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const keyboardRef = useRef<HTMLTextAreaElement | null>(null)
  const [viewportSize, setViewportSize] = useState({ width: 1280, height: 720 })
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [diagnostics, setDiagnostics] = useState<ChromiumStartupDiagnostics | null>(null)
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false)
  const [copyStatus, setCopyStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [frameRevision, setFrameRevision] = useState(0)
  const [frameSrc, setFrameSrc] = useState('')
  const [keyboardBuffer, setKeyboardBuffer] = useState('')
  const composingRef = useRef(false)
  const remoteUrlRef = useRef('')
  const navigatingRef = useRef(false)
  const lastAttemptUrlRef = useRef('')
  const closedRef = useRef(false)
  const sessionId = tab.remoteSessionId || tab.id
  const apiBase = runtimeInfo().apiBase
  const encodedSessionId = useMemo(() => encodeURIComponent(sessionId), [sessionId])
  const screenshotUrl = `${apiBase}/web-browser/chromium/${encodedSessionId}/screenshot?r=${frameRevision}`
  const streamUrl = useMemo(() => {
    const base = apiBase.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:').replace(/\/api$/, '')
    return `${base}/api/web-browser/cdp/${encodedSessionId}/stream`
  }, [apiBase, encodedSessionId])

  const loadDiagnostics = useCallback(async () => {
    setDiagnosticsLoading(true)
    try {
      const value = await api<ChromiumStartupDiagnostics>('/web-browser/chromium/diagnostics')
      setDiagnostics(value)
    } catch {
      // Keep diagnostics captured from the failed navigate response if refresh fails.
    } finally {
      setDiagnosticsLoading(false)
    }
  }, [])

  const captureFailure = useCallback((cause: unknown) => {
    setError(browserErrorMessage(cause))
    const embedded = diagnosticsFromError(cause)
    if (embedded) setDiagnostics(embedded)
    void loadDiagnostics()
  }, [loadDiagnostics])

  const copyDiagnostics = useCallback(async () => {
    const text = diagnosticsText(diagnostics)
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopyStatus('복사됨')
    } catch {
      setCopyStatus('복사 실패')
    }
    window.setTimeout(() => setCopyStatus(''), 1400)
  }, [diagnostics])

  const applyState = useCallback((state: ChromiumBrowserState) => {
    remoteUrlRef.current = state.url || remoteUrlRef.current
    setLoading(Boolean(state.loading))
    setReady(true)
    setError('')
    onRemoteState(tab.id, state)
    for (const popup of state.popups || []) {
      onRemotePopup(tab.id, popup)
    }
    setFrameRevision((value: LegacyValue) => value + 1)
  }, [onRemotePopup, onRemoteState, tab.id])

  const sendAction = useCallback(async (
    action: string,
    payload: Record<string, unknown> = {},
  ) => {
    try {
      const state = await api<ChromiumBrowserState>(
        `/web-browser/chromium/${encodedSessionId}/action`,
        {
          method: 'POST',
          body: JSON.stringify({
            action,
            viewport_width: viewportSize.width,
            viewport_height: viewportSize.height,
            ...payload,
          }),
        },
      )
      applyState(state)
    } catch (cause) {
      captureFailure(cause)
    }
  }, [applyState, captureFailure, encodedSessionId, viewportSize.height, viewportSize.width])

  useEffect(() => {
    closedRef.current = false
    const target = tab.url
    if (!target || navigatingRef.current) return
    if (lastAttemptUrlRef.current === target) return
    // Popup pages are already alive in Chromium. Do not reload the popup merely
    // because AgentStudio created a matching UI tab for it.
    if (tab.remoteSessionId && remoteUrlRef.current === '') {
      remoteUrlRef.current = target
      setReady(true)
      setFrameRevision((value: LegacyValue) => value + 1)
      return
    }
    if (remoteUrlRef.current === target) return
    navigatingRef.current = true
    lastAttemptUrlRef.current = target
    const forceRestart = false
    setLoading(true)
    setError('')
    setDiagnostics(null)
    setCopyStatus('')
    void api<ChromiumBrowserState>(
      `/web-browser/chromium/${encodedSessionId}/navigate`,
      {
        method: 'POST',
        body: JSON.stringify({
          url: target,
          viewport_width: viewportSize.width,
          viewport_height: viewportSize.height,
          force_restart: forceRestart,
        }),
      },
    ).then(applyState).catch((cause: LegacyValue) => {
      captureFailure(cause)
      setLoading(false)
    }).finally(() => {
      navigatingRef.current = false
    })
    return () => {
      closedRef.current = true
    }
  }, [applyState, captureFailure, encodedSessionId, tab.remoteSessionId, tab.url, viewportSize.height, viewportSize.width])

  useEffect(() => {
    const node = viewportRef.current
    if (!node || typeof ResizeObserver === 'undefined') return
    let timer = 0
    const observer = new ResizeObserver((entries: LegacyValue) => {
      const rect = entries[0]?.contentRect
      if (!rect) return
      const width = Math.max(MIN_WIDTH, Math.round(rect.width))
      const height = Math.max(MIN_HEIGHT, Math.round(rect.height))
      setViewportSize((current: LegacyValue) => current.width === width && current.height === height ? current : { width, height })
      window.clearTimeout(timer)
      timer = window.setTimeout(() => {
        if (ready && !error) void sendAction('resize', { viewport_width: width, viewport_height: height })
      }, 180)
    })
    observer.observe(node)
    return () => {
      window.clearTimeout(timer)
      observer.disconnect()
    }
  }, [error, ready, sendAction])

  useEffect(() => {
    if (!tab.url || !ready || error) return
    let disposed = false
    let retryTimer = 0
    let socket: WebSocket | null = null
    let retryCount = 0

    const connect = () => {
      if (disposed) return
      socket = new WebSocket(streamUrl)
      socket.onmessage = (event: LegacyValue) => {
        if (disposed) return
        try {
          const message = JSON.parse(event.data) as ChromiumScreencastFrame
          if (message.type === 'frame' && message.data) {
            setFrameSrc(`data:image/jpeg;base64,${message.data}`)
            setFrameRevision(Number(message.revision || 0))
            setReady(true)
            setLoading(Boolean(message.loading))
            setError('')
          } else if (message.type === 'error' && message.message) {
            setError(message.message)
            void loadDiagnostics()
          }
        } catch {
          // Ignore malformed frame messages; state polling remains as fallback.
        }
      }
      socket.onclose = () => {
        if (!disposed && !error && retryCount < 2) {
          retryCount += 1
          retryTimer = window.setTimeout(connect, 900 * retryCount)
        }
      }
      socket.onerror = () => {
        try { socket?.close() } catch { /* noop */ }
      }
    }
    connect()
    return () => {
      disposed = true
      window.clearTimeout(retryTimer)
      try { socket?.close() } catch { /* noop */ }
    }
  }, [error, loadDiagnostics, ready, streamUrl, tab.url])

  useEffect(() => {
    if (!tab.url || !ready || error) return
    const poll = window.setInterval(() => {
      void api<ChromiumBrowserState>(`/web-browser/chromium/${encodedSessionId}/state`)
        .then((state: LegacyValue) => {
          if (!closedRef.current) applyState(state)
        })
        .catch(() => undefined)
    }, 1800)
    return () => window.clearInterval(poll)
  }, [applyState, encodedSessionId, error, ready, tab.url])


  useEffect(() => {
    return () => {
      if (!ready) return
      void api<ChromiumBrowserState>(
        `/web-browser/chromium/${encodedSessionId}/action`,
        { method: 'POST', body: JSON.stringify({ action: 'suspend' }) },
      ).catch(() => undefined)
    }
  }, [encodedSessionId, ready])

  const clickRemote = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect()
    if (!rect || rect.width <= 0 || rect.height <= 0) return
    const x = (event.clientX - rect.left) * (viewportSize.width / rect.width)
    const y = (event.clientY - rect.top) * (viewportSize.height / rect.height)
    keyboardRef.current?.focus({ preventScroll: true })
    void sendAction('click', {
      x,
      y,
      button: event.button === 2 ? 'right' : event.button === 1 ? 'middle' : 'left',
      click_count: Math.max(1, Math.min(3, event.detail || 1)),
    })
  }

  const wheelRemote = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    void sendAction('scroll', { delta_x: event.deltaX, delta_y: event.deltaY })
  }

  const keyRemote = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!isControlKey(event)) return
    const key = playwrightKey(event)
    if (!key) return
    event.preventDefault()
    void sendAction('key', { key })
  }

  const textRemote = (value: string) => {
    if (!value) return
    setKeyboardBuffer('')
    void sendAction('text', { text: value })
  }

  const retryRemote = () => {
    if (!tab.url || navigatingRef.current) return
    navigatingRef.current = true
    lastAttemptUrlRef.current = tab.url
    remoteUrlRef.current = ''
    setReady(false)
    setLoading(true)
    setError('')
    setDiagnostics(null)
    setCopyStatus('')
    void api<ChromiumBrowserState>(
      `/web-browser/chromium/${encodedSessionId}/navigate`,
      {
        method: 'POST',
        body: JSON.stringify({
          url: tab.url,
          viewport_width: viewportSize.width,
          viewport_height: viewportSize.height,
          force_restart: true,
        }),
      },
    ).then(applyState).catch((cause: LegacyValue) => {
      captureFailure(cause)
      setLoading(false)
    }).finally(() => {
      navigatingRef.current = false
    })
  }

  return <div
    ref={viewportRef}
    className="chromium-remote-viewport"
    onMouseDown={clickRemote}
    onWheel={wheelRemote}
    onContextMenu={(event: React.MouseEvent<HTMLDivElement>) => event.preventDefault()}
  >
    {ready && !error && <img
      src={frameSrc || screenshotUrl}
      alt="외부 Chromium 웹페이지 화면"
      draggable={false}
      onLoad={() => setLoading(false)}
      onError={() => undefined}
    />}
    {!ready && !error && <div className="chromium-remote-overlay">
      <div className="chromium-remote-spinner"></div>
      <strong>시스템 Chrome CDP에 연결하는 중...</strong>
      <small>외부 사이트는 Chrome DevTools Protocol 실시간 screencast로 표시합니다.</small>
    </div>}
    {loading && ready && !error && <div className="chromium-remote-loading">불러오는 중…</div>}
    {error && <div className="chromium-remote-error" onMouseDown={(event: LegacyValue) => event.stopPropagation()} onWheel={(event: LegacyValue) => event.stopPropagation()}>
      <div className="chromium-remote-error-summary">
        <strong>외부 Chromium 브라우저 연결 실패</strong>
        <p>{error}</p>
        <small>아래 진단 로그에서 Chrome/Edge 실행 단계와 실제 실패 지점을 확인할 수 있습니다.</small>
        <div className="chromium-remote-error-actions">
          <button type="button" className="chromium-remote-retry" onClick={retryRemote}>다시 연결</button>
          <button type="button" className="chromium-remote-log-button" onClick={() => void loadDiagnostics()} disabled={diagnosticsLoading}>
            {diagnosticsLoading ? '로그 확인 중…' : '로그 새로고침'}
          </button>
          <button type="button" className="chromium-remote-log-button" onClick={() => void copyDiagnostics()} disabled={!diagnostics}>
            진단 로그 복사{copyStatus ? ` · ${copyStatus}` : ''}
          </button>
        </div>
      </div>
      <details className="chromium-remote-diagnostics" open>
        <summary>Chrome CDP 진단 로그</summary>
        {diagnostics ? <div className="chromium-remote-diagnostics-body">
          <div className="chromium-remote-diag-grid">
            <span>상태</span><b>{diagnostics.status || '-'}</b>
            <span>실패 단계</span><b>{diagnostics.stage || '-'}</b>
            <span>원인</span><b>{diagnostics.message || '-'}</b>
            <span>확인 사항</span><b>{diagnostics.hint || '-'}</b>
            <span>진단 파일</span><code>{diagnostics.log_path || '-'}</code>
            <span>진단 파일 상태</span><b>{diagnostics.log_exists ? `존재 · ${diagnostics.log_size_bytes ?? 0} bytes` : `없음${diagnostics.log_write_error ? ` · ${diagnostics.log_write_error}` : ''}`}</b>
            <span>CDP Endpoint</span><code>{diagnostics.cdp_http_url || '-'}</code>
            <span>Playwright Helper</span><b>{diagnostics.worker?.pid ? `PID ${diagnostics.worker.pid} · ${diagnostics.worker.event_loop_policy || '-'}` : '-'}</b>
            <span>Helper 로그</span><code>{diagnostics.worker?.log_path || '-'}</code>
            <span>Helper 예외</span><b>{diagnostics.worker?.exception_type ? `${diagnostics.worker.exception_type}: ${diagnostics.worker.exception_repr || '-'}` : '-'}</b>
          </div>
          {(diagnostics.attempts || []).map((attempt: LegacyValue, index: LegacyValue) => <section className="chromium-remote-diag-attempt" key={`${attempt.executable}-${index}`}>
            <h4>브라우저 시도 {index + 1} · {attempt.browser || 'Browser'}</h4>
            <div className="chromium-remote-diag-grid">
              <span>실행 파일</span><code>{attempt.executable || '-'}</code>
              <span>PID / ExitCode</span><b>{attempt.pid ?? '-'} / {attempt.exit_code ?? '-'}</b>
              <span>Runtime Profile</span><code>{attempt.runtime_profile_dir || '-'}</code>
              <span>DevToolsActivePort</span><b>{attempt.devtools_active_port_exists ? '생성됨' : '생성되지 않음'}</b>
              <span>PID Handoff</span><b>{attempt.handoff_detected ? `감지됨 · ${(attempt.handoff_pids || []).join(', ')}` : '없음'}</b>
              <span>실패 정리</span><b>kill {attempt.cleanup_killed ?? 0} · remaining {attempt.cleanup_remaining ?? 0}</b>
              <span>마지막 오류</span><b>{attempt.last_error || '-'}</b>
              <span>Startup Log</span><code>{attempt.startup_log_path || '-'}</code>
              <span>보존 Startup Log</span><code>{attempt.startup_log_archived_path || '-'}</code>
            </div>
            <div className="chromium-remote-diag-command"><b>실행 명령</b><pre>{(attempt.command || []).join(' ') || '-'}</pre></div>
            <div className="chromium-remote-diag-command"><b>Chrome startup log tail</b><pre>{attempt.startup_log_tail || '(로그 내용 없음)'}</pre></div>
          </section>)}
          {diagnostics.worker && <section className="chromium-remote-diag-attempt">
            <h4>Playwright CDP Helper</h4>
            <div className="chromium-remote-diag-grid">
              <span>모드</span><b>{diagnostics.worker.mode || '-'}</b>
              <span>PID</span><b>{diagnostics.worker.pid ?? '-'}</b>
              <span>Python</span><code>{diagnostics.worker.python || '-'}</code>
              <span>EventLoop</span><b>{diagnostics.worker.event_loop_policy || '-'}</b>
              <span>로그 파일</span><code>{diagnostics.worker.log_path || '-'}</code>
              <span>로그 상태</span><b>{diagnostics.worker.log_exists ? '존재' : '없음'}</b>
              <span>예외 타입</span><b>{diagnostics.worker.exception_type || '-'}</b>
              <span>예외 repr</span><code>{diagnostics.worker.exception_repr || '-'}</code>
            </div>
            <div className="chromium-remote-diag-command"><b>Helper traceback</b><pre>{diagnostics.worker.traceback || '(없음)'}</pre></div>
            <div className="chromium-remote-diag-command"><b>Helper log tail</b><pre>{diagnostics.worker.log_tail || '(로그 내용 없음)'}</pre></div>
          </section>}
          {(!diagnostics.attempts || diagnostics.attempts.length === 0) && <pre className="chromium-remote-diag-empty">{diagnosticsText(diagnostics)}</pre>}
        </div> : <div className="chromium-remote-diag-empty">{diagnosticsLoading ? '진단 로그를 불러오는 중입니다…' : '진단 로그가 없습니다. 로그 새로고침을 눌러 확인하세요.'}</div>}
      </details>
    </div>}
    <textarea
      ref={keyboardRef}
      className="chromium-remote-keyboard-capture"
      value={keyboardBuffer}
      aria-label="외부 웹브라우저 키보드 입력"
      onKeyDown={keyRemote}
      onCompositionStart={() => { composingRef.current = true }}
      onCompositionEnd={(event: CompositionEvent<HTMLTextAreaElement>) => {
        composingRef.current = false
        const value = event.currentTarget.value
        if (value) textRemote(value)
      }}
      onChange={(event: ChangeEvent<HTMLTextAreaElement>) => {
        const value = event.target.value
        setKeyboardBuffer(value)
        if (!composingRef.current && value) textRemote(value)
      }}
    />
  </div>
}
