import type { ChromiumBrowserPopup, ChromiumBrowserState, WebBrowserTab } from '../../types/browser'
import { EmbeddedWebBrowser } from './EmbeddedWebBrowser'

export interface WebBrowserWorkspaceProps {
  tabs: WebBrowserTab[]
  activeTabId: string
  detectionEnabled: boolean
  onDetectionEnabledChange: (enabled: boolean) => void
  onActivateTab: (tabId: string) => void
  onCloseTab: (tabId: string) => void
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

export function WebBrowserWorkspace({
  tabs,
  activeTabId,
  detectionEnabled,
  onDetectionEnabledChange,
  onActivateTab,
  onCloseTab,
  onNavigate,
  onBack,
  onForward,
  onReload,
  onHome,
  onOpenNewTab,
  onOpenExternal,
  onRemoteState,
  onRemotePopup,
}: WebBrowserWorkspaceProps) {
  const activeTab = tabs.find(tab => tab.id === activeTabId) ?? tabs[0] ?? null

  if (!activeTab) {
    return <div className="web-browser-workspace-empty">웹브라우저 탭을 준비하지 못했습니다.</div>
  }

  return <div className="web-browser-workspace">
    <div className="web-browser-workspace-tabs" role="tablist" aria-label="웹브라우저 탭">
      {tabs.map(tab => {
        const active = tab.id === activeTab.id
        return <div
          key={tab.id}
          className={[
            'web-browser-workspace-tab',
            active ? 'active' : '',
            tab.fixed ? 'fixed' : '',
          ].filter(Boolean).join(' ')}
        >
          <button
            type="button"
            className="web-browser-workspace-tab-select"
            role="tab"
            aria-selected={active}
            title={tab.url || (tab.fixed ? '기본 고정 웹브라우저' : tab.title)}
            onClick={() => onActivateTab(tab.id)}
          >
            <span aria-hidden="true">🌐</span>
            <strong>{tab.fixed ? '기본 웹브라우저' : tab.title}</strong>
            {tab.detected && <i title="터미널 웹 감시에서 승인된 URL">●</i>}
          </button>
          {tab.fixed
            ? <span className="web-browser-workspace-fixed-pin" title="기본 고정 웹브라우저">📌</span>
            : <button
                type="button"
                className="web-browser-workspace-tab-close"
                title="웹브라우저 탭 닫기"
                aria-label={`${tab.title} 웹브라우저 탭 닫기`}
                onClick={event => {
                  event.stopPropagation()
                  onCloseTab(tab.id)
                }}
              >×</button>
          }
        </div>
      })}
      <button
        type="button"
        className="web-browser-workspace-add-tab"
        title="빈 웹브라우저 탭 추가"
        onClick={() => onOpenNewTab('')}
      >＋</button>
    </div>

    <EmbeddedWebBrowser
      tab={activeTab}
      detectionEnabled={detectionEnabled}
      onDetectionEnabledChange={onDetectionEnabledChange}
      onNavigate={onNavigate}
      onBack={onBack}
      onForward={onForward}
      onReload={onReload}
      onHome={onHome}
      onOpenNewTab={onOpenNewTab}
      onOpenExternal={onOpenExternal}
      onRemoteState={onRemoteState}
      onRemotePopup={onRemotePopup}
    />
  </div>
}
