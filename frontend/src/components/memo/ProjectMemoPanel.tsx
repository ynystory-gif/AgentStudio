import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, saveBlobToOutput } from '../../api'
import { useMediaSession } from '../media/MediaSessionProvider'

type ProjectMemo = {
  id: string
  filePath: string
  title: string
  content: string
  createdAt: string
  updatedAt: string
}

type Props = {
  projectRoot: string
  activeFile?: string
  projectFiles?: string[]
  onAddLlmReference?: (reference: any) => boolean | void
  onOpenExternalMedia?: (url: string) => void
}

type SplitDragState = {
  pointerId: number
  startY: number
  startPercent: number
  height: number
}

const DEFAULT_LIST_PERCENT = 22
const MIN_LIST_PERCENT = 14
const MAX_LIST_PERCENT = 55

function normalizePath(value: string): string {
  return String(value || '').replace(/\\/g, '/').replace(/^\.\//, '').trim()
}

function memoFileKey(value: string): string {
  return normalizePath(value).toLocaleLowerCase('en-US')
}

function dedupeMemosByFile(items: ProjectMemo[]): ProjectMemo[] {
  const byFile = new Map<string, ProjectMemo>()
  for (const memo of items || []) {
    const filePath = normalizePath(memo.filePath)
    if (!filePath) continue
    const key = memoFileKey(filePath)
    const normalized = { ...memo, filePath }
    const previous = byFile.get(key)
    if (!previous || String(normalized.updatedAt || '') >= String(previous.updatedAt || '')) {
      byFile.set(key, normalized)
    }
  }
  return Array.from(byFile.values())
}

async function loadMemos(projectRoot: string): Promise<ProjectMemo[]> {
  if (!projectRoot) return []
  const result = await api<{ memos?: ProjectMemo[] }>(`/project-memos?root=${encodeURIComponent(projectRoot)}`)
  const parsed = Array.isArray(result?.memos) ? result.memos : []
  return dedupeMemosByFile(
    parsed
      .filter(Boolean)
      .map((item: any) => ({
        id: String(item.id || ''),
        filePath: normalizePath(item.filePath || ''),
        title: String(item.title || ''),
        content: String(item.content || ''),
        createdAt: String(item.createdAt || ''),
        updatedAt: String(item.updatedAt || '')
      }))
      .filter((item: ProjectMemo) => item.id && item.filePath)
  )
}

async function persistMemos(projectRoot: string, memos: ProjectMemo[]): Promise<void> {
  if (!projectRoot) return
  await api('/project-memos', {
    method: 'POST',
    body: JSON.stringify({ root: projectRoot, memos: dedupeMemosByFile(memos) })
  })
}

function newMemoId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `memo-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function fileName(path: string): string {
  const normalized = normalizePath(path)
  return normalized.split('/').filter(Boolean).pop() || normalized || '파일 미지정'
}

function formatUpdated(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function ProjectMemoPanel({ projectRoot, activeFile = '', projectFiles = [], onAddLlmReference, onOpenExternalMedia }: Props) {
  const mediaSession = useMediaSession()
  const [panelMode, setPanelMode] = useState<'MEMO' | 'LIVE'>('MEMO')
  const [liveSourceType, setLiveSourceType] = useState<'MICROPHONE' | 'SCREEN'>('MICROPHONE')
  const [liveEnableStt, setLiveEnableStt] = useState(true)
  const [externalMediaUrl, setExternalMediaUrl] = useState('')
  const [liveSummary, setLiveSummary] = useState('')
  const [liveSummaryLoading, setLiveSummaryLoading] = useState(false)
  const [liveSummaryError, setLiveSummaryError] = useState('')
  const [liveSummarySegmentCount, setLiveSummarySegmentCount] = useState(0)
  const [liveFileSaving, setLiveFileSaving] = useState<'' | 'TRANSCRIPT' | 'SUMMARY'>('')
  const [liveSavedFile, setLiveSavedFile] = useState<{ kind: 'TRANSCRIPT' | 'SUMMARY'; path: string; relativePath: string } | null>(null)
  const [recordingFileSaving, setRecordingFileSaving] = useState(false)
  const [recordingSavedPath, setRecordingSavedPath] = useState('')
  const [memos, setMemos] = useState<ProjectMemo[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [draftFile, setDraftFile] = useState('')
  const [draftTitle, setDraftTitle] = useState('')
  const [draftContent, setDraftContent] = useState('')
  const [filterMode, setFilterMode] = useState<'ALL' | 'CURRENT'>('ALL')
  const [status, setStatus] = useState('')
  const [listPercent, setListPercent] = useState(DEFAULT_LIST_PERCENT)
  const workspaceRef = useRef<HTMLDivElement | null>(null)
  const splitDragRef = useRef<SplitDragState | null>(null)

  const normalizedActiveFile = normalizePath(activeFile)
  const selectableFiles = useMemo(() => {
    const unique = new Set<string>()
    if (normalizedActiveFile) unique.add(normalizedActiveFile)
    for (const path of projectFiles || []) {
      const normalized = normalizePath(path)
      if (normalized) unique.add(normalized)
    }
    return Array.from(unique).sort((a, b) => a.localeCompare(b, 'ko'))
  }, [normalizedActiveFile, projectFiles])

  const selectedMemo = useMemo(
    () => memos.find(item => item.id === selectedId) || null,
    [memos, selectedId]
  )

  const memoForActiveFile = useMemo(
    () => normalizedActiveFile ? memos.find(item => memoFileKey(item.filePath) === memoFileKey(normalizedActiveFile)) || null : null,
    [memos, normalizedActiveFile]
  )

  const usedFileKeys = useMemo(
    () => new Set(memos.map(item => memoFileKey(item.filePath))),
    [memos]
  )

  const memoTargetFiles = useMemo(() => {
    if (selectedMemo) return [normalizePath(selectedMemo.filePath)]
    return selectableFiles.filter(path => !usedFileKeys.has(memoFileKey(path)))
  }, [selectableFiles, selectedMemo, usedFileKeys])

  useEffect(() => {
    let cancelled = false
    setLiveSummary('')
    setLiveSummaryError('')
    setLiveSummarySegmentCount(0)
    setLiveFileSaving('')
    setLiveSavedFile(null)
    setRecordingFileSaving(false)
    setRecordingSavedPath('')
    setSelectedId('')
    setDraftFile(normalizedActiveFile)
    setDraftTitle('')
    setDraftContent('')
    setStatus(projectRoot ? '메모를 불러오는 중…' : '')
    if (!projectRoot) {
      setMemos([])
      return () => { cancelled = true }
    }
    void loadMemos(projectRoot)
      .then(next => {
        if (cancelled) return
        setMemos(next)
        const current = normalizedActiveFile
          ? next.find(item => memoFileKey(item.filePath) === memoFileKey(normalizedActiveFile)) || null
          : null
        if (current) {
          setSelectedId(current.id)
          setDraftFile(current.filePath)
          setDraftTitle(current.title)
          setDraftContent(current.content)
        }
        setStatus('')
      })
      .catch(error => {
        if (cancelled) return
        setMemos([])
        setStatus(`메모 불러오기 실패: ${String((error as Error)?.message || error)}`)
      })
    return () => { cancelled = true }
  }, [projectRoot])

  useEffect(() => {
    if (!projectRoot || typeof window === 'undefined') {
      setListPercent(DEFAULT_LIST_PERCENT)
      return
    }
    const key = `agentstudio:project-memo-split:${projectRoot}`
    const stored = Number(window.localStorage.getItem(key))
    setListPercent(Number.isFinite(stored) && stored > 0
      ? clamp(stored, MIN_LIST_PERCENT, MAX_LIST_PERCENT)
      : DEFAULT_LIST_PERCENT)
  }, [projectRoot])

  useEffect(() => {
    if (!normalizedActiveFile) return
    const existing = memos.find(item => memoFileKey(item.filePath) === memoFileKey(normalizedActiveFile)) || null
    if (existing) {
      setSelectedId(existing.id)
      setDraftFile(existing.filePath)
      setDraftTitle(existing.title)
      setDraftContent(existing.content)
      return
    }
    setSelectedId('')
    setDraftFile(normalizedActiveFile)
    setDraftTitle('')
    setDraftContent('')
  }, [normalizedActiveFile])

  useEffect(() => {
    if (panelMode !== 'LIVE' || !projectRoot) return
    if (mediaSession.status === 'RECORDING' || mediaSession.status === 'STARTING' || mediaSession.status === 'STOPPING') return
    void mediaSession.loadProjectTranscript(projectRoot)
  }, [panelMode, projectRoot, mediaSession.status])

  useEffect(() => {
    if (String(mediaSession.transcriptText || '').trim()) return
    setLiveSummary('')
    setLiveSummaryError('')
    setLiveSummarySegmentCount(0)
  }, [mediaSession.transcriptText])

  const formatElapsed = (totalSeconds: number) => {
    const seconds = Math.max(0, Math.floor(Number(totalSeconds || 0)))
    const hh = String(Math.floor(seconds / 3600)).padStart(2, '0')
    const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')
    const ss = String(seconds % 60).padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  }

  const appendTranscriptToCurrentMemo = () => {
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!normalizedActiveFile) {
      setStatus('실시간 기록을 메모로 저장하려면 먼저 파일을 여세요.')
      setPanelMode('MEMO')
      return
    }
    const existing = memos.find(item => memoFileKey(item.filePath) === memoFileKey(normalizedActiveFile)) || null
    const header = `[실시간 기록 ${new Date().toLocaleString('ko-KR')}]`
    const nextContent = transcript ? `${header}\n${transcript}` : header
    if (existing) {
      setSelectedId(existing.id)
      setDraftFile(existing.filePath)
      setDraftTitle(existing.title || '실시간 기록')
      const base = existing.content || ''
      setDraftContent(base.trim() ? `${base.trimEnd()}\n\n${nextContent}` : nextContent)
    } else {
      setSelectedId('')
      setDraftFile(normalizedActiveFile)
      setDraftTitle('실시간 기록')
      setDraftContent(nextContent)
    }
    setStatus('실시간 기록을 현재 파일 메모에 넣었습니다. 저장 버튼을 눌러 확정하세요.')
    setPanelMode('MEMO')
  }

  const sendTranscriptToLlmReference = () => {
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!transcript) return
    const added = onAddLlmReference?.({
      path: normalizedActiveFile,
      text: transcript,
      start_line: 1,
      start_column: 1,
      end_line: 1,
      end_column: 1,
      source: 'live-transcript'
    })
    setStatus(added === false ? '이미 같은 실시간 기록이 LLM 참조 문구에 있습니다.' : '실시간 기록을 LLM 참조 문구에 추가했습니다.')
  }

  const startLiveRecording = async () => {
    setLiveSummary('')
    setLiveSummaryError('')
    setLiveSummarySegmentCount(0)
    const started = await mediaSession.start({
      projectRoot,
      sourceType: liveSourceType,
      enableStt: liveEnableStt,
      language: 'ko-KR'
    })
    if (!started) setStatus('녹음을 시작하지 못했습니다. 브라우저 권한과 입력 장치를 확인하세요.')
  }

  const summarizeLiveTranscript = async () => {
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!transcript || liveSummaryLoading) return
    setLiveSummaryLoading(true)
    setLiveSummaryError('')
    try {
      const result = await api<{ summary?: string; truncated?: boolean }>('/media-stt/summarize', {
        method: 'POST',
        body: JSON.stringify({ root: projectRoot, transcript })
      })
      const summary = String(result?.summary || '').trim()
      if (!summary) throw new Error('요약 결과가 비어 있습니다.')
      setLiveSummary(summary)
      setLiveSummarySegmentCount(mediaSession.transcriptSegments.length)
      setStatus(result?.truncated ? '긴 Transcript의 일부를 압축해 요약했습니다.' : '실시간 Transcript를 요약정리했습니다.')
    } catch (summaryError) {
      setLiveSummaryError(`요약정리 실패: ${String((summaryError as Error)?.message || summaryError)}`)
    } finally {
      setLiveSummaryLoading(false)
    }
  }

  const persistLiveTextFile = async (kind: 'TRANSCRIPT' | 'SUMMARY', text: string) => {
    const content = String(text || '').trim()
    if (!projectRoot) throw new Error('프로젝트를 먼저 선택하세요.')
    if (!content) throw new Error(kind === 'SUMMARY' ? '저장할 요약정리 내용이 없습니다.' : '저장할 실시간 Transcript가 없습니다.')
    const result = await api<{ path?: string; relative_path?: string }>('/media-stt/save-text', {
      method: 'POST',
      body: JSON.stringify({ root: projectRoot, kind: kind.toLowerCase(), text: content })
    })
    const savedPath = String(result?.path || '').trim()
    const relativePath = String(result?.relative_path || '').trim()
    if (!savedPath) throw new Error('Backend가 저장된 파일 경로를 반환하지 않았습니다.')
    setLiveSavedFile({ kind, path: savedPath, relativePath })
    setStatus(`${kind === 'SUMMARY' ? '요약정리' : '실시간 Transcript'} 텍스트 파일을 저장했습니다.`)
    return savedPath
  }

  const saveLiveTranscriptFile = async () => {
    if (liveFileSaving) return
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!transcript) {
      setStatus('저장할 실시간 Transcript가 없습니다.')
      return
    }
    setLiveFileSaving('TRANSCRIPT')
    try {
      await persistLiveTextFile('TRANSCRIPT', transcript)
    } catch (saveError) {
      setStatus(`실시간 Transcript 파일 저장 실패: ${String((saveError as Error)?.message || saveError)}`)
    } finally {
      setLiveFileSaving('')
    }
  }

  const saveLiveSummaryFile = async () => {
    if (liveFileSaving || liveSummaryLoading) return
    const transcript = String(mediaSession.transcriptText || '').trim()
    if (!transcript) {
      setStatus('요약정리할 실시간 Transcript가 없습니다.')
      return
    }
    setLiveFileSaving('SUMMARY')
    setLiveSummaryError('')
    try {
      const result = await api<{ summary?: string; truncated?: boolean }>('/media-stt/summarize', {
        method: 'POST',
        body: JSON.stringify({ root: projectRoot, transcript })
      })
      const summary = String(result?.summary || '').trim()
      if (!summary) throw new Error('요약 결과가 비어 있습니다.')
      setLiveSummary(summary)
      setLiveSummarySegmentCount(mediaSession.transcriptSegments.length)
      await persistLiveTextFile('SUMMARY', summary)
    } catch (saveError) {
      const message = String((saveError as Error)?.message || saveError)
      setLiveSummaryError(`요약정리 파일 저장 실패: ${message}`)
      setStatus(`요약정리 파일 저장 실패: ${message}`)
    } finally {
      setLiveFileSaving('')
    }
  }

  const saveRecordingFileToOutput = async () => {
    if (!mediaSession.recordingUrl || recordingFileSaving) return
    setRecordingFileSaving(true)
    try {
      const response = await fetch(mediaSession.recordingUrl)
      const blob = await response.blob()
      const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+$/, '').replace('T', '_')
      const saved = await saveBlobToOutput(blob, `recording_${stamp}.webm`, 'recordings', projectRoot)
      setRecordingSavedPath(saved.path)
      setStatus(`녹음 파일을 Output 경로에 저장했습니다: ${saved.path}`)
    } catch (saveError) {
      setStatus(`녹음 파일 저장 실패: ${String((saveError as Error)?.message || saveError)}`)
    } finally { setRecordingFileSaving(false) }
  }

  const visibleMemos = useMemo(() => {
    const sorted = [...memos].sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)))
    if (filterMode === 'CURRENT' && normalizedActiveFile) {
      return sorted.filter(item => memoFileKey(item.filePath) === memoFileKey(normalizedActiveFile))
    }
    return sorted
  }, [memos, filterMode, normalizedActiveFile])

  const loadMemo = (memo: ProjectMemo) => {
    setSelectedId(memo.id)
    setDraftFile(normalizePath(memo.filePath))
    setDraftTitle(memo.title)
    setDraftContent(memo.content)
    setStatus('메모를 불러왔습니다.')
  }

  const startNewMemo = () => {
    const target = normalizedActiveFile || memoTargetFiles[0] || selectableFiles.find(path => !usedFileKeys.has(memoFileKey(path))) || ''
    const existing = target ? memos.find(item => memoFileKey(item.filePath) === memoFileKey(target)) || null : null
    if (existing) {
      loadMemo(existing)
      setStatus('이 파일에는 이미 메모가 있습니다. 파일별 메모는 1개만 사용할 수 있습니다.')
      return
    }
    setSelectedId('')
    setDraftFile(target)
    setDraftTitle('')
    setDraftContent('')
    setStatus(target ? '새 파일 메모를 작성하세요.' : '메모를 만들 수 있는 파일을 선택하세요.')
  }

  const saveMemo = async () => {
    if (!projectRoot) {
      setStatus('프로젝트를 먼저 선택하세요.')
      return
    }
    const targetFile = normalizePath(draftFile || normalizedActiveFile)
    if (!targetFile) {
      setStatus('메모를 연결할 파일을 선택하세요.')
      return
    }
    const conflictingMemo = memos.find(item => memoFileKey(item.filePath) === memoFileKey(targetFile) && item.id !== selectedId)
    if (conflictingMemo) {
      setStatus('선택한 파일에는 이미 메모가 있습니다. 파일별 메모는 1개만 저장할 수 있습니다.')
      return
    }
    const content = String(draftContent || '')
    const title = String(draftTitle || '').trim() || content.trim().split(/\r?\n/)[0]?.slice(0, 60) || '메모'
    const now = new Date().toISOString()
    let next: ProjectMemo[]
    let id = selectedId
    if (selectedMemo) {
      next = memos.map(item => item.id === selectedMemo.id
        ? { ...item, filePath: targetFile, title, content, updatedAt: now }
        : item)
      id = selectedMemo.id
    } else {
      id = newMemoId()
      next = [{ id, filePath: targetFile, title, content, createdAt: now, updatedAt: now }, ...memos]
    }
    next = dedupeMemosByFile(next)
    try {
      await persistMemos(projectRoot, next)
      setMemos(next)
      setSelectedId(id)
      setDraftFile(targetFile)
      setDraftTitle(title)
      setStatus('메모를 저장했습니다.')
    } catch (error) {
      setStatus(`메모 저장 실패: ${String((error as Error)?.message || error)}`)
    }
  }

  const deleteMemo = async () => {
    if (!selectedMemo) return
    if (!window.confirm(`메모 "${selectedMemo.title || '메모'}"를 삭제하시겠습니까?`)) return
    const next = memos.filter(item => item.id !== selectedMemo.id)
    try {
      await persistMemos(projectRoot, next)
      setMemos(next)
      setSelectedId('')
      setDraftFile(normalizedActiveFile || selectableFiles.find(path => !next.some(item => memoFileKey(item.filePath) === memoFileKey(path))) || '')
      setDraftTitle('')
      setDraftContent('')
      setStatus('메모를 삭제했습니다.')
    } catch (error) {
      setStatus(`메모 삭제 실패: ${String((error as Error)?.message || error)}`)
    }
  }

  const onSplitterPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    const workspace = workspaceRef.current
    if (!workspace) return
    const rect = workspace.getBoundingClientRect()
    if (rect.height <= 0) return
    splitDragRef.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startPercent: listPercent,
      height: rect.height
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    event.preventDefault()
  }

  const onSplitterPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = splitDragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const deltaPercent = ((event.clientY - drag.startY) / Math.max(1, drag.height)) * 100
    setListPercent(clamp(drag.startPercent + deltaPercent, MIN_LIST_PERCENT, MAX_LIST_PERCENT))
  }

  const finishSplitterDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = splitDragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    splitDragRef.current = null
    try {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    } catch {
      // Pointer capture may already be released by the browser.
    }
    if (projectRoot && typeof window !== 'undefined') {
      window.localStorage.setItem(`agentstudio:project-memo-split:${projectRoot}`, String(listPercent))
    }
  }

  const renderLivePanel = () => (
    <div className="project-live-recording-panel">
      <div className="project-live-recording-state">
        <div>
          <span className={mediaSession.status === 'RECORDING' ? 'live-recording-dot active' : 'live-recording-dot'} />
          <strong>{mediaSession.status === 'RECORDING' ? '녹음 중' : mediaSession.status === 'STARTING' ? '녹음 준비 중' : mediaSession.status === 'STOPPING' ? '녹음 정지 중' : '녹음 대기'}</strong>
        </div>
        <b>{formatElapsed(mediaSession.elapsedSeconds)}</b>
      </div>

      <div className={`project-live-stage-flow stage-${mediaSession.transcriptStage.toLowerCase()}`} aria-label="Transcript 처리 상태">
        <span className={mediaSession.transcriptStage === 'COLLECTING' ? 'active collecting' : ''}><b>1</b> 수집 중</span>
        <i>›</i>
        <span className={mediaSession.transcriptStage === 'REFINING' ? 'active refining' : ''}><b>2</b> 보정 중</span>
        <i>›</i>
        <span className={mediaSession.transcriptStage === 'COMPLETED' ? 'active completed' : ''}><b>3</b> 완료</span>
        {mediaSession.transcriptStage === 'ERROR' && <em>처리 오류</em>}
      </div>

      {mediaSession.status === 'RECORDING' && mediaSession.projectRoot && mediaSession.projectRoot !== projectRoot && (
        <div className="project-live-project-lock">현재 녹음은 다른 프로젝트에 연결되어 있습니다. 프로젝트를 이동해도 기존 녹음 대상은 자동 변경되지 않습니다.<code>{mediaSession.projectRoot}</code></div>
      )}

      <div className="project-live-recording-options">
        <label>
          <span>입력</span>
          <select value={liveSourceType} onChange={event => setLiveSourceType(event.target.value === 'SCREEN' ? 'SCREEN' : 'MICROPHONE')} disabled={mediaSession.status !== 'IDLE'}>
            <option value="MICROPHONE">마이크 / 외부 음성</option>
            <option value="SCREEN">화면 / 시스템 오디오</option>
          </select>
        </label>
        <label className="project-live-stt-toggle">
          <input type="checkbox" checked={liveEnableStt} onChange={event => setLiveEnableStt(event.target.checked)} disabled={mediaSession.status !== 'IDLE'} />
          <span>실시간 텍스트 변환</span>
        </label>
      </div>

      <div className="project-live-media-launcher">
        <input
          value={externalMediaUrl}
          onChange={event => setExternalMediaUrl(event.target.value)}
          placeholder="YouTube 또는 외부 영상 URL"
          onKeyDown={event => {
            if (event.key === 'Enter' && externalMediaUrl.trim()) {
              event.preventDefault()
              onOpenExternalMedia?.(externalMediaUrl.trim())
            }
          }}
        />
        <button type="button" onClick={() => externalMediaUrl.trim() && onOpenExternalMedia?.(externalMediaUrl.trim())} disabled={!externalMediaUrl.trim() || !onOpenExternalMedia}>▶ 영상 열기</button>
      </div>

      <div className="project-live-recording-actions">
        {mediaSession.status === 'RECORDING' || mediaSession.status === 'STARTING' || mediaSession.status === 'STOPPING' ? (
          <button type="button" className="danger" onClick={() => void mediaSession.stop()} disabled={mediaSession.status !== 'RECORDING'}>■ 녹음 정지</button>
        ) : (
          <button type="button" className="primary" onClick={() => void startLiveRecording()}>● 녹음 시작</button>
        )}
        <span>{mediaSession.sttStatus}</span>
      </div>

      <div className="project-live-health" aria-label="실시간 음성 인식 상태">
        <div className="project-live-audio-meter-row">
          <span>음성 입력</span>
          <div className="project-live-audio-meter" aria-label={`음성 입력 레벨 ${Math.round(mediaSession.audioLevel * 100)}%`}>
            <i style={{ width: `${Math.max(0, Math.min(100, mediaSession.audioLevel * 100))}%` }} />
          </div>
          <b>{Math.round(mediaSession.audioLevel * 100)}%</b>
        </div>
        <div className="project-live-health-grid">
          <span>STT 엔진 <b>{mediaSession.sttEngine}</b></span>
          <span>마지막 인식 <b>{mediaSession.lastRecognizedAt ? new Date(mediaSession.lastRecognizedAt).toLocaleTimeString() : '-'}</b></span>
          <span>재연결 <b>{mediaSession.sttReconnectCount}회</b></span>
          <span className={mediaSession.sttDroppedChunks > 0 ? 'warn' : ''}>전송 누락 <b>{mediaSession.sttDroppedChunks}개</b></span>
        </div>
        {mediaSession.refineStatus === 'RUNNING' && <div className="project-live-refine-status running"><span className="spinner" />{mediaSession.refineMessage || '녹음 전체 정밀 보정 중…'}</div>}
        {mediaSession.refineStatus === 'DONE' && <div className="project-live-refine-status done">✓ {mediaSession.refineMessage || '정밀 보정 완료'}</div>}
        {mediaSession.refineStatus === 'ERROR' && <div className="project-live-refine-status error">⚠ {mediaSession.refineMessage || '정밀 보정 실패'}</div>}
      </div>

      {liveSourceType === 'SCREEN' && liveEnableStt && mediaSession.status !== 'RECORDING' && (
        <div className="project-live-stt-note strong">YouTube 음성을 텍스트로 변환하려면 <b>녹음 시작 → Chrome 탭 선택 → 탭 오디오 공유 ON</b>으로 시작하세요. ‘창’만 공유해 오디오 Track이 없으면 실시간 인식뿐 아니라 종료 후 정밀 보정도 텍스트를 만들 수 없습니다.</div>
      )}

      <div className="project-live-transcript" aria-live="polite">
        <div className="project-live-transcript-head">
          <div>
            <strong>실시간 Transcript</strong>
            <small>임시 인식은 즉시 표시되고, 정밀 보정 결과가 도착하면 같은 시간 구간을 교체합니다.</small>
          </div>
          <div className="project-live-transcript-head-actions">
            <span>{mediaSession.transcriptSegments.length}{mediaSession.interimSegment ? '+1' : ''}개 구간</span>
            <button type="button" className="save-file" onClick={() => void saveLiveTranscriptFile()} disabled={!mediaSession.transcriptText.trim() || Boolean(liveFileSaving)}>{liveFileSaving === 'TRANSCRIPT' ? '저장 중…' : '💾 파일 저장'}</button>
            <button type="button" className="save-file summary-file" onClick={() => void saveLiveSummaryFile()} disabled={!mediaSession.transcriptText.trim() || Boolean(liveFileSaving) || liveSummaryLoading}>{liveFileSaving === 'SUMMARY' ? '요약·저장 중…' : '💾 요약 파일 저장'}</button>
            <button type="button" className="summary" onClick={() => void summarizeLiveTranscript()} disabled={!mediaSession.transcriptText.trim() || liveSummaryLoading || Boolean(liveFileSaving)}>{liveSummaryLoading ? '요약 중…' : '✦ 요약정리'}</button>
          </div>
        </div>
        <div className="project-live-transcript-body">
          {mediaSession.transcriptSegments.length === 0 && !mediaSession.interimText && <small>녹음을 시작하면 Backend STT가 인식한 문장이 여기에 계속 누적됩니다.</small>}
          {mediaSession.transcriptSegments.map(segment => (
            <p key={segment.id} className={segment.refined ? 'refined' : 'collected'} title={segment.confidence == null ? '' : `인식 신뢰도 ${Math.round(segment.confidence * 100)}%`}>
              <time>{formatElapsed(Math.floor(segment.offsetMs / 1000))}</time>
              <span>{segment.text}</span>
              <em>{segment.refined ? '보정 완료' : '수집됨'}</em>
            </p>
          ))}
          {mediaSession.interimText && <p className="interim provisional">
            <time>{mediaSession.interimSegment ? formatElapsed(Math.floor(mediaSession.interimSegment.offsetMs / 1000)) : '…'}</time>
            <span>{mediaSession.interimText}</span>
            <em>수집 중</em>
          </p>}
        </div>
      </div>

      <div className="project-live-transcript-actions">
        <button type="button" onClick={appendTranscriptToCurrentMemo} disabled={!mediaSession.transcriptText.trim()}>현재 파일 메모에 넣기</button>
        <button type="button" onClick={sendTranscriptToLlmReference} disabled={!mediaSession.transcriptText.trim() || !onAddLlmReference}>LLM 참조 문구</button>
        <button type="button" onClick={() => void navigator.clipboard?.writeText?.(mediaSession.transcriptText)} disabled={!mediaSession.transcriptText.trim()}>텍스트 복사</button>
        <button type="button" onClick={() => void mediaSession.clearTranscript()} disabled={!mediaSession.transcriptText.trim() || mediaSession.status === 'RECORDING'}>기록 지우기</button>
      </div>

      {liveSavedFile && (
        <div className="project-live-save-path" title={liveSavedFile.path}>
          <strong>{liveSavedFile.kind === 'SUMMARY' ? '요약 파일 저장 경로' : 'Transcript 파일 저장 경로'}</strong>
          <code>{liveSavedFile.path}</code>
        </div>
      )}

      {(liveSummary || liveSummaryLoading || liveSummaryError) && (
        <div className={`project-live-summary ${liveSummaryError ? 'error' : ''}`}>
          <div className="project-live-summary-head">
            <div><strong>Transcript 요약정리</strong><small>{liveSummarySegmentCount > 0 ? `${liveSummarySegmentCount}개 구간 기준` : '현재 Transcript 기준'}</small></div>
            {liveSummary && <button type="button" onClick={() => void navigator.clipboard?.writeText?.(liveSummary)}>복사</button>}
          </div>
          {liveSummaryLoading && <div className="project-live-summary-loading"><span className="spinner" /> LLM이 현재까지 수집된 텍스트를 요약하고 있습니다.</div>}
          {liveSummaryError && <div className="project-live-summary-error">{liveSummaryError}</div>}
          {liveSummary && !liveSummaryLoading && <div className="project-live-summary-body">{liveSummary}</div>}
          {liveSummary && mediaSession.transcriptSegments.length > liveSummarySegmentCount && <div className="project-live-summary-stale">요약 이후 {mediaSession.transcriptSegments.length - liveSummarySegmentCount}개 구간이 추가되었습니다. 최신 내용까지 반영하려면 다시 ‘요약정리’를 누르세요.</div>}
        </div>
      )}

      {mediaSession.recordingUrl && (
        <button type="button" className="project-live-recording-download" onClick={() => void saveRecordingFileToOutput()} disabled={recordingFileSaving}>{recordingFileSaving ? '녹음 파일 저장 중…' : '녹음 파일 저장'}</button>
      )}
      {recordingSavedPath && (
        <div className="project-live-save-path" title={recordingSavedPath}><strong>녹음 파일 저장 경로</strong><code>{recordingSavedPath}</code></div>
      )}
      {mediaSession.error && <div className="project-memo-status error">{mediaSession.error}</div>}
      {status && <div className="project-memo-status">{status}</div>}
    </div>
  )

  if (!projectRoot) {
    return (
      <div className="project-memo-panel code-tab-panel">
        <div className="project-memo-empty">프로젝트를 선택하면 파일별 메모를 사용할 수 있습니다.</div>
      </div>
    )
  }

  return (
    <div className="project-memo-panel code-tab-panel">
      <div className="project-memo-toolbar">
        <div>
          <strong>{panelMode === 'LIVE' ? '실시간 기록' : '프로젝트 메모'}</strong>
          <small>{panelMode === 'LIVE' ? '화면을 이동해도 녹음과 STT 세션은 계속 유지됩니다.' : '파일별 메모 1개 · 자동 저장 대상은 프로젝트 내부'}</small>
        </div>
        {panelMode === 'MEMO' && <button type="button" onClick={startNewMemo}>+ 메모</button>}
      </div>

      <div className="project-memo-mode-tabs" role="tablist" aria-label="메모 기능">
        <button type="button" className={panelMode === 'MEMO' ? 'active' : ''} onClick={() => setPanelMode('MEMO')}>파일 메모</button>
        <button type="button" className={panelMode === 'LIVE' ? 'active' : ''} onClick={() => setPanelMode('LIVE')}>● 실시간 기록</button>
      </div>

      {panelMode === 'LIVE' ? renderLivePanel() : (<>
      <div className="project-memo-filter" role="group" aria-label="메모 목록 필터">
        <button type="button" className={filterMode === 'ALL' ? 'active' : ''} onClick={() => setFilterMode('ALL')}>전체 {memos.length}</button>
        <button
          type="button"
          className={filterMode === 'CURRENT' ? 'active' : ''}
          onClick={() => setFilterMode('CURRENT')}
          disabled={!normalizedActiveFile}
          title={normalizedActiveFile || '현재 열린 파일이 없습니다.'}
        >현재 파일 {memoForActiveFile ? 1 : 0}</button>
      </div>

      <div className="project-memo-workspace" ref={workspaceRef}>
        <div
          className="project-memo-list"
          aria-label="저장된 메모 목록"
          style={{ flexBasis: `${listPercent}%` }}
        >
          {visibleMemos.length === 0 && (
            <div className="project-memo-empty">저장된 메모가 없습니다.</div>
          )}
          {visibleMemos.map(memo => (
            <button
              type="button"
              key={memo.id}
              className={memo.id === selectedId ? 'project-memo-list-item active' : 'project-memo-list-item'}
              onClick={() => loadMemo(memo)}
              title={memo.filePath}
            >
              <span className="project-memo-list-title">{memo.title || '메모'}</span>
              <span className="project-memo-list-file">{fileName(memo.filePath)}</span>
              <span className="project-memo-list-time">{formatUpdated(memo.updatedAt)}</span>
            </button>
          ))}
        </div>

        <div
          className="project-memo-splitter"
          role="separator"
          aria-label="메모 목록과 입력 영역 크기 조절"
          aria-orientation="horizontal"
          aria-valuemin={MIN_LIST_PERCENT}
          aria-valuemax={MAX_LIST_PERCENT}
          aria-valuenow={Math.round(listPercent)}
          title="위아래로 드래그하여 메모 목록과 입력 영역 크기를 조절합니다."
          onPointerDown={onSplitterPointerDown}
          onPointerMove={onSplitterPointerMove}
          onPointerUp={finishSplitterDrag}
          onPointerCancel={finishSplitterDrag}
        >
          <span />
        </div>

        <div className="project-memo-editor">
          <label>
            <span>파일</span>
            <select
              value={draftFile}
              disabled={Boolean(selectedMemo)}
              onChange={event => setDraftFile(event.target.value)}
              title={selectedMemo ? '저장된 메모의 파일은 변경할 수 없습니다. 파일별 메모는 1개입니다.' : '메모를 저장할 파일을 선택합니다.'}
            >
              {!draftFile && <option value="">파일 선택</option>}
              {memoTargetFiles.map(path => <option key={path} value={path}>{path}</option>)}
              {draftFile && !memoTargetFiles.includes(draftFile) && <option value={draftFile}>{draftFile}</option>}
            </select>
          </label>
          <label>
            <span>제목</span>
            <input
              value={draftTitle}
              onChange={event => setDraftTitle(event.target.value)}
              placeholder="메모 제목"
            />
          </label>
          <label className="project-memo-content-label">
            <span>메모</span>
            <textarea
              value={draftContent}
              onChange={event => setDraftContent(event.target.value)}
              onKeyDown={event => {
                if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
                  event.preventDefault()
                  void saveMemo()
                }
              }}
              placeholder="코드 수정 중 잠시 보관할 내용을 입력하세요. Ctrl+S로 저장할 수 있습니다."
            />
          </label>
          <div className="project-memo-actions">
            <button type="button" className="primary" onClick={() => void saveMemo()}>저장</button>
            <button type="button" onClick={startNewMemo}>새 메모</button>
            <button type="button" className="danger" onClick={() => void deleteMemo()} disabled={!selectedMemo}>삭제</button>
          </div>
          {status && <div className="project-memo-status">{status}</div>}
        </div>
      </div>
      </>)}
    </div>
  )
}
