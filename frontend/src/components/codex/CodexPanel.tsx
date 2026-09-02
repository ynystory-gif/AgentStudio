import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, runtimeInfo } from '../../api'
import { AiAttachmentPicker, type AiAttachment, type AiAttachmentAnalysisState } from '../ai/AiAttachmentPicker'
import type {
  CodexModel,
  CodexRateLimitSnapshot,
  CodexRateLimitWindow,
  CodexServerRequest,
  CodexStatus,
  CodexThread,
  CodexTranscriptItem
} from '../../types/codex'

type CodexProposalBlock = {
  type: 'explanation' | 'code'
  content: string
  language?: string
}

type CodexCodeProposal = {
  source: 'codex'
  question: string
  responseText: string
  blocks: CodexProposalBlock[]
  codeBlockCount: number
  activeFile: string
  createdAt: string
}

type Props = {
  projectRoot: string
  activeFile?: string
  onCodeProposal?: (proposal: CodexCodeProposal) => void
}

type CodexWireEvent = {
  type?: string
  method?: string
  params?: Record<string, any>
  status?: CodexStatus
  request_id?: string
  message?: string
  [key: string]: any
}

const nowId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

function modelId(model: CodexModel): string {
  return String(model.model || model.id || '')
}

function modelLabel(model: CodexModel): string {
  return String(model.displayName || model.model || model.id || 'Codex')
}

function effortValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') {
    const row = value as Record<string, unknown>
    return String(row.reasoningEffort || row.effort || row.value || row.label || '')
  }
  return ''
}

function remainingPercent(window?: CodexRateLimitWindow | null): string {
  if (!window || typeof window.usedPercent !== 'number') return '-'
  return `${Math.max(0, 100 - Number(window.usedPercent)).toFixed(0)}%`
}

function usageWindowLabel(window: CodexRateLimitWindow | null | undefined, fallback: string): string {
  const minutes = Number(window?.windowDurationMins || 0)
  if (!minutes) return fallback
  if (minutes === 300) return '5시간'
  if (minutes === 10080) return '1주'
  if (minutes % 10080 === 0) return `${Math.round(minutes / 10080)}주`
  if (minutes % 1440 === 0) return `${Math.round(minutes / 1440)}일`
  if (minutes % 60 === 0) return `${Math.round(minutes / 60)}시간`
  return `${minutes}분`
}

function formatUsageReset(window?: CodexRateLimitWindow | null): string {
  const value = Number(window?.resetsAt || 0)
  if (!value) return '-'
  const date = new Date(value * 1000)
  if (Number.isNaN(date.getTime())) return '-'
  const duration = Number(window?.windowDurationMins || 0)
  if (duration >= 1440) {
    return date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  }
  return date.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })
}

function userInputQuestions(request: CodexServerRequest): Array<Record<string, any>> {
  const questions = request.params.questions
  return Array.isArray(questions) ? questions.filter(row => row && typeof row === 'object') as Array<Record<string, any>> : []
}

function approvalTitle(request: CodexServerRequest): string {
  if (request.method.includes('commandExecution')) return '명령 실행 승인 요청'
  if (request.method.includes('fileChange')) return '파일 변경 승인 요청'
  if (request.method.includes('requestUserInput')) return 'Codex 추가 입력 요청'
  return 'Codex 승인 요청'
}

function toText(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(toText).filter(Boolean).join(' ')
  if (value == null) return ''
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}


function parseCodexCodeProposal(text: string): { blocks: CodexProposalBlock[]; codeBlockCount: number } | null {
  const source = String(text || '')
  if (!source.includes('```')) return null
  const blocks: CodexProposalBlock[] = []
  const pattern = /```([^\n`]*)\n?([\s\S]*?)```/g
  let cursor = 0
  let match: RegExpExecArray | null
  let codeBlockCount = 0
  while ((match = pattern.exec(source)) !== null) {
    const explanation = source.slice(cursor, match.index).trim()
    if (explanation) blocks.push({ type: 'explanation', content: explanation })
    const content = String(match[2] || '').replace(/\s+$/g, '')
    if (content.trim()) {
      codeBlockCount += 1
      blocks.push({
        type: 'code',
        language: String(match[1] || '').trim().split(/\s+/)[0] || 'text',
        content
      })
    }
    cursor = pattern.lastIndex
  }
  const tail = source.slice(cursor).trim()
  if (tail) blocks.push({ type: 'explanation', content: tail })
  return codeBlockCount > 0 ? { blocks, codeBlockCount } : null
}

function transcriptFromThread(thread: any): CodexTranscriptItem[] {
  const items: CodexTranscriptItem[] = []
  const turns = Array.isArray(thread?.turns) ? thread.turns : []
  for (const turn of turns) {
    const turnItems = Array.isArray(turn?.items) ? turn.items : []
    for (const item of turnItems) {
      const type = String(item?.type || '')
      if (type === 'userMessage') {
        const text = toText(item?.content || item?.text)
        if (text) items.push({ id: String(item?.id || nowId('user')), kind: 'user', text, createdAt: Date.now() })
      } else if (type === 'agentMessage') {
        const text = toText(item?.text || item?.content)
        if (text) items.push({ id: String(item?.id || nowId('assistant')), kind: 'assistant', text, createdAt: Date.now() })
      } else if (type === 'commandExecution') {
        items.push({
          id: String(item?.id || nowId('cmd')),
          kind: 'command',
          title: 'Command',
          command: toText(item?.command),
          cwd: String(item?.cwd || ''),
          text: toText(item?.aggregatedOutput || ''),
          status: String(item?.status || ''),
          createdAt: Date.now()
        })
      } else if (type === 'fileChange') {
        items.push({
          id: String(item?.id || nowId('file')),
          kind: 'file',
          title: 'File change',
          text: toText(item?.changes || ''),
          status: String(item?.status || ''),
          createdAt: Date.now()
        })
      }
    }
  }
  return items
}

export function CodexPanel({ projectRoot, activeFile = '', onCodeProposal }: Props) {
  const [status, setStatus] = useState<CodexStatus>({ installed: false, running: false, initialized: false })
  const [busy, setBusy] = useState(false)
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<AiAttachment[]>([])
  const [attachmentAnalysis, setAttachmentAnalysis] = useState<AiAttachmentAnalysisState>({ busy: false, ready: true, overallProgress: 100, failedFiles: 0, successfulFiles: 0, files: [] })
  const [threadId, setThreadId] = useState('')
  const [turnId, setTurnId] = useState('')
  const [threads, setThreads] = useState<CodexThread[]>([])
  const [threadMenuOpen, setThreadMenuOpen] = useState(false)
  const [transcript, setTranscript] = useState<CodexTranscriptItem[]>([])
  const [pendingApprovals, setPendingApprovals] = useState<CodexServerRequest[]>([])
  const [model, setModel] = useState('')
  const [effort, setEffort] = useState('medium')
  const [detailOpen, setDetailOpen] = useState(false)
  const [usageRefreshing, setUsageRefreshing] = useState(false)
  const [loginUrl, setLoginUrl] = useState('')
  const [lastDiff, setLastDiff] = useState('')
  const [reasoning, setReasoning] = useState('')
  const [approvalAnswers, setApprovalAnswers] = useState<Record<string, string>>({})
  const transcriptRef = useRef<HTMLDivElement | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const mountedRef = useRef(true)
  const activeAssistantIdRef = useRef('')
  const autoStartAttemptedRef = useRef('')
  const settingsMenuRef = useRef<HTMLDivElement | null>(null)
  const lastSubmittedQuestionRef = useRef('')
  const activeFileRef = useRef(activeFile)

  useEffect(() => {
    activeFileRef.current = activeFile
  }, [activeFile])

  const models = status.models || []
  const selectedModel = useMemo(() => models.find(row => modelId(row) === model) || null, [models, model])
  const efforts = useMemo(() => {
    const values = (selectedModel?.supportedReasoningEfforts || []).map(effortValue).filter(Boolean)
    return values.length ? values : ['low', 'medium', 'high']
  }, [selectedModel])

  useEffect(() => {
    if (!selectedModel) return
    const preferred = String(selectedModel.defaultReasoningEffort || '')
    setEffort(current => {
      if (efforts.includes(current)) return current
      if (preferred && efforts.includes(preferred)) return preferred
      return efforts[0] || 'medium'
    })
  }, [selectedModel, efforts])

  const pushTranscript = useCallback((item: CodexTranscriptItem) => {
    setTranscript(prev => [...prev, item].slice(-300))
  }, [])

  const appendAssistantDelta = useCallback((delta: string) => {
    if (!delta) return
    const existingId = activeAssistantIdRef.current
    if (!existingId) {
      const id = nowId('assistant')
      activeAssistantIdRef.current = id
      setTranscript(prev => [...prev, { id, kind: 'assistant', text: delta, createdAt: Date.now() }])
      return
    }
    setTranscript(prev => prev.map(item => item.id === existingId ? { ...item, text: item.text + delta } : item))
  }, [])

  const refreshStatus = useCallback(async () => {
    try {
      const next = await api<CodexStatus>(`/codex/status?root=${encodeURIComponent(projectRoot || '')}`)
      if (!mountedRef.current) return
      setStatus(next)
      setModel(current => {
        if (current || !next.models?.length) return current
        const preferred = next.models.find(row => row.isDefault) || next.models[0]
        return preferred ? modelId(preferred) : current
      })
      setThreadId(current => current || next.current_thread_id || '')
      if (next.active_turn_id) setTurnId(next.active_turn_id)
      setPendingApprovals(next.pending_requests || [])
    } catch (error: any) {
      if (!mountedRef.current) return
      setStatus(prev => ({ ...prev, last_error: error?.message || String(error) }))
    }
  }, [projectRoot])

  const loadThreads = useCallback(async () => {
    try {
      const result = await api<{ data: CodexThread[] }>(`/codex/threads?root=${encodeURIComponent(projectRoot || '')}&limit=20`)
      if (mountedRef.current) setThreads(result.data || [])
    } catch { /* thread history is supplementary */ }
  }, [projectRoot])

  const startCodex = useCallback(async () => {
    if (!projectRoot) return
    setBusy(true)
    try {
      const next = await api<CodexStatus>('/codex/start', { method: 'POST', body: JSON.stringify({ root: projectRoot }) })
      setStatus(next)
      if (next.models?.length) {
        const preferred = next.models.find(row => row.isDefault) || next.models[0]
        if (preferred) {
          setModel(current => current || modelId(preferred))
        }
      }
    } catch (error: any) {
      setStatus(prev => ({ ...prev, last_error: error?.message || String(error) }))
    } finally {
      setBusy(false)
    }
  }, [projectRoot])

  useEffect(() => {
    mountedRef.current = true
    refreshStatus()
    return () => { mountedRef.current = false }
  }, [refreshStatus])

  useEffect(() => {
    if (!projectRoot || status.enabled === false || !status.installed || status.running || busy) return
    if (autoStartAttemptedRef.current === projectRoot) return
    autoStartAttemptedRef.current = projectRoot
    startCodex()
  }, [projectRoot, status.enabled, status.installed, status.running, busy, startCodex])

  useEffect(() => {
    if (autoStartAttemptedRef.current && autoStartAttemptedRef.current !== projectRoot) {
      autoStartAttemptedRef.current = ''
    }
  }, [projectRoot])

  useEffect(() => {
    if (!detailOpen) return
    const closeOnPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (target && !settingsMenuRef.current?.contains(target)) setDetailOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDetailOpen(false)
    }
    document.addEventListener('mousedown', closeOnPointerDown)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnPointerDown)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [detailOpen])

  useEffect(() => {
    if (status.initialized) loadThreads()
  }, [status.initialized, loadThreads])

  useEffect(() => {
    const info = runtimeInfo()
    const url = info.wsBase.replace(/\/ws$/, '/codex/events')
    const ws = new WebSocket(url)
    socketRef.current = ws

    ws.onmessage = event => {
      let wire: CodexWireEvent
      try { wire = JSON.parse(event.data) as CodexWireEvent } catch { return }
      if (wire.type === 'codex/state' && wire.status) {
        setStatus(wire.status)
        return
      }
      if (wire.type === 'codex/error' || wire.type === 'codex/process-exited') {
        if (wire.message) pushTranscript({ id: nowId('error'), kind: 'error', text: wire.message, createdAt: Date.now() })
        if (wire.type === 'codex/process-exited') {
          setTurnId('')
          setThreadId('')
          activeAssistantIdRef.current = ''
          setPendingApprovals([])
          setApprovalAnswers({})
        }
        refreshStatus()
        return
      }
      if (wire.type === 'codex/server-request') {
        const req: CodexServerRequest = {
          request_id: String(wire.request_id || ''),
          method: String(wire.method || ''),
          params: wire.params || {}
        }
        setPendingApprovals(prev => prev.some(row => row.request_id === req.request_id) ? prev : [...prev, req])
        return
      }
      if (wire.type !== 'codex/event') return
      const method = String(wire.method || '')
      const params = wire.params || {}

      if (method === 'account/updated' || method === 'account/login/completed') {
        setTimeout(refreshStatus, 250)
        return
      }
      if (method === 'serverRequest/resolved') {
        const requestId = String(params.requestId || '')
        setPendingApprovals(prev => prev.filter(row => row.request_id !== requestId))
        setApprovalAnswers(prev => {
          const next = { ...prev }
          Object.keys(next).filter(key => key.startsWith(`${requestId}:`)).forEach(key => delete next[key])
          return next
        })
        return
      }
      if (method === 'turn/started') {
        const id = String(params.turn?.id || '')
        if (id) setTurnId(id)
        activeAssistantIdRef.current = ''
        setReasoning('')
        return
      }
      if (method === 'turn/completed') {
        setTurnId('')
        activeAssistantIdRef.current = ''
        const turn = params.turn || {}
        if (turn.status === 'failed' && turn.error?.message) {
          pushTranscript({ id: nowId('error'), kind: 'error', text: String(turn.error.message), createdAt: Date.now() })
        }
        loadThreads()
        return
      }
      if (method === 'item/agentMessage/delta') {
        appendAssistantDelta(String(params.delta || ''))
        return
      }
      if (method === 'item/reasoning/summaryTextDelta') {
        setReasoning(prev => (prev + String(params.delta || '')).slice(-6000))
        return
      }
      if (method === 'item/commandExecution/outputDelta') {
        const itemId = String(params.itemId || '')
        const delta = String(params.delta || '')
        setTranscript(prev => prev.map(item => item.id === itemId ? { ...item, text: item.text + delta } : item))
        return
      }
      if (method === 'turn/diff/updated') {
        setLastDiff(String(params.diff || ''))
        return
      }
      if (method === 'item/started' || method === 'item/completed') {
        const item = params.item || {}
        const type = String(item.type || '')
        const id = String(item.id || nowId(type || 'item'))
        const completed = method === 'item/completed'
        if (type === 'agentMessage' && completed) {
          const text = toText(item.text || item.content)
          if (text) {
            const parsedProposal = parseCodexCodeProposal(text)
            if (parsedProposal && onCodeProposal) {
              const activeId = activeAssistantIdRef.current
              onCodeProposal({
                source: 'codex',
                question: lastSubmittedQuestionRef.current,
                responseText: text,
                blocks: parsedProposal.blocks,
                codeBlockCount: parsedProposal.codeBlockCount,
                activeFile: activeFileRef.current,
                createdAt: new Date().toISOString()
              })
              setTranscript(prev => {
                const filtered = activeId ? prev.filter(row => row.id !== activeId) : prev.filter(row => row.id !== id)
                return [...filtered, {
                  id: nowId('proposal'),
                  kind: 'assistant',
                  text: `코드가 포함된 답변을 AI 변경 제안으로 등록했습니다. 코드 블록 ${parsedProposal.codeBlockCount}개`,
                  createdAt: Date.now()
                }]
              })
              activeAssistantIdRef.current = ''
            } else {
              const activeId = activeAssistantIdRef.current
              if (activeId) {
                setTranscript(prev => prev.map(row => row.id === activeId ? { ...row, text } : row))
              } else {
                setTranscript(prev => [...prev, { id, kind: 'assistant', text, createdAt: Date.now() }])
              }
            }
          }
        } else if (type === 'commandExecution') {
          const row: CodexTranscriptItem = {
            id,
            kind: 'command',
            title: completed ? '명령 실행 결과' : '명령 실행',
            command: toText(item.command),
            cwd: String(item.cwd || ''),
            text: toText(item.aggregatedOutput || ''),
            status: String(item.status || (completed ? 'completed' : 'inProgress')),
            createdAt: Date.now()
          }
          setTranscript(prev => {
            const exists = prev.some(x => x.id === id)
            return exists ? prev.map(x => x.id === id ? row : x) : [...prev, row]
          })
        } else if (type === 'fileChange') {
          const row: CodexTranscriptItem = {
            id,
            kind: 'file',
            title: completed ? '파일 변경 결과' : '파일 변경',
            text: toText(item.changes || ''),
            status: String(item.status || (completed ? 'completed' : 'inProgress')),
            createdAt: Date.now()
          }
          setTranscript(prev => {
            const exists = prev.some(x => x.id === id)
            return exists ? prev.map(x => x.id === id ? row : x) : [...prev, row]
          })
        }
      }
    }

    return () => {
      if (socketRef.current === ws) socketRef.current = null
      try { ws.close() } catch { /* noop */ }
    }
  }, [appendAssistantDelta, loadThreads, onCodeProposal, pushTranscript, refreshStatus])

  useEffect(() => {
    const element = transcriptRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [transcript, pendingApprovals, reasoning])

  async function loginChatGPT() {
    const popup = window.open('about:blank', '_blank')
    setBusy(true)
    try {
      const result = await api<any>('/codex/login/chatgpt', { method: 'POST', body: JSON.stringify({ root: projectRoot }) })
      const url = String(result.authUrl || result.auth_url || '')
      setLoginUrl(url)
      if (popup && url) popup.location.href = url
      else if (url) window.open(url, '_blank', 'noopener,noreferrer')
      if (!url && popup) popup.close()
    } catch (error: any) {
      if (popup) popup.close()
      setStatus(prev => ({ ...prev, last_error: error?.message || String(error) }))
    } finally {
      setBusy(false)
    }
  }

  async function createThread(): Promise<string> {
    const result = await api<{ thread: any }>('/codex/thread/start', {
      method: 'POST',
      body: JSON.stringify({ root: projectRoot, model, effort })
    })
    const id = String(result.thread?.id || '')
    if (!id) throw new Error('Codex thread id를 받지 못했습니다.')
    setThreadId(id)
    setTranscript([])
    setLastDiff('')
    setReasoning('')
    activeAssistantIdRef.current = ''
    return id
  }

  async function newConversation() {
    if (turnId) return
    setThreadId('')
    setTranscript([])
    setLastDiff('')
    setReasoning('')
    activeAssistantIdRef.current = ''
    setThreadMenuOpen(false)
  }

  async function resumeThread(thread: CodexThread) {
    if (!thread.id || turnId) return
    setBusy(true)
    try {
      const result = await api<{ thread: any }>('/codex/thread/resume', {
        method: 'POST',
        body: JSON.stringify({ thread_id: thread.id, root: projectRoot })
      })
      setThreadId(thread.id)
      setTranscript(transcriptFromThread(result.thread))
      setLastDiff('')
      setReasoning('')
      activeAssistantIdRef.current = ''
      setThreadMenuOpen(false)
    } catch (error: any) {
      pushTranscript({ id: nowId('error'), kind: 'error', text: error?.message || String(error), createdAt: Date.now() })
    } finally {
      setBusy(false)
    }
  }

  async function sendMessage() {
    const typedText = input.trim()
    const text = typedText || (attachments.length ? '첨부한 참고 파일의 내용을 분석하고 핵심 내용을 정리해줘.' : '')
    if (!text || busy || turnId || !status.initialized || !projectRoot) return
    if (attachments.length && !attachmentAnalysis.ready) return
    setInput('')
    lastSubmittedQuestionRef.current = text
    const attachmentLabel = attachments.length
      ? `\n\n📎 참고 파일: ${attachments.map(item => item.name).join(', ')}`
      : ''
    pushTranscript({ id: nowId('user'), kind: 'user', text: text + attachmentLabel, createdAt: Date.now() })
    setBusy(true)
    try {
      const targetThread = threadId || await createThread()
      const result = await api<{ turn: any; attachment_warnings?: string[] }>('/codex/turn/start', {
        method: 'POST',
        body: JSON.stringify({
          thread_id: targetThread,
          root: projectRoot,
          text,
          model,
          effort,
          attachment_ids: attachments.map(item => item.attachment_id),
        })
      })
      if (Array.isArray(result.attachment_warnings) && result.attachment_warnings.length) {
        pushTranscript({
          id: nowId('error'),
          kind: 'error',
          text: `참고 파일 알림: ${result.attachment_warnings.join(' / ')}`,
          createdAt: Date.now(),
        })
      }
      const id = String(result.turn?.id || '')
      if (id) setTurnId(id)
    } catch (error: any) {
      pushTranscript({ id: nowId('error'), kind: 'error', text: error?.message || String(error), createdAt: Date.now() })
    } finally {
      setBusy(false)
    }
  }

  async function interrupt() {
    if (!threadId || !turnId) return
    try {
      await api('/codex/turn/interrupt', {
        method: 'POST',
        body: JSON.stringify({ thread_id: threadId, turn_id: turnId })
      })
    } catch (error: any) {
      pushTranscript({ id: nowId('error'), kind: 'error', text: error?.message || String(error), createdAt: Date.now() })
    }
  }

  async function resolveApproval(request: CodexServerRequest, decision: string) {
    try {
      await api('/codex/approval', {
        method: 'POST',
        body: JSON.stringify({ request_id: request.request_id, decision, payload: {} })
      })
      setPendingApprovals(prev => prev.filter(row => row.request_id !== request.request_id))
      setApprovalAnswers(prev => {
        const next = { ...prev }
        Object.keys(next).filter(key => key.startsWith(`${request.request_id}:`)).forEach(key => delete next[key])
        return next
      })
    } catch (error: any) {
      pushTranscript({ id: nowId('error'), kind: 'error', text: error?.message || String(error), createdAt: Date.now() })
    }
  }

  async function resolveUserInput(request: CodexServerRequest) {
    const questions = userInputQuestions(request)
    const answers: Record<string, { answers: string[] }> = {}
    for (const question of questions) {
      const id = String(question.id || '')
      if (!id) continue
      const value = approvalAnswers[`${request.request_id}:${id}`] || ''
      answers[id] = { answers: value ? [value] : [] }
    }
    try {
      await api('/codex/approval', {
        method: 'POST',
        body: JSON.stringify({ request_id: request.request_id, decision: 'accept', payload: { answers } })
      })
      setPendingApprovals(prev => prev.filter(row => row.request_id !== request.request_id))
      setApprovalAnswers(prev => {
        const next = { ...prev }
        Object.keys(next).filter(key => key.startsWith(`${request.request_id}:`)).forEach(key => delete next[key])
        return next
      })
    } catch (error: any) {
      pushTranscript({ id: nowId('error'), kind: 'error', text: error?.message || String(error), createdAt: Date.now() })
    }
  }

  function copyInstallCommand() {
    const command = status.windows_install_command || status.npm_install_command || ''
    if (command) navigator.clipboard?.writeText(command).catch(() => {})
  }

  const loggedIn = !!status.account
  const plan = String(status.account?.planType || '').toUpperCase()
  const usageBucket: CodexRateLimitSnapshot | undefined = status.rate_limits?.rateLimits
    || Object.values(status.rate_limits?.rateLimitsByLimitId || {})[0]

  async function refreshCodexUsage(force = true) {
    if (!loggedIn || usageRefreshing) return
    setUsageRefreshing(true)
    try {
      const result = await api<any>(`/codex/rate-limits?force=${force ? 'true' : 'false'}`)
      if (!result?.ok && !result?.rate_limits) {
        throw new Error(result?.message || result?.error || 'Codex 사용량을 확인할 수 없습니다.')
      }
      await refreshStatus()
    } catch (error: any) {
      setStatus(prev => ({ ...prev, rate_limits_error: error?.message || String(error) }))
    } finally {
      if (mountedRef.current) setUsageRefreshing(false)
    }
  }

  function toggleSettingsMenu() {
    const opening = !detailOpen
    setDetailOpen(opening)
    if (opening) {
      setThreadMenuOpen(false)
      if (loggedIn) void refreshCodexUsage(true)
      else void refreshStatus()
    }
  }

  if (!projectRoot) {
    return <div className="codex-panel code-tab-panel"><div className="codex-empty"><b>Codex</b><span>먼저 프로젝트를 선택하세요.</span></div></div>
  }

  if (status.enabled === false) {
    return <div className="codex-panel code-tab-panel">
      <div className="codex-empty">
        <div className="codex-mark">⌁</div>
        <b>Codex 사용이 꺼져 있습니다</b>
        <span>시스템 설정 → Codex / ChatGPT 계정에서 Codex 사용을 켜고 설정을 저장하세요.</span>
        <button type="button" onClick={() => { window.location.href = '/system' }}>시스템 설정 열기</button>
        <button type="button" className="secondary" onClick={refreshStatus}>상태 다시 확인</button>
      </div>
    </div>
  }

  if (!status.installed) {
    return <div className="codex-panel code-tab-panel">
      <div className="codex-empty codex-install-empty">
        <div className="codex-mark">⌁</div>
        <b>Codex CLI가 필요합니다</b>
        <span>VS Code Codex와 같은 app-server 방식으로 연결하려면 Codex CLI를 설치해야 합니다.</span>
        <code>{status.windows_install_command || 'Codex 설치 명령을 확인할 수 없습니다.'}</code>
        <button type="button" onClick={copyInstallCommand}>설치 명령 복사</button>
        <button type="button" className="secondary" onClick={refreshStatus}>설치 확인</button>
      </div>
    </div>
  }

  return <div className="codex-panel code-tab-panel">
    <div className="codex-toolbar">
      <div className="codex-brand">
        <span className={status.initialized ? 'codex-status-dot online' : 'codex-status-dot'}></span>
        <strong>Codex</strong>
        {plan && <span className="codex-plan-badge">{plan}</span>}
      </div>
      <div className="codex-toolbar-actions">
        <button type="button" title="새 대화" onClick={newConversation} disabled={!!turnId}>＋</button>
        <div className="codex-thread-menu-wrap">
          <button type="button" title="최근 대화" onClick={() => { setDetailOpen(false); setThreadMenuOpen(v => !v); loadThreads() }}>⌄</button>
          {threadMenuOpen && <div className="codex-thread-menu">
            <div className="codex-thread-menu-head">최근 대화</div>
            {threads.length ? threads.map(row => <button type="button" key={row.id} onClick={() => resumeThread(row)}>
              <b>{row.name || 'Codex 대화'}</b>
              <small>{row.id.slice(0, 12)}</small>
            </button>) : <span>저장된 대화가 없습니다.</span>}
          </div>}
        </div>
        <div className="codex-settings-menu-wrap" ref={settingsMenuRef}>
          <button type="button" title="Codex 설정 및 남은 사용량" aria-expanded={detailOpen} onClick={toggleSettingsMenu}>⚙</button>
          {detailOpen && <div className="codex-usage-popover">
            <div className="codex-usage-account">
              <div className="codex-usage-avatar">{String(status.account?.email || 'C').slice(0, 1).toUpperCase()}</div>
              <div>
                <strong>{status.account?.email || 'Codex'}</strong>
                <span>{plan ? `ChatGPT ${plan}` : 'ChatGPT Codex'}</span>
              </div>
            </div>

            <div className="codex-usage-section">
              <div className="codex-usage-section-title">
                <span>◔</span><strong>남은 사용량</strong>
                <button type="button" title="사용량 새로고침" onClick={() => void refreshCodexUsage(true)} disabled={usageRefreshing || !loggedIn}>
                  {usageRefreshing ? '…' : '↻'}
                </button>
              </div>
              {usageBucket ? <div className="codex-usage-compact-list">
                <div className="codex-usage-compact-row">
                  <span>{usageWindowLabel(usageBucket.primary, '5시간')}</span>
                  <b>{remainingPercent(usageBucket.primary)}</b>
                  <small>{formatUsageReset(usageBucket.primary)}</small>
                </div>
                <div className="codex-usage-compact-row">
                  <span>{usageWindowLabel(usageBucket.secondary, '1주')}</span>
                  <b>{remainingPercent(usageBucket.secondary)}</b>
                  <small>{formatUsageReset(usageBucket.secondary)}</small>
                </div>
                {usageBucket.individualLimit && <div className="codex-usage-compact-row">
                  <span>개별 한도</span>
                  <b>{usageBucket.individualLimit.remainingPercent ?? '-'}%</b>
                  <small>{usageBucket.individualLimit.resetsAt ? new Date(usageBucket.individualLimit.resetsAt * 1000).toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' }) : '-'}</small>
                </div>}
              </div> : <div className="codex-usage-empty">
                {loggedIn ? (status.rate_limits_error || '사용량 정보를 확인하는 중입니다.') : 'ChatGPT 계정을 연결하면 남은 사용량이 표시됩니다.'}
              </div>}
              {status.rate_limits?.rateLimitResetCredits?.availableCount != null && status.rate_limits.rateLimitResetCredits.availableCount > 0 && <div className="codex-reset-credit">
                <span>재설정 {status.rate_limits.rateLimitResetCredits.availableCount}회 가능</span><b>›</b>
              </div>}
            </div>

            <div className="codex-usage-menu-divider" />
            <details className="codex-usage-technical">
              <summary>Codex 상세 정보</summary>
              <div><span>CLI</span><b>{status.version || '확인 중'}</b></div>
              <div><span>프로세스</span><b>{status.running ? `PID ${status.pid || '-'}` : '중지'}</b></div>
              <div><span>프로젝트</span><b title={projectRoot}>{projectRoot}</b></div>
              {activeFile && <div><span>현재 파일</span><b title={activeFile}>{activeFile}</b></div>}
            </details>
            <button type="button" className="codex-usage-system-settings" onClick={() => { window.location.href = '/system' }}>
              <span>⚙</span><strong>Codex 설정</strong><small>시스템 설정 열기</small>
            </button>
            {(status.rate_limits_error || status.last_error) && <div className="codex-usage-error">{status.rate_limits_error || status.last_error}</div>}
          </div>}
        </div>
      </div>
    </div>

    {!status.initialized && <div className="codex-connect-card">
      <b>Codex app-server를 시작하는 중입니다.</b>
      <span>{status.last_error || '잠시 기다리거나 다시 시작해 주세요.'}</span>
      <button type="button" disabled={busy} onClick={startCodex}>{busy ? '시작 중…' : 'Codex 다시 시작'}</button>
    </div>}

    {status.initialized && !loggedIn && status.requires_openai_auth !== false && <div className="codex-login-card">
      <div className="codex-mark">⌁</div>
      <b>ChatGPT로 Codex 사용</b>
      <span>현재 ChatGPT 구독 계정으로 로그인합니다. AgentStudio는 비밀번호를 저장하지 않습니다.</span>
      <button type="button" onClick={loginChatGPT} disabled={busy}>{busy ? '로그인 준비 중…' : 'ChatGPT로 로그인'}</button>
      {loginUrl && <button type="button" className="linkish" onClick={() => window.open(loginUrl, '_blank', 'noopener,noreferrer')}>로그인 페이지 다시 열기</button>}
    </div>}

    {status.initialized && (loggedIn || status.requires_openai_auth === false) && <>
      <div className="codex-context-strip">
        <span title={projectRoot}>⌂ {projectRoot.split(/[\\/]/).filter(Boolean).pop() || projectRoot}</span>
        {activeFile && <span title={activeFile}>◫ {activeFile.split(/[\\/]/).pop()}</span>}
      </div>

      <div className="codex-transcript" ref={transcriptRef}>
        {!transcript.length && <div className="codex-welcome">
          <div className="codex-mark">⌁</div>
          <strong>무엇을 만들까요?</strong>
          <span>현재 프로젝트를 기준으로 코드 설명, 수정, 테스트, 리팩터링을 요청할 수 있습니다.</span>
          <button type="button" onClick={() => setInput('현재 프로젝트 구조를 분석하고 개선할 부분을 알려줘.')}>프로젝트 분석</button>
          <button type="button" onClick={() => setInput('현재 열린 파일을 검토하고 오류 가능성을 찾아줘.')}>현재 파일 검토</button>
        </div>}

        {transcript.map(item => <div className={`codex-message ${item.kind}`} key={item.id}>
          {item.kind === 'user' && <div className="codex-message-label">나</div>}
          {item.kind === 'assistant' && <div className="codex-message-label">Codex</div>}
          {(item.kind === 'command' || item.kind === 'file') && <div className="codex-activity-head">
            <b>{item.kind === 'command' ? '⌘' : 'Δ'} {item.title}</b>
            <span>{item.status}</span>
          </div>}
          {item.command && <code className="codex-command">{item.command}</code>}
          {item.cwd && <small className="codex-cwd">{item.cwd}</small>}
          <div className="codex-message-body">{item.text || (item.kind === 'command' ? '실행 중…' : '')}</div>
        </div>)}

        {reasoning && <details className="codex-reasoning" open={!!turnId}>
          <summary>{turnId ? '작업 중' : '작업 요약'}</summary>
          <div>{reasoning}</div>
        </details>}

        {lastDiff && <details className="codex-diff-card">
          <summary>변경 내용 보기</summary>
          <pre>{lastDiff}</pre>
        </details>}

        {pendingApprovals.map(request => {
          const isUserInput = request.method === 'item/tool/requestUserInput'
          const questions = isUserInput ? userInputQuestions(request) : []
          const allAnswered = !questions.length || questions.every(question => {
            const id = String(question.id || '')
            return !!approvalAnswers[`${request.request_id}:${id}`]?.trim()
          })
          return <div className="codex-approval-card" key={request.request_id}>
            <strong>{approvalTitle(request)}</strong>
            {isUserInput ? <div className="codex-user-input-questions">
              {questions.map((question, questionIndex) => {
                const questionId = String(question.id || '')
                const answerKey = `${request.request_id}:${questionId}`
                const options = Array.isArray(question.options) ? question.options : []
                const answer = approvalAnswers[answerKey] || ''
                return <div className="codex-user-input-question" key={questionId || `question-${questionIndex}`}>
                  {question.header && <b>{String(question.header)}</b>}
                  <p>{String(question.question || '')}</p>
                  {!!options.length && <div className="codex-user-input-options">
                    {options.map((option: any) => <button
                      type="button"
                      key={String(option.label || '')}
                      className={answer === String(option.label || '') ? 'active' : ''}
                      onClick={() => setApprovalAnswers(prev => ({ ...prev, [answerKey]: String(option.label || '') }))}
                      title={String(option.description || '')}
                    >{String(option.label || '')}</button>)}
                  </div>}
                  {(question.isOther !== false || !options.length) && <input
                    type={question.isSecret ? 'password' : 'text'}
                    value={options.some((option: any) => String(option.label || '') === answer) ? '' : answer}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) => setApprovalAnswers(prev => ({ ...prev, [answerKey]: event.target.value }))}
                    placeholder={options.length ? '기타 답변' : '답변 입력'}
                  />}
                </div>
              })}
              <div className="codex-approval-actions">
                <button type="button" onClick={() => resolveUserInput(request)} disabled={!allAnswered}>답변 보내기</button>
              </div>
            </div> : <>
              {request.params.reason && <p>{String(request.params.reason)}</p>}
              {request.params.command && <code>{toText(request.params.command)}</code>}
              {request.params.cwd && <small>{String(request.params.cwd)}</small>}
              {!request.params.command && request.method.includes('fileChange') && <pre>{toText(request.params)}</pre>}
              <div className="codex-approval-actions">
                <button type="button" onClick={() => resolveApproval(request, 'accept')}>승인</button>
                <button type="button" className="secondary" onClick={() => resolveApproval(request, 'acceptForSession')}>이번 세션 승인</button>
                <button type="button" className="danger" onClick={() => resolveApproval(request, 'decline')}>거부</button>
              </div>
            </>}
          </div>
        })}
      </div>

      <div className="codex-composer">
        <AiAttachmentPicker
          attachments={attachments}
          onChange={setAttachments}
          projectRoot={projectRoot}
          initialPath={projectRoot}
          disabled={busy || !!turnId}
          compact
          label="참고 파일 선택"
          title="Codex가 함께 분석할 참고 파일을 선택하세요."
          maxFiles={12}
          analysisPurpose="Codex 참고 파일 분석 준비"
          analysisActive={busy || !!turnId}
          onAnalysisStateChange={setAttachmentAnalysis}
        />
        <textarea
          value={input}
          onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setInput(event.target.value)}
          onKeyDown={(event: React.KeyboardEvent<HTMLTextAreaElement>) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              sendMessage()
            }
          }}
          placeholder="Codex에게 작업을 요청하세요"
          disabled={busy}
        />
        <div className="codex-composer-footer">
          <div className="codex-selectors">
            <select value={model} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setModel(event.target.value)} title="Codex 모델">
              {!models.length && <option value="">기본 모델</option>}
              {models.map(row => <option key={modelId(row)} value={modelId(row)}>{modelLabel(row)}</option>)}
            </select>
            <select value={effort} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setEffort(event.target.value)} title="Reasoning effort">
              {efforts.map(value => <option value={value} key={value}>{value}</option>)}
            </select>
          </div>
          {turnId
            ? <button type="button" className="codex-stop-button" onClick={interrupt} title="작업 중지">■</button>
            : <button type="button" className="codex-send-button" onClick={sendMessage} disabled={(!input.trim() && !attachments.length) || busy || (attachments.length > 0 && !attachmentAnalysis.ready)} title="전송">↑</button>}
        </div>
      </div>
    </>}
  </div>
}
