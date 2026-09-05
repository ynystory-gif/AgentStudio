import { asLegacyError } from '../../utils/errors'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api'

export type AiAttachment = {
  attachment_id: string
  path: string
  name: string
  size: number
  extension?: string
  mime_type?: string
  project_relative_path?: string
}

export type AiAttachmentAnalysisFile = {
  attachment_id: string
  name: string
  size?: number
  status: 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED'
  progress: number
  stage: string
  message: string
  content_type?: string
  content_chars?: number
  cached?: boolean
}

export type AiAttachmentAnalysisState = {
  busy: boolean
  ready: boolean
  overallProgress: number
  failedFiles: number
  successfulFiles: number
  files: AiAttachmentAnalysisFile[]
}

type Props = {
  attachments: AiAttachment[]
  onChange: (attachments: AiAttachment[]) => void
  projectRoot?: string
  initialPath?: string
  disabled?: boolean
  compact?: boolean
  label?: string
  title?: string
  maxFiles?: number
  analysisPurpose?: string
  analysisActive?: boolean
  onAnalysisStateChange?: (state: AiAttachmentAnalysisState) => void
}

type JobResponse = {
  id?: string
  status?: string
  progress?: number
  message?: string
  result?: {
    analysis?: {
      files?: AiAttachmentAnalysisFile[]
      overall_progress?: number
      failed_files?: number
      successful_files?: number
    }
    warnings?: string[]
  }
}

function formatBytes(value: number): string {
  const bytes = Math.max(0, Number(value) || 0)
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function normalizePath(value: string): string {
  return String(value || '').replace(/\\/g, '/').toLocaleLowerCase()
}

function terminal(status: string): boolean {
  return status === 'SUCCESS' || status === 'FAILED'
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve: LegacyValue) => window.setTimeout(resolve, ms))
}

export function AiAttachmentPicker({
  attachments,
  onChange,
  projectRoot = '',
  initialPath = '',
  disabled = false,
  compact = false,
  label = '파일 선택',
  title = 'AI가 분석할 참고 파일을 선택하세요.',
  maxFiles = 12,
  analysisPurpose = 'AI 참고 파일 분석 준비',
  analysisActive = false,
  onAnalysisStateChange,
}: Props) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [analysisBusy, setAnalysisBusy] = useState(false)
  const [analysisFiles, setAnalysisFiles] = useState<Record<string, AiAttachmentAnalysisFile>>({})
  const analysisRunRef = useRef(0)
  const attachmentsRef = useRef(attachments)

  useEffect(() => {
    attachmentsRef.current = attachments
    const activeIds = new Set(attachments.map((item: LegacyValue) => item.attachment_id))
    setAnalysisFiles((current: LegacyValue) => {
      let changed = false
      const next: Record<string, AiAttachmentAnalysisFile> = {}
      for (const [key, value] of Object.entries(current)) {
        if (activeIds.has(key)) next[key] = value as AiAttachmentAnalysisFile
        else changed = true
      }
      return changed ? next : current
    })
  }, [attachments])

  const analysisState = useMemo<AiAttachmentAnalysisState>(() => {
    const files = attachments.map((item: LegacyValue) => analysisFiles[item.attachment_id] || {
      attachment_id: item.attachment_id,
      name: item.name,
      size: item.size,
      status: 'QUEUED' as const,
      progress: 0,
      stage: '대기',
      message: '분석 대기 중',
    })
    const ready = files.length === 0 || files.every((item: LegacyValue) => terminal(item.status))
    const overallProgress = files.length
      ? Math.round(files.reduce((sum: LegacyValue, item: LegacyValue) => sum + Math.max(0, Math.min(100, Number(item.progress) || 0)), 0) / files.length)
      : 100
    return {
      busy: analysisBusy,
      ready,
      overallProgress,
      failedFiles: files.filter((item: LegacyValue) => item.status === 'FAILED').length,
      successfulFiles: files.filter((item: LegacyValue) => item.status === 'SUCCESS').length,
      files,
    }
  }, [analysisBusy, analysisFiles, attachments])

  useEffect(() => {
    onAnalysisStateChange?.(analysisState)
  }, [analysisState, onAnalysisStateChange])

  async function release(ids: string[]) {
    if (!ids.length) return
    try {
      await api('/ai/attachments/release', {
        method: 'POST',
        body: JSON.stringify({ attachment_ids: ids }),
      })
    } catch {
      // Registry entries also expire automatically. UI removal must not fail
      // just because the release request could not reach the backend.
    }
  }

  function applyAnalysisSnapshot(rows: AiAttachmentAnalysisFile[] | undefined) {
    if (!Array.isArray(rows) || !rows.length) return
    const activeIds = new Set(attachmentsRef.current.map((item: LegacyValue) => item.attachment_id))
    setAnalysisFiles((current: LegacyValue) => {
      const next = { ...current }
      for (const row of rows) {
        const id = String(row?.attachment_id || '')
        if (!id || !activeIds.has(id)) continue
        next[id] = {
          ...row,
          progress: Math.max(0, Math.min(100, Number(row.progress) || 0)),
        }
      }
      return next
    })
  }

  async function analyzePending(pending: AiAttachment[]) {
    if (!pending.length || analysisBusy) return
    const runId = analysisRunRef.current + 1
    analysisRunRef.current = runId
    setAnalysisBusy(true)
    setMessage('')
    setAnalysisFiles((current: LegacyValue) => {
      const next = { ...current }
      for (const item of pending) {
        next[item.attachment_id] = {
          attachment_id: item.attachment_id,
          name: item.name,
          size: item.size,
          status: 'QUEUED',
          progress: 0,
          stage: '대기',
          message: '분석 대기 중',
        }
      }
      return next
    })

    try {
      const created = await api<JobResponse>('/ai/attachments/analyze', {
        method: 'POST',
        body: JSON.stringify({
          attachment_ids: pending.map((item: LegacyValue) => item.attachment_id),
          purpose: analysisPurpose,
        }),
      })
      const jobId = String(created.id || '')
      if (!jobId) throw new Error('첨부 파일 분석 Job ID를 받지 못했습니다.')

      for (let attempt = 0; attempt < 1200; attempt += 1) {
        if (analysisRunRef.current !== runId) return
        const job = await api<JobResponse>(`/jobs/${encodeURIComponent(jobId)}`)
        applyAnalysisSnapshot(job.result?.analysis?.files)
        const status = String(job.status || '')
        if (status === 'SUCCESS') {
          applyAnalysisSnapshot(job.result?.analysis?.files)
          const warnings = Array.isArray(job.result?.warnings) ? job.result?.warnings : []
          if (warnings.length) setMessage(warnings.join(' / '))
          return
        }
        if (status === 'FAILED' || status === 'CANCELLED') {
          throw new Error(job.message || `첨부 파일 분석 작업이 ${status} 상태로 종료되었습니다.`)
        }
        await delay(180)
      }
      throw new Error('첨부 파일 분석 준비 시간이 너무 오래 걸리고 있습니다.')
    } catch (error) {
      const failure = asLegacyError(error).message || String(error)
      const pendingIds = new Set(pending.map((item: LegacyValue) => item.attachment_id))
      setAnalysisFiles((current: LegacyValue) => {
        const next = { ...current }
        for (const item of pending) {
          const previous = next[item.attachment_id]
          if (previous && terminal(previous.status)) continue
          if (!pendingIds.has(item.attachment_id)) continue
          next[item.attachment_id] = {
            attachment_id: item.attachment_id,
            name: item.name,
            size: item.size,
            status: 'FAILED',
            progress: 100,
            stage: '실패',
            message: failure,
          }
        }
        return next
      })
      setMessage(failure)
    } finally {
      if (analysisRunRef.current === runId) setAnalysisBusy(false)
    }
  }

  useEffect(() => {
    if (analysisBusy || !attachments.length) return
    const pending = attachments.filter((item: LegacyValue) => {
      const state = analysisFiles[item.attachment_id]
      return !state || !terminal(state.status)
    })
    if (pending.length) void analyzePending(pending)
    // analyzePending intentionally reads the latest state from refs. Keeping
    // this effect dependency list explicit prevents an analysis loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachments, analysisFiles, analysisBusy, analysisPurpose])

  async function pick() {
    if (disabled || busy || analysisBusy) return
    setBusy(true)
    setMessage('')
    try {
      const result = await api<{
        ok?: boolean
        cancelled?: boolean
        message?: string
        attachments?: AiAttachment[]
        rejected?: Array<{ name?: string; message?: string }>
      }>('/ai/attachments/pick', {
        method: 'POST',
        body: JSON.stringify({
          title,
          initial_path: initialPath || projectRoot || '',
          project_root: projectRoot || '',
          max_files: Math.max(1, Math.min(maxFiles, 30)),
        }),
      })

      if (result.cancelled) return
      const incoming = Array.isArray(result.attachments) ? result.attachments : []
      const next = [...attachments]
      const duplicateIds: string[] = []
      for (const row of incoming) {
        const key = normalizePath(row.path)
        const existingIndex = next.findIndex((item: LegacyValue) => normalizePath(item.path) === key)
        if (existingIndex >= 0) {
          duplicateIds.push(row.attachment_id)
          continue
        }
        if (next.length >= maxFiles) {
          duplicateIds.push(row.attachment_id)
          continue
        }
        next.push(row)
      }
      if (duplicateIds.length) void release(duplicateIds)
      onChange(next)

      const rejected = Array.isArray(result.rejected) ? result.rejected : []
      if (rejected.length) {
        setMessage(rejected.map((row: LegacyValue) => `${row.name || '파일'}: ${row.message || '등록 제외'}`).join(' / '))
      } else if (incoming.length && next.length === attachments.length) {
        setMessage('이미 등록된 파일입니다.')
      }
    } catch (error) {
      setMessage(asLegacyError(error).message || String(error))
    } finally {
      setBusy(false)
    }
  }

  function remove(attachmentId: string) {
    analysisRunRef.current += 1
    onChange(attachments.filter((item: LegacyValue) => item.attachment_id !== attachmentId))
    setAnalysisBusy(false)
    void release([attachmentId])
  }

  function clear() {
    analysisRunRef.current += 1
    const ids = attachments.map((item: LegacyValue) => item.attachment_id)
    onChange([])
    setAnalysisFiles({})
    setAnalysisBusy(false)
    void release(ids)
  }

  const showProgress = attachments.length > 0
  const overallLabel = analysisActive && analysisState.ready
    ? '첨부 Context 준비 완료 · 현재 AI 요청에 사용 중'
    : analysisState.ready && attachments.length > 0
      ? '첨부 Context 준비 완료 · 요구사항 정리 대기'
    : analysisState.busy
      ? `첨부 파일 분석 준비 ${analysisState.overallProgress}%`
      : analysisState.failedFiles
        ? `분석 준비 완료 · 성공 ${analysisState.successfulFiles} / 실패 ${analysisState.failedFiles}`
        : '첨부 파일 분석 준비 완료'

  return (
    <div className={`ai-attachment-picker ${compact ? 'compact' : ''}`}>
      <div className="ai-attachment-toolbar">
        <button
          type="button"
          className="ai-attachment-pick-button"
          onClick={pick}
          disabled={disabled || busy || analysisBusy || attachments.length >= maxFiles}
          title={`${title} 여러 파일을 한 번에 선택할 수 있습니다.`}
        >
          <span aria-hidden="true">📎</span>
          {busy ? '선택 중...' : label}
        </button>
        {attachments.length > 0 && (
          <>
            <span className="ai-attachment-count">참고 파일 {attachments.length}개</span>
            <button type="button" className="ai-attachment-clear" onClick={clear} disabled={disabled || analysisBusy}>전체 제거</button>
          </>
        )}
      </div>

      {showProgress && (
        <div className={`ai-attachment-analysis ${analysisState.failedFiles ? 'has-failure' : ''}`}>
          <div className="ai-attachment-analysis-head">
            <strong>{overallLabel}</strong>
            <span>{analysisState.overallProgress}%</span>
          </div>
          <div className="ai-attachment-overall-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={analysisState.overallProgress}>
            <div className="ai-attachment-overall-fill" style={{ width: `${analysisState.overallProgress}%` }} />
          </div>
          <div className="ai-attachment-progress-list" aria-label="파일별 AI 분석 준비 진행률">
            {analysisState.files.map((item: LegacyValue) => {
              const activeLabel = analysisActive && item.status === 'SUCCESS' ? '현재 AI 요청에 사용 중' : item.stage
              return <div className={`ai-attachment-progress-row ${item.status.toLowerCase()}`} key={item.attachment_id} title={item.message}>
                <div className="ai-attachment-progress-meta">
                  <span className="ai-attachment-name" title={attachments.find((row: LegacyValue) => row.attachment_id === item.attachment_id)?.path || item.name}>{item.name}</span>
                  <small>{formatBytes(item.size || 0)}</small>
                  <b>{activeLabel}</b>
                  <em>{item.progress}%</em>
                  <button
                    type="button"
                    aria-label={`${item.name} 첨부 제거`}
                    title="첨부 제거"
                    onClick={() => remove(item.attachment_id)}
                    disabled={disabled || analysisBusy}
                  >×</button>
                </div>
                <div className="ai-attachment-file-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.progress}>
                  <div className="ai-attachment-file-fill" style={{ width: `${item.progress}%` }} />
                </div>
                <div className="ai-attachment-stage-message">{analysisActive && item.status === 'SUCCESS' ? '준비된 파일 Context를 현재 AI 요청에 포함하고 있습니다.' : (item.status === 'SUCCESS' ? 'Context 준비 완료. 추출된 Context를 캐시했으며 같은 첨부 ID는 다시 읽지 않습니다.' : item.message)}</div>
              </div>
            })}
          </div>
        </div>
      )}

      {message && <div className="ai-attachment-message">{message}</div>}
    </div>
  )
}
