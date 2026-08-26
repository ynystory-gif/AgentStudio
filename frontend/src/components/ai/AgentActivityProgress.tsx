import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api'
import type { AiAttachmentAnalysisState } from './AiAttachmentPicker'

type ActivityKind = 'IDLE' | 'INTERVIEW' | 'ATTACHMENT_SUMMARY'

type Props = {
  active: boolean
  kind: ActivityKind
  attachmentCount: number
  attachmentState: AiAttachmentAnalysisState
  databasePreviewLoading?: boolean
  error?: string
  canRetry?: boolean
  onCancel?: () => void
  onRetry?: () => void
}

type HeartbeatStatus = 'IDLE' | 'CHECKING' | 'OK' | 'FAIL'

type ActivityLog = {
  at: number
  message: string
}

function elapsedLabel(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (!minutes) return `${rest}초`
  return `${minutes}분 ${String(rest).padStart(2, '0')}초`
}

function relativeSecondsLabel(timestamp: number, now: number): string {
  if (!timestamp) return '-'
  const seconds = Math.max(0, Math.floor((now - timestamp) / 1000))
  if (seconds < 2) return '방금 전'
  return `${seconds}초 전`
}

export function AgentActivityProgress({
  active,
  kind,
  attachmentCount,
  attachmentState,
  databasePreviewLoading = false,
  error = '',
  canRetry = false,
  onCancel,
  onRetry,
}: Props) {
  const [startedAt, setStartedAt] = useState(0)
  const [now, setNow] = useState(Date.now())
  const [heartbeat, setHeartbeat] = useState<HeartbeatStatus>('IDLE')
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState(0)
  const [heartbeatFailures, setHeartbeatFailures] = useState(0)
  const [logs, setLogs] = useState<ActivityLog[]>([])
  const previousKindRef = useRef<ActivityKind>('IDLE')

  function addLog(message: string) {
    const text = String(message || '').trim()
    if (!text) return
    setLogs(current => {
      const last = current[current.length - 1]
      if (last?.message === text) return current
      return [...current.slice(-19), { at: Date.now(), message: text }]
    })
  }

  useEffect(() => {
    if (!active) {
      previousKindRef.current = 'IDLE'
      setHeartbeat('IDLE')
      return
    }

    const started = Date.now()
    setStartedAt(started)
    setNow(started)
    setHeartbeat('CHECKING')
    setHeartbeatFailures(0)
    setLogs([])
    addLog(kind === 'ATTACHMENT_SUMMARY'
      ? '첨부 파일 통합 요구사항 분석을 시작했습니다.'
      : '사용자 요청을 Backend에 전달하고 AI 응답을 기다립니다.')
    previousKindRef.current = kind

    const tick = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(tick)
  }, [active, kind])

  useEffect(() => {
    if (!active) return undefined
    let cancelled = false

    const ping = async () => {
      try {
        setHeartbeat(current => current === 'OK' ? current : 'CHECKING')
        await api('/health')
        if (cancelled) return
        setHeartbeat('OK')
        setLastHeartbeatAt(Date.now())
        setHeartbeatFailures(0)
      } catch (cause: any) {
        if (cancelled) return
        setHeartbeat('FAIL')
        setHeartbeatFailures(value => value + 1)
        addLog(`Backend Heartbeat 실패: ${cause?.message || String(cause)}`)
      }
    }

    void ping()
    const timer = window.setInterval(() => void ping(), 5000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [active])

  useEffect(() => {
    if (!active) return
    if (attachmentCount && attachmentState.ready) addLog(`첨부 Context 준비 완료 (${attachmentState.successfulFiles || attachmentCount}개).`)
  }, [active, attachmentCount, attachmentState.ready, attachmentState.successfulFiles])

  useEffect(() => {
    if (!active) return
    if (databasePreviewLoading) addLog('DB 실시간 설계 초안 갱신을 시작했습니다.')
  }, [active, databasePreviewLoading])

  useEffect(() => {
    if (error) addLog(error)
  }, [error])

  const elapsedSeconds = startedAt ? Math.max(0, Math.floor((now - startedAt) / 1000)) : 0
  const delayed = active && elapsedSeconds >= 45
  const veryDelayed = active && elapsedSeconds >= 120
  const backendProblem = active && heartbeatFailures >= 2

  const currentTask = useMemo(() => {
    if (!active) return canRetry ? '이전 요청이 중단되었거나 실패했습니다.' : '대기 중'
    if (attachmentState.busy) return '첨부 파일 Context를 준비하고 있습니다.'
    if (kind === 'ATTACHMENT_SUMMARY') return '첨부 파일의 목적·기능·데이터·기술 구성을 통합 분석하고 있습니다.'
    if (databasePreviewLoading) return 'AI 응답을 기다리는 동안 DB 설계 초안을 갱신하고 있습니다.'
    return 'Backend가 요청을 처리 중이며 LLM 응답을 기다리고 있습니다.'
  }, [active, canRetry, attachmentState.busy, kind, databasePreviewLoading])

  const phases = [
    {
      label: '첨부 파일 등록',
      status: attachmentCount ? 'done' : 'skip',
      detail: attachmentCount ? `${attachmentCount}개 등록` : '첨부 없음',
    },
    {
      label: '첨부 Context 생성',
      status: !attachmentCount ? 'skip' : attachmentState.busy ? 'active' : attachmentState.ready ? 'done' : 'wait',
      detail: !attachmentCount ? '해당 없음' : attachmentState.busy ? `${attachmentState.overallProgress}%` : attachmentState.ready ? '준비 완료' : '대기',
    },
    {
      label: kind === 'ATTACHMENT_SUMMARY' ? '통합 요구사항 분석' : '사용자 요청 전송',
      status: active ? (attachmentState.busy ? 'wait' : 'done') : 'wait',
      detail: active && !attachmentState.busy ? '전송 완료' : '대기',
    },
    {
      label: 'Backend / LLM 처리',
      status: active && !attachmentState.busy ? 'active' : 'wait',
      detail: active && !attachmentState.busy ? (backendProblem ? 'Heartbeat 이상' : '응답 대기') : '대기',
    },
    {
      label: '요구사항 · DB 초안 반영',
      status: databasePreviewLoading ? 'active' : 'wait',
      detail: databasePreviewLoading ? 'DB 초안 갱신 중' : '응답 후 반영',
    },
    {
      label: '사용자 응답 표시',
      status: active ? 'wait' : canRetry ? 'error' : 'wait',
      detail: active ? '대기' : canRetry ? '미완료' : '대기',
    },
  ]

  if (!active && !canRetry && !error) return null

  return (
    <section className={`agent-activity-progress ${backendProblem ? 'backend-problem' : veryDelayed ? 'very-delayed' : delayed ? 'delayed' : ''}`}>
      <div className="agent-activity-head">
        <div>
          <strong>{active ? 'AI 작업 진행 중' : 'AI 작업 상태'}</strong>
          <small>{currentTask}</small>
        </div>
        <div className="agent-activity-time">
          <b>{active ? elapsedLabel(elapsedSeconds) : '-'}</b>
          <span className={`agent-heartbeat ${heartbeat.toLowerCase()}`}>
            Backend {heartbeat === 'OK' ? '정상' : heartbeat === 'FAIL' ? '확인 실패' : heartbeat === 'CHECKING' ? '확인 중' : '대기'}
          </span>
        </div>
      </div>

      <div className="agent-activity-phases">
        {phases.map((phase, index) => (
          <div className={`agent-activity-phase ${phase.status}`} key={phase.label}>
            <i>{phase.status === 'done' ? '✓' : phase.status === 'active' ? '●' : phase.status === 'error' ? '!' : phase.status === 'skip' ? '–' : '○'}</i>
            <span>{index + 1}. {phase.label}</span>
            <em>{phase.detail}</em>
          </div>
        ))}
      </div>

      <div className="agent-activity-current">
        <div><span>현재 작업</span><strong>{currentTask}</strong></div>
        <div><span>최근 Backend 확인</span><strong>{relativeSecondsLabel(lastHeartbeatAt, now)}</strong></div>
        {attachmentCount > 0 && <div><span>첨부 Context</span><strong>{attachmentState.ready ? '준비 완료' : `${attachmentState.overallProgress}%`}</strong></div>}
      </div>

      {delayed && !backendProblem && (
        <div className={`agent-activity-warning ${veryDelayed ? 'strong' : ''}`}>
          {veryDelayed
            ? '응답 대기가 2분을 넘었습니다. Backend는 살아 있지만 LLM 또는 외부 처리 지연 가능성이 있습니다.'
            : '응답이 평소보다 오래 걸리고 있습니다. Backend 상태를 계속 확인하고 있습니다.'}
        </div>
      )}
      {backendProblem && (
        <div className="agent-activity-warning strong">Backend Heartbeat가 연속 실패했습니다. 연결 문제 또는 Backend 중단 가능성을 확인해 주세요.</div>
      )}
      {error && <div className="agent-activity-error">{error}</div>}

      <div className="agent-activity-actions">
        {active && onCancel && <button type="button" className="danger" onClick={onCancel}>작업 취소</button>}
        {!active && canRetry && onRetry && <button type="button" onClick={onRetry}>현재 요청 다시 시도</button>}
        <details>
          <summary>상세 진행 로그</summary>
          <div className="agent-activity-log">
            {logs.length ? logs.map((row, index) => (
              <div key={`${row.at}-${index}`}><time>{new Date(row.at).toLocaleTimeString()}</time><span>{row.message}</span></div>
            )) : <small>기록된 진행 이벤트가 없습니다.</small>}
          </div>
        </details>
      </div>
    </section>
  )
}
