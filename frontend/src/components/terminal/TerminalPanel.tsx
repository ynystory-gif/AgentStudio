import type { ChangeEvent, KeyboardEvent, MouseEvent, MutableRefObject } from 'react'
import type {
  ProjectTerminalStatus,
  TerminalCompletionItem,
  TerminalCompletionState,
  TerminalErrorInfo,
  TerminalSession,
} from '../../types/terminal'

interface TerminalPanelProps {
  hiddenForSql?: boolean
  sessions: TerminalSession[]
  activeTerminalId: string
  activeTerminal?: TerminalSession
  errors: Record<string, TerminalErrorInfo | null | undefined>
  terminalNameEditId: string | null
  terminalNameDraft: string
  activeTerminalProjectId: string | number | null
  projectTerminalSessions: Record<string, ProjectTerminalStatus | undefined>
  completion: TerminalCompletionState | null
  completionRef: MutableRefObject<TerminalCompletionState | null>
  onDismissError: (sessionId: string) => void
  onNameDraftChange: (value: string) => void
  onSaveName: (sessionId: string) => void
  onCancelRename: () => void
  onSelectTerminal: (session: TerminalSession) => void
  onStartRename: (session: TerminalSession) => void
  onRemoveTerminal: (sessionId: string) => void
  onRestartTerminal: (sessionId: string) => void
  onInterruptTerminal: (sessionId: string) => void
  onClearTerminal: (sessionId: string) => void
  onAddTerminal: () => void
  onBindTerminalContainer: (session: TerminalSession, element: HTMLDivElement | null) => void
  onTerminalMouseDown: (session: TerminalSession) => void
  onTerminalClick: (session: TerminalSession) => void
  onCompletionHover: (index: number) => void
  onApplyCompletion: (item: TerminalCompletionItem) => void
}

export function TerminalPanel({
  hiddenForSql = false,
  sessions,
  activeTerminalId,
  activeTerminal,
  errors,
  terminalNameEditId,
  terminalNameDraft,
  activeTerminalProjectId,
  projectTerminalSessions,
  completion,
  completionRef,
  onDismissError,
  onNameDraftChange,
  onSaveName,
  onCancelRename,
  onSelectTerminal,
  onStartRename,
  onRemoveTerminal,
  onRestartTerminal,
  onInterruptTerminal,
  onClearTerminal,
  onAddTerminal,
  onBindTerminalContainer,
  onTerminalMouseDown,
  onTerminalClick,
  onCompletionHover,
  onApplyCompletion,
}: TerminalPanelProps) {
  const activeError = activeTerminalId ? errors[activeTerminalId] : null
  const activeProject = activeTerminalProjectId == null
    ? undefined
    : projectTerminalSessions[String(activeTerminalProjectId)]

  return (
    <section className={`terminal-pane multi-terminal-pane ${hiddenForSql ? 'sql-hidden' : ''}`}>
      <div className="terminal-toolbar">
        <div className="terminal-tabs">
          {activeTerminalId && activeError && (
            <div className="terminal-error-panel">
              <div className="terminal-error-head">
                <strong>터미널 오류 상세</strong>
                <button type="button" onClick={() => onDismissError(activeTerminalId)}>닫기</button>
              </div>

              <div className="terminal-error-grid">
                <span>단계</span><code>{activeError.stage || '-'}</code>
                <span>오류</span><code>{activeError.message || '-'}</code>
                <span>프로젝트</span><code>{activeError.root || '-'}</code>
                <span>세션 ID</span><code>{activeError.sessionId || '-'}</code>
                <span>WebSocket</span><code>{activeError.wsUrl || '-'}</code>
                <span>발생 시각</span><code>{activeError.time || '-'}</code>
              </div>

              {activeError.logPath && (
                <div className="terminal-error-log-path">
                  <span>로그 전체 경로</span>
                  <code>{activeError.logPath}</code>
                </div>
              )}

              {activeError.detail && (
                <details className="terminal-error-detail" open>
                  <summary>상세 오류 / Traceback</summary>
                  <pre>{activeError.detail}</pre>
                </details>
              )}
            </div>
          )}

          {sessions.map((terminal) => (
            <div
              key={terminal.id}
              className={activeTerminalId === terminal.id ? 'terminal-tab active' : 'terminal-tab'}
            >
              {terminalNameEditId === terminal.id ? (
                <input
                  className="terminal-name-input"
                  value={terminalNameDraft}
                  autoFocus
                  onChange={(event: ChangeEvent<HTMLInputElement>) => onNameDraftChange(event.target.value)}
                  onBlur={() => onSaveName(terminal.id)}
                  onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
                    if (event.key === 'Enter') onSaveName(terminal.id)
                    if (event.key === 'Escape') onCancelRename()
                  }}
                />
              ) : (
                <button
                  className="terminal-tab-select"
                  onClick={() => onSelectTerminal(terminal)}
                  onDoubleClick={() => onStartRename(terminal)}
                  title="더블클릭하면 이름을 변경할 수 있습니다."
                >
                  {terminal.name}
                </button>
              )}

              <button
                className="terminal-tab-menu"
                onClick={() => onStartRename(terminal)}
                title="이름 변경"
              >✎</button>

              {sessions.length > 1 && (
                <button
                  className="terminal-tab-close"
                  onClick={() => onRemoveTerminal(terminal.id)}
                  title="터미널 닫기"
                >×</button>
              )}
            </div>
          ))}
        </div>

        {activeTerminal?.processState === 'exited' && (
          <button
            type="button"
            className="terminal-restart-button"
            onClick={() => onRestartTerminal(activeTerminal.id)}
          >
            다시 시작
          </button>
        )}

        {activeTerminal?.busy && (
          <button
            type="button"
            className="terminal-stop-button execution-stop-button"
            onClick={() => onInterruptTerminal(activeTerminalId)}
            title={activeTerminal.interrupting
              ? '종료가 아직 끝나지 않았다면 중단 신호를 다시 보냅니다.'
              : '현재 터미널에서 실행 중인 명령을 Ctrl+C로 중지'}
          >
            {activeTerminal.interrupting ? '■ 종료 확인 중…' : '■ 실행 정지'}
          </button>
        )}

        <button
          type="button"
          className="terminal-clear-button"
          onClick={() => onClearTerminal(activeTerminalId)}
          disabled={!activeTerminalId}
          title="현재 터미널 출력 지우기 (PowerShell 세션은 유지됩니다)"
        >⌫ Clear</button>

        <button className="add-terminal-button" onClick={onAddTerminal} title="새 터미널 만들기">
          ＋ 터미널
        </button>
      </div>

      {activeProject && (
        <div className="project-terminal-status">
          <span className="project-terminal-dot" />
          <strong>{activeProject.projectName || '프로젝트'}</strong>
          <code>{activeProject.root}</code>
          {activeProject.hasVenv && <span className="project-terminal-venv">.venv 활성</span>}
        </div>
      )}

      <div className="xterm-shell-wrap">
        {sessions.map((terminal) => (
          <div
            key={terminal.id}
            ref={(element: HTMLDivElement | null) => onBindTerminalContainer(terminal, element)}
            className={activeTerminalId === terminal.id ? 'xterm-shell active' : 'xterm-shell hidden'}
            onMouseDown={() => onTerminalMouseDown(terminal)}
            onClick={() => onTerminalClick(terminal)}
          />
        ))}

        {completion?.sessionId === activeTerminalId && (
          <div className="terminal-completion-menu" onMouseDown={(event: MouseEvent<HTMLDivElement>) => event.preventDefault()}>
            <div className="terminal-completion-head">
              <strong>
                터미널 자동완성
                {completion.token ? ` · ${completion.token}` : ''}
              </strong>
              <span>{completion.items?.length || 0}개 · ↑↓ 선택 · Tab/Enter 적용 · Esc 닫기</span>
            </div>

            {completion.loading && <div className="terminal-completion-empty">후보를 찾는 중...</div>}

            {!completion.loading && completion.error && (
              <div className="terminal-completion-empty error">{completion.error}</div>
            )}

            {!completion.loading && !completion.error && completion.items?.length === 0 && (
              <div className="terminal-completion-empty">일치하는 후보가 없습니다.</div>
            )}

            {!completion.loading && completion.items?.length > 0 && (
              <div className="terminal-completion-list">
                {completion.items.map((item, index) => (
                  <button
                    type="button"
                    key={`${item.kind || 'item'}:${item.insert_text || item.label}:${index}`}
                    className={index === completion.selectedIndex ? 'selected' : ''}
                    onMouseEnter={() => {
                      const current = completionRef.current
                      if (current?.sessionId === activeTerminalId) onCompletionHover(index)
                    }}
                    onMouseDown={(event: MouseEvent<HTMLButtonElement>) => {
                      event.preventDefault()
                      onApplyCompletion(item)
                    }}
                    title={item.detail || item.label}
                  >
                    <span className={`terminal-completion-kind ${item.kind || 'item'}`}>
                      {item.kind === 'folder' ? 'DIR' : item.kind === 'file' ? 'FILE' : 'CMD'}
                    </span>
                    <span className="terminal-completion-label">{item.label}</span>
                    <small>{item.detail || ''}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
