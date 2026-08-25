import { useEffect, useState } from 'react'
import { api } from '../../api'
import type {
  ChromiumBrowserPopup,
  ChromiumBrowserState,
  WebBrowserTab,
} from '../../types/browser'
import {
  normalizeBrowserUrl,
  usesBackendBrowserProxy,
} from '../../utils/browser'
import { ChromiumRemoteViewport } from './ChromiumRemoteViewport'

export interface EmbeddedWebBrowserProps {
  tab: WebBrowserTab
  detectionEnabled: boolean
  onDetectionEnabledChange: (enabled: boolean) => void
  onNavigate: (tabId: string, url: string) => void
  onBack: (tabId: string) => void
  onForward: (tabId: string) => void
  onReload: (tabId: string) => void
  onHome: (tabId: string) => void
  onOpenNewTab: (url?: string) => void
  onOpenExternal: (url: string) => void
  onRemoteState: (tabId: string, state: ChromiumBrowserState) => void
  onRemotePopup: (parentTabId: string, popup: ChromiumBrowserPopup) => void
}

export function EmbeddedWebBrowser({
  tab,
  detectionEnabled,
  onDetectionEnabledChange,
  onNavigate,
  onBack,
  onForward,
  onReload,
  onHome,
  onOpenNewTab,
  onOpenExternal,
  onRemoteState,
  onRemotePopup,
}: EmbeddedWebBrowserProps) {
  const [address, setAddress] = useState(tab.url)
  const externalChromiumMode = Boolean(tab.remoteSessionId) || usesBackendBrowserProxy(tab.url)

  useEffect(() => {
    setAddress(tab.url)
  }, [tab.id, tab.url])

  const submit = () => {
    const url = normalizeBrowserUrl(address)
    if (!url) return
    onNavigate(tab.id, url)
  }

  const remoteSessionId = tab.remoteSessionId || tab.id
  const remoteHistoryAction = async (action: 'back' | 'forward' | 'reload') => {
    try {
      const state = await api<ChromiumBrowserState>(
        `/web-browser/chromium/${encodeURIComponent(remoteSessionId)}/action`,
        { method: 'POST', body: JSON.stringify({ action }) },
      )
      onRemoteState(tab.id, state)
      for (const popup of state.popups || []) onRemotePopup(tab.id, popup)
    } catch {
      // The remote viewport keeps its own visible error state. Toolbar history
      // failure should not crash the AgentStudio workspace.
    }
  }

  const canBack = externalChromiumMode ? Boolean(tab.url) : tab.historyIndex > 0
  const canForward = externalChromiumMode
    ? Boolean(tab.url)
    : tab.historyIndex >= 0 && tab.historyIndex < tab.history.length - 1

  return <div className="embedded-web-browser">
    <div className="embedded-browser-chrome-bar">
      <div className="embedded-browser-window-dots" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <strong>Chrome</strong>
      <span className="embedded-browser-mode">
        {tab.url
          ? (externalChromiumMode ? '외부 사이트 · Chrome CDP 실시간' : '내부 IP · 직접 연결')
          : 'AgentStudio 내장 웹브라우저'}
      </span>
      <label className="embedded-browser-monitor-toggle" title="터미널에서 로컬 웹 서비스 URL을 감지합니다.">
        <input
          type="checkbox"
          checked={detectionEnabled}
          onChange={event => onDetectionEnabledChange(event.target.checked)}
        />
        웹 URL 감지
      </label>
    </div>

    <div className="embedded-browser-toolbar">
      <button
        type="button"
        onClick={() => externalChromiumMode ? void remoteHistoryAction('back') : onBack(tab.id)}
        disabled={!canBack}
        title="뒤로"
      >←</button>
      <button
        type="button"
        onClick={() => externalChromiumMode ? void remoteHistoryAction('forward') : onForward(tab.id)}
        disabled={!canForward}
        title="앞으로"
      >→</button>
      <button
        type="button"
        onClick={() => externalChromiumMode ? void remoteHistoryAction('reload') : onReload(tab.id)}
        disabled={!tab.url}
        title="새로고침"
      >↻</button>
      <button type="button" onClick={() => onHome(tab.id)} title="새 탭">⌂</button>
      <form
        className="embedded-browser-address-form"
        onSubmit={event => {
          event.preventDefault()
          submit()
        }}
      >
        <span className="embedded-browser-security-mark">◉</span>
        <input
          value={address}
          onChange={event => setAddress(event.target.value)}
          onFocus={event => event.currentTarget.select()}
          placeholder="https://www.naver.com 또는 http://localhost:8501"
          spellCheck={false}
          aria-label="웹 주소"
        />
      </form>
      <button type="button" className="embedded-browser-go" onClick={submit}>이동</button>
      <button type="button" onClick={() => onOpenNewTab(tab.url)} title="추가 Browser 탭">＋ 웹</button>
      <button
        type="button"
        onClick={() => tab.url && onOpenExternal(tab.url)}
        disabled={!tab.url}
        title="현재 URL을 외부 Chrome/기본 브라우저로 엽니다."
      >↗ Chrome</button>
    </div>

    <div className="embedded-browser-viewport">
      {(tab.url || tab.remoteSessionId)
        ? externalChromiumMode
          ? <ChromiumRemoteViewport
              tab={tab}
              onRemoteState={(tabId, state) => {
                setAddress(state.url || tab.url)
                onRemoteState(tabId, state)
              }}
              onRemotePopup={onRemotePopup}
            />
          : <iframe
              key={`${tab.id}:${tab.revision}:${tab.url}`}
              src={tab.url}
              title={`${tab.title} 웹 미리보기`}
              referrerPolicy="no-referrer-when-downgrade"
              allow="clipboard-read; clipboard-write; fullscreen"
            />
        : <div className="embedded-browser-start-page">
            <div className="embedded-browser-start-logo">◎</div>
            <h2>THEANOVA Web Browser</h2>
            <p>외부 사이트는 시스템 Chrome CDP로 실시간 표시하고, 내부 개발 서버는 직접 연결로 엽니다.</p>
            <div className="embedded-browser-start-examples">
              <code>https://www.naver.com</code>
              <code>http://localhost:8501</code>
              <code>http://127.0.0.1:8000/docs</code>
            </div>
          </div>
      }
    </div>

    <div className="embedded-browser-statusbar">
      <span>{address || '새 탭'}</span>
      <small>
        {tab.url
          ? (externalChromiumMode
              ? '외부 사이트는 시스템 Chrome CDP screencast로 실시간 표시합니다. 사이트 팝업은 새 AgentStudio 웹브라우저 탭으로 엽니다.'
              : 'localhost/내부 IP는 기존 방식으로 직접 표시합니다.')
          : '외부=Chrome CDP · 내부 IP=직접 연결'}
      </small>
    </div>
  </div>
}
