import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../api'
import type { CodexRateLimitSnapshot, CodexStatus } from '../../types/codex'

type Props = {
  enabled: boolean
  busy?: boolean
  onEnabledChange: (enabled: boolean) => void
  onSave: () => Promise<void> | void
}

function formatReset(value?: number | null): string {
  if (!value) return '-'
  try { return new Date(value * 1000).toLocaleString('ko-KR') } catch { return '-' }
}

function remaining(window?: { usedPercent?: number } | null): string {
  if (!window || typeof window.usedPercent !== 'number') return '-'
  return `${Math.max(0, 100 - Number(window.usedPercent)).toFixed(0)}%`
}

function windowLabel(window: { windowDurationMins?: number | null } | null | undefined, fallback: string): string {
  const minutes = Number(window?.windowDurationMins || 0)
  if (!minutes) return fallback
  if (minutes === 300) return '5시간 한도 남음'
  if (minutes === 10080) return '1주 한도 남음'
  if (minutes % 1440 === 0) return `${Math.round(minutes / 1440)}일 한도 남음`
  if (minutes % 60 === 0) return `${Math.round(minutes / 60)}시간 한도 남음`
  return `${minutes}분 한도 남음`
}

export function CodexSettingsPanel({ enabled, busy = false, onEnabledChange, onSave }: Props) {
  const [status, setStatus] = useState<CodexStatus>({ installed: false, running: false, initialized: false })
  const [localBusy, setLocalBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const next = await api<CodexStatus>('/codex/status')
      setStatus(next)
      setError('')
      return next
    } catch (e: any) {
      setError(e?.message || String(e))
      return null
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const account = status.account || null
  const usageBuckets = useMemo(() => {
    const payload = status.rate_limits || {}
    const byId = payload.rateLimitsByLimitId || null
    if (byId && Object.keys(byId).length) return Object.values(byId)
    return payload.rateLimits ? [payload.rateLimits] : []
  }, [status.rate_limits])

  async function save() {
    setMessage(''); setError('')
    try {
      await onSave()
      setMessage(enabled ? 'Codex 사용 설정을 저장했습니다.' : 'Codex 비사용 설정을 저장했습니다.')
      setTimeout(refresh, 100)
    } catch (e: any) {
      setError(e?.message || String(e))
    }
  }

  async function start() {
    setLocalBusy(true); setMessage(''); setError('')
    try {
      await onSave()
      const started = await api<CodexStatus>('/codex/start', { method: 'POST', body: JSON.stringify({ root: '' }) })
      const next = started.initialized ? (await refresh() || started) : started
      setStatus(next)
      if (next.initialized) setMessage(next.account ? 'Codex app-server와 ChatGPT 계정 연결을 확인했습니다.' : 'Codex app-server가 준비되었습니다.')
      else setError(next.last_error || 'Codex app-server를 시작하지 못했습니다.')
    } catch (e: any) { setError(e?.message || String(e)) }
    finally { setLocalBusy(false) }
  }

  async function login() {
    const popup = window.open('about:blank', '_blank')
    setLocalBusy(true); setMessage(''); setError('')
    try {
      await onSave()
      const result = await api<any>('/codex/login/chatgpt', { method: 'POST', body: JSON.stringify({ root: '' }) })
      const url = String(result.authUrl || result.auth_url || '')
      if (popup && url) popup.location.href = url
      else if (url) window.open(url, '_blank', 'noopener,noreferrer')
      else if (popup) popup.close()
      setMessage('ChatGPT 로그인 페이지를 열었습니다. 로그인 완료 후 상태 확인을 눌러 주세요.')
    } catch (e: any) {
      if (popup) popup.close()
      setError(e?.message || String(e))
    } finally { setLocalBusy(false) }
  }

  async function logout() {
    setLocalBusy(true); setMessage(''); setError('')
    try {
      const next = await api<CodexStatus>('/codex/logout', { method: 'POST' })
      setStatus(next)
      setMessage('Codex ChatGPT 계정 연결을 해제했습니다.')
    } catch (e: any) { setError(e?.message || String(e)) }
    finally { setLocalBusy(false) }
  }

  async function refreshUsage() {
    setLocalBusy(true); setMessage(''); setError('')
    try {
      const result = await api<any>('/codex/rate-limits?force=true')
      if (!result.ok && !result.rate_limits) throw new Error(result.message || result.error || 'Codex 사용량을 확인할 수 없습니다.')
      await refresh()
      setMessage('Codex 사용량을 새로고침했습니다.')
    } catch (e: any) { setError(e?.message || String(e)) }
    finally { setLocalBusy(false) }
  }

  const working = busy || localBusy
  const plan = String(account?.planType || '').toUpperCase()
  const accountLabel = account?.email || (account ? 'ChatGPT 계정 연결됨' : '연결 안 됨')

  return <section className="settings-panel codex-settings-panel">
    <h2>Codex / ChatGPT 계정</h2>
    <label className="setting-checkbox-row">
      <input type="checkbox" checked={enabled} onChange={(e: React.ChangeEvent<HTMLInputElement>) => onEnabledChange(e.target.checked)} />
      <span>Codex 사용</span>
    </label>
    <div className="hint-box">
      Codex를 켜면 복잡한 코딩·요구사항 분석에서 <b>Ollama → OpenAI API → Codex</b> 순으로 필요할 때만 보조 Provider로 사용할 수 있습니다.
      ChatGPT OAuth 토큰은 AgentStudio DB나 .env에 저장하지 않고 공식 Codex CLI가 관리합니다.
    </div>

    <div className="codex-settings-status-grid">
      <div><span>설치</span><b>{status.installed ? `설치됨 ${status.version || ''}` : '미설치'}</b></div>
      <div><span>app-server</span><b>{status.initialized ? '준비됨' : status.running ? '시작 중' : '중지'}</b></div>
      <div><span>계정</span><b>{accountLabel}</b></div>
      <div><span>요금제</span><b>{plan || '-'}</b></div>
    </div>

    {!status.installed && <div className="codex-install-command">
      <span>Codex CLI 설치 명령</span>
      <code>{status.windows_install_command || status.npm_install_command || 'npm install -g @openai/codex'}</code>
    </div>}

    <div className="panel-actions codex-settings-actions">
      <button disabled={working} onClick={save}>Codex 설정 저장</button>
      <button disabled={working || !enabled || !status.installed} onClick={start}>Codex 시작/상태 확인</button>
      {!account
        ? <button disabled={working || !enabled || !status.installed} onClick={login}>ChatGPT 계정 연결</button>
        : <button disabled={working || !enabled} className="danger" onClick={logout}>계정 연결 해제</button>}
      <button disabled={working || !account} onClick={refreshUsage}>남은 사용량 새로고침</button>
    </div>

    {!!usageBuckets.length && <div className="codex-usage-settings">
      <div className="codex-usage-settings-title"><b>Codex 남은 사용량</b><span>app-server 공식 rate limit 정보</span></div>
      {usageBuckets.map((bucket: CodexRateLimitSnapshot, index) => <div className="codex-usage-bucket" key={String(bucket.limitId || bucket.limitName || index)}>
        <strong>{bucket.limitName || bucket.limitId || `사용량 ${index + 1}`}</strong>
        <div className="codex-usage-window-grid">
          <div><span>{windowLabel(bucket.primary, '1차 한도 남음')}</span><b>{remaining(bucket.primary)}</b><small>초기화 {formatReset(bucket.primary?.resetsAt)}</small></div>
          <div><span>{windowLabel(bucket.secondary, '2차 한도 남음')}</span><b>{remaining(bucket.secondary)}</b><small>초기화 {formatReset(bucket.secondary?.resetsAt)}</small></div>
          {bucket.individualLimit && <div><span>개별 한도 남음</span><b>{bucket.individualLimit.remainingPercent ?? '-'}%</b><small>초기화 {formatReset(bucket.individualLimit.resetsAt)}</small></div>}
          {bucket.credits && <div><span>Credit</span><b>{bucket.credits.unlimited ? '무제한' : (bucket.credits.balance ?? '-')}</b><small>{bucket.credits.hasCredits ? '사용 가능' : '추가 Credit 없음'}</small></div>}
        </div>
      </div>)}
      {status.rate_limits?.rateLimitResetCredits?.availableCount != null && <small>사용 가능한 사용량 Reset Credit: {status.rate_limits.rateLimitResetCredits.availableCount}개</small>}
    </div>}

    {account && !usageBuckets.length && <div className="hint-box">현재 Codex app-server가 사용량 정보를 반환하지 않았습니다. 요금제/서버 버전에 따라 일부 사용량 정보가 제공되지 않을 수 있습니다.</div>}
    {status.rate_limits_error && <div className="test-result badbox">{status.rate_limits_error}</div>}
    {message && <div className="test-result okbox">{message}</div>}
    {error && <div className="test-result badbox">{error}</div>}
  </section>
}
