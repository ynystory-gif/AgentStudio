import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, getAuthToken, runtimeInfo } from '../../api'

type MediaSourceType = 'MICROPHONE' | 'SCREEN'
type MediaSessionStatus = 'IDLE' | 'STARTING' | 'RECORDING' | 'STOPPING' | 'ERROR'
type RefineStatus = 'IDLE' | 'RUNNING' | 'DONE' | 'ERROR'
type TranscriptStage = 'IDLE' | 'COLLECTING' | 'REFINING' | 'COMPLETED' | 'ERROR'

type TranscriptSegment = {
  id: string
  text: string
  createdAt: string
  offsetMs: number
  endOffsetMs?: number
  confidence?: number | null
  source?: string
  refined?: boolean
  provisional?: boolean
}

type StartMediaSessionOptions = {
  projectRoot: string
  sourceType: MediaSourceType
  enableStt: boolean
  language?: string
}

type MediaSessionContextValue = {
  status: MediaSessionStatus
  sourceType: MediaSourceType
  projectRoot: string
  startedAt: string
  elapsedSeconds: number
  enableStt: boolean
  sttSupported: boolean
  sttStatus: string
  sttEngine: string
  audioLevel: number
  lastRecognizedAt: string
  sttReconnectCount: number
  sttDroppedChunks: number
  refineStatus: RefineStatus
  refineMessage: string
  transcriptStage: TranscriptStage
  interimText: string
  interimSegment: TranscriptSegment | null
  transcriptSegments: TranscriptSegment[]
  transcriptText: string
  recordingUrl: string
  recordingMimeType: string
  error: string
  start: (options: StartMediaSessionOptions) => Promise<boolean>
  stop: () => Promise<void>
  clearTranscript: () => Promise<void>
  loadProjectTranscript: (projectRoot: string) => Promise<void>
}

const MediaSessionContext = createContext<MediaSessionContextValue | null>(null)
const TARGET_STT_SAMPLE_RATE = 16_000

function nowIso() {
  return new Date().toISOString()
}

function makeSegmentId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `segment-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function formatTranscript(segments: TranscriptSegment[], interimText = '', interimSegment: TranscriptSegment | null = null) {
  const formatOffset = (offsetMs: number) => {
    const seconds = Math.max(0, Math.floor(Number(offsetMs || 0) / 1000))
    const hh = String(Math.floor(seconds / 3600)).padStart(2, '0')
    const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')
    const ss = String(seconds % 60).padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  }
  const rows = [...segments]
    .sort((a, b) => Number(a.offsetMs || 0) - Number(b.offsetMs || 0))
    .map(segment => `[${formatOffset(segment.offsetMs)}] ${segment.text}`)
  if (interimSegment?.text?.trim()) {
    rows.push(`[${formatOffset(interimSegment.offsetMs)}] ${interimSegment.text.trim()}`)
  } else if (interimText.trim()) {
    rows.push(interimText.trim())
  }
  return rows.join('\n')
}

function rangesOverlap(a: TranscriptSegment, b: TranscriptSegment, toleranceMs = 160) {
  const aStart = Math.max(0, Number(a.offsetMs || 0))
  const aEnd = Math.max(aStart, Number(a.endOffsetMs ?? aStart))
  const bStart = Math.max(0, Number(b.offsetMs || 0))
  const bEnd = Math.max(bStart, Number(b.endOffsetMs ?? bStart))
  return aStart <= bEnd + toleranceMs && bStart <= aEnd + toleranceMs
}

function replaceTranscriptRange(
  current: TranscriptSegment[],
  replacements: TranscriptSegment[],
  rangeStartMs: number,
  rangeEndMs: number
) {
  const start = Math.max(0, Number(rangeStartMs || 0))
  const end = Math.max(start, Number(rangeEndMs || start))
  const retained = current.filter(segment => {
    const segmentStart = Math.max(0, Number(segment.offsetMs || 0))
    const segmentEnd = Math.max(segmentStart, Number(segment.endOffsetMs ?? segmentStart))
    return segmentEnd < start || segmentStart > end
  })
  return [...retained, ...replacements]
    .filter(segment => String(segment.text || '').trim())
    .sort((a, b) => Number(a.offsetMs || 0) - Number(b.offsetMs || 0))
}

function getSpeechRecognitionConstructor(): any {
  if (typeof window === 'undefined') return null
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null
}

function buildSttWebSocketUrl(projectRoot: string, language: string) {
  const info = runtimeInfo()
  const wsApiBase = String(info.apiBase || '').replace(/^http/i, 'ws').replace(/\/$/, '')
  const token = getAuthToken()
  const params = new URLSearchParams({
    root: projectRoot,
    language: language || 'ko-KR',
    sample_rate: String(TARGET_STT_SAMPLE_RATE)
  })
  if (token) params.set('access_token', token)
  return `${wsApiBase}/media-stt/stream?${params.toString()}`
}

function downsampleToPcm16(input: Float32Array, inputSampleRate: number, outputSampleRate = TARGET_STT_SAMPLE_RATE) {
  if (!input.length) return new Int16Array(0)
  const sourceRate = Math.max(1, Number(inputSampleRate || outputSampleRate))
  if (sourceRate === outputSampleRate) {
    const output = new Int16Array(input.length)
    for (let i = 0; i < input.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, input[i] || 0))
      output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    }
    return output
  }
  const ratio = sourceRate / outputSampleRate
  const outputLength = Math.max(1, Math.floor(input.length / ratio))
  const output = new Int16Array(outputLength)
  for (let outIndex = 0; outIndex < outputLength; outIndex += 1) {
    const start = Math.floor(outIndex * ratio)
    const end = Math.max(start + 1, Math.min(input.length, Math.floor((outIndex + 1) * ratio)))
    let sum = 0
    for (let sourceIndex = start; sourceIndex < end; sourceIndex += 1) sum += input[sourceIndex] || 0
    const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)))
    output[outIndex] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }
  return output
}

export function MediaSessionProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<MediaSessionStatus>('IDLE')
  const [sourceType, setSourceType] = useState<MediaSourceType>('MICROPHONE')
  const [projectRoot, setProjectRoot] = useState('')
  const [startedAt, setStartedAt] = useState('')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [enableStt, setEnableStt] = useState(true)
  const [sttStatus, setSttStatus] = useState('대기')
  const [sttEngine, setSttEngine] = useState('대기')
  const [audioLevel, setAudioLevel] = useState(0)
  const [lastRecognizedAt, setLastRecognizedAt] = useState('')
  const [sttReconnectCount, setSttReconnectCount] = useState(0)
  const [sttDroppedChunks, setSttDroppedChunks] = useState(0)
  const [refineStatus, setRefineStatus] = useState<RefineStatus>('IDLE')
  const [refineMessage, setRefineMessage] = useState('')
  const [interimText, setInterimText] = useState('')
  const [interimSegment, setInterimSegment] = useState<TranscriptSegment | null>(null)
  const [transcriptSegments, setTranscriptSegments] = useState<TranscriptSegment[]>([])
  const [recordingUrl, setRecordingUrl] = useState('')
  const [recordingMimeType, setRecordingMimeType] = useState('')
  const [error, setError] = useState('')

  const recordingUrlRef = useRef('')
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaChunksRef = useRef<Blob[]>([])
  const recognitionRef = useRef<any>(null)
  const recognitionRestartTimerRef = useRef<number | null>(null)
  const persistTimerRef = useRef<number | null>(null)
  const sessionActiveRef = useRef(false)
  const startedAtMsRef = useRef(0)
  const startedAtRef = useRef('')
  const projectRootRef = useRef('')
  const transcriptSegmentsRef = useRef<TranscriptSegment[]>([])
  const sourceTypeRef = useRef<MediaSourceType>('MICROPHONE')
  const enableSttRef = useRef(true)
  const sttEngineRef = useRef('대기')
  const refineStatusRef = useRef<RefineStatus>('IDLE')
  const backendWsRef = useRef<WebSocket | null>(null)
  const backendReadyRef = useRef(false)
  const backendFallbackStartedRef = useRef(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const audioSourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null)
  const audioMuteGainRef = useRef<GainNode | null>(null)
  const audioLevelLastUpdateRef = useRef(0)
  const refineWaitResolveRef = useRef<(() => void) | null>(null)
  const refineWaitTimerRef = useRef<number | null>(null)
  const stopRef = useRef<() => Promise<void>>(async () => {})

  const sttSupported = typeof WebSocket !== 'undefined' || Boolean(getSpeechRecognitionConstructor())

  useEffect(() => { transcriptSegmentsRef.current = transcriptSegments }, [transcriptSegments])
  useEffect(() => { projectRootRef.current = projectRoot }, [projectRoot])
  useEffect(() => { recordingUrlRef.current = recordingUrl }, [recordingUrl])
  useEffect(() => { sourceTypeRef.current = sourceType }, [sourceType])
  useEffect(() => { enableSttRef.current = enableStt }, [enableStt])
  useEffect(() => { sttEngineRef.current = sttEngine }, [sttEngine])
  useEffect(() => { refineStatusRef.current = refineStatus }, [refineStatus])

  useEffect(() => {
    if (status !== 'RECORDING' || !startedAtMsRef.current) return
    const update = () => setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAtMsRef.current) / 1000)))
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [status, startedAt])

  const persistTranscriptSnapshot = useCallback(async (overrides?: Partial<{ status: string; stoppedAt: string; segments: TranscriptSegment[] }>) => {
    const root = projectRootRef.current
    if (!root) return
    const segments = overrides?.segments || transcriptSegmentsRef.current
    try {
      await api('/project-live-transcript', {
        method: 'POST',
        body: JSON.stringify({
          root,
          session: {
            sourceType: sourceTypeRef.current,
            enableStt: enableSttRef.current,
            startedAt: startedAtRef.current || '',
            stoppedAt: overrides?.stoppedAt || '',
            status: overrides?.status || (sessionActiveRef.current ? 'RECORDING' : 'IDLE'),
            updatedAt: nowIso(),
            sttEngine: sttEngineRef.current,
            refineStatus: refineStatusRef.current,
            segments
          }
        })
      })
    } catch {
      // Recording must stay alive even when transcript persistence is temporarily unavailable.
    }
  }, [])

  const schedulePersist = useCallback(() => {
    if (persistTimerRef.current) window.clearTimeout(persistTimerRef.current)
    persistTimerRef.current = window.setTimeout(() => {
      persistTimerRef.current = null
      void persistTranscriptSnapshot()
    }, 650)
  }, [persistTranscriptSnapshot])

  const stopSpeechRecognition = useCallback(() => {
    if (recognitionRestartTimerRef.current) {
      window.clearTimeout(recognitionRestartTimerRef.current)
      recognitionRestartTimerRef.current = null
    }
    const recognition = recognitionRef.current
    recognitionRef.current = null
    if (recognition) {
      try { recognition.onend = null } catch {}
      try { recognition.stop?.() } catch {}
      try { recognition.abort?.() } catch {}
    }
  }, [])

  const startSpeechRecognitionFallback = useCallback((language: string, reason = '') => {
    const Recognition = getSpeechRecognitionConstructor()
    if (!Recognition || sourceTypeRef.current !== 'MICROPHONE') {
      if (sourceTypeRef.current === 'SCREEN') {
        setSttStatus('Backend STT를 사용할 수 없습니다. 화면/시스템 오디오는 브라우저 SpeechRecognition으로 대체할 수 없습니다.')
      } else {
        setSttStatus('Backend STT와 브라우저 SpeechRecognition을 모두 사용할 수 없습니다.')
      }
      return
    }
    if (backendFallbackStartedRef.current) return
    backendFallbackStartedRef.current = true
    setSttEngine('브라우저 SpeechRecognition (보조)')
    sttEngineRef.current = '브라우저 SpeechRecognition (보조)'
    if (reason) setSttStatus(`Backend STT 대체 모드 · ${reason}`)

    const createAndStart = () => {
      if (!sessionActiveRef.current || !enableSttRef.current || sourceTypeRef.current !== 'MICROPHONE') return
      let recognition: any
      try {
        recognition = new Recognition()
      } catch (recognitionError) {
        setSttStatus(`보조 STT 시작 실패: ${String((recognitionError as Error)?.message || recognitionError)}`)
        return
      }
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = language || 'ko-KR'
      recognition.maxAlternatives = 1
      recognition.onstart = () => setSttStatus('보조 STT 연결됨 · Backend faster-whisper 사용 불가')
      recognition.onresult = (event: any) => {
        let interim = ''
        const finals: TranscriptSegment[] = []
        for (let index = Number(event.resultIndex || 0); index < event.results.length; index += 1) {
          const result = event.results[index]
          const text = String(result?.[0]?.transcript || '').trim()
          if (!text) continue
          if (result.isFinal) {
            finals.push({
              id: makeSegmentId(),
              text,
              createdAt: nowIso(),
              offsetMs: Math.max(0, Date.now() - startedAtMsRef.current),
              source: 'browser-speech-recognition',
              refined: false
            })
          } else {
            interim += `${text} `
          }
        }
        const interimValue = interim.trim()
        setInterimText(interimValue)
        setInterimSegment(interimValue ? {
          id: `browser-partial-${Date.now()}`,
          text: interimValue,
          createdAt: nowIso(),
          offsetMs: Math.max(0, Date.now() - startedAtMsRef.current),
          endOffsetMs: Math.max(0, Date.now() - startedAtMsRef.current),
          source: 'browser-speech-recognition',
          refined: false,
          provisional: true
        } : null)
        if (finals.length) {
          setInterimText('')
          setInterimSegment(null)
          setLastRecognizedAt(nowIso())
          setTranscriptSegments(previous => {
            const next = [...previous, ...finals]
            transcriptSegmentsRef.current = next
            return next
          })
          schedulePersist()
        }
      }
      recognition.onerror = (event: any) => {
        const reasonText = String(event?.error || 'unknown')
        if (reasonText === 'no-speech' || reasonText === 'aborted') return
        setSttStatus(`보조 STT 오류: ${reasonText}`)
      }
      recognition.onend = () => {
        if (!sessionActiveRef.current || !enableSttRef.current || sourceTypeRef.current !== 'MICROPHONE') return
        setSttReconnectCount(previous => previous + 1)
        setSttStatus('보조 STT 재연결 중…')
        recognitionRestartTimerRef.current = window.setTimeout(() => createAndStart(), 350)
      }
      recognitionRef.current = recognition
      try { recognition.start() } catch (startError) {
        setSttStatus(`보조 STT 시작 실패: ${String((startError as Error)?.message || startError)}`)
      }
    }

    createAndStart()
  }, [schedulePersist])

  const stopPcmCapture = useCallback(async () => {
    const processor = audioProcessorRef.current
    audioProcessorRef.current = null
    if (processor) {
      try { processor.onaudioprocess = null } catch {}
      try { processor.disconnect() } catch {}
    }
    const source = audioSourceNodeRef.current
    audioSourceNodeRef.current = null
    if (source) {
      try { source.disconnect() } catch {}
    }
    const gain = audioMuteGainRef.current
    audioMuteGainRef.current = null
    if (gain) {
      try { gain.disconnect() } catch {}
    }
    const context = audioContextRef.current
    audioContextRef.current = null
    if (context) {
      try { await context.close() } catch {}
    }
    setAudioLevel(0)
  }, [])

  const resolveRefineWait = useCallback(() => {
    if (refineWaitTimerRef.current) {
      window.clearTimeout(refineWaitTimerRef.current)
      refineWaitTimerRef.current = null
    }
    const resolve = refineWaitResolveRef.current
    refineWaitResolveRef.current = null
    if (resolve) resolve()
  }, [])

  const startBackendStt = useCallback(async (stream: MediaStream, language: string) => {
    const audioTracks = stream.getAudioTracks()
    if (!audioTracks.length) {
      setSttStatus(sourceTypeRef.current === 'SCREEN'
        ? '화면 공유에서 오디오가 선택되지 않았습니다. 공유 창에서 시스템/탭 오디오 공유를 켜세요.'
        : '마이크 Audio Track을 찾을 수 없습니다.')
      return false
    }

    let socket: WebSocket
    try {
      socket = new WebSocket(buildSttWebSocketUrl(projectRootRef.current, language))
    } catch (socketError) {
      setSttStatus(`Backend STT 연결 생성 실패: ${String((socketError as Error)?.message || socketError)}`)
      return false
    }
    backendWsRef.current = socket
    backendReadyRef.current = false

    const opened = await new Promise<boolean>(resolve => {
      let settled = false
      const timer = window.setTimeout(() => {
        if (settled) return
        settled = true
        resolve(false)
      }, 5000)
      socket.onopen = () => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        resolve(true)
      }
      socket.onerror = () => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        resolve(false)
      }
    })

    if (!opened || socket.readyState !== WebSocket.OPEN) {
      try { socket.close() } catch {}
      if (backendWsRef.current === socket) backendWsRef.current = null
      setSttStatus('Backend STT WebSocket 연결 실패')
      return false
    }

    socket.onmessage = event => {
      let payload: any
      try { payload = JSON.parse(String(event.data || '{}')) } catch { return }
      const type = String(payload?.type || '')
      if (type === 'status') {
        setSttStatus(String(payload?.message || payload?.status || 'Backend STT 처리 중'))
        return
      }
      if (type === 'ready') {
        backendReadyRef.current = true
        const engineLabel = `faster-whisper ${String(payload?.model || '').trim()}`.trim()
        setSttEngine(engineLabel)
        sttEngineRef.current = engineLabel
        setSttStatus(String(payload?.message || 'Backend STT 연결됨'))
        return
      }
      if (type === 'level') return
      if (type === 'partial') {
        const item = payload?.segment || {}
        const text = String(item?.text || payload?.text || '').trim()
        const provisional = text ? {
          id: String(item?.id || `partial-${Number(item?.offsetMs ?? payload?.windowStartMs ?? 0)}-${Number(item?.endOffsetMs ?? payload?.windowEndMs ?? 0)}`),
          text,
          createdAt: String(item?.createdAt || nowIso()),
          offsetMs: Number(item?.offsetMs ?? payload?.windowStartMs ?? 0),
          endOffsetMs: Number(item?.endOffsetMs ?? payload?.windowEndMs ?? item?.offsetMs ?? 0),
          confidence: item?.confidence == null ? null : Number(item.confidence),
          source: String(item?.source || 'faster-whisper'),
          refined: false,
          provisional: true
        } satisfies TranscriptSegment : null
        setInterimText(text)
        setInterimSegment(provisional)
        if (text) setLastRecognizedAt(nowIso())
        return
      }
      if (type === 'final') {
        const item = payload?.segment || {}
        const text = String(item?.text || '').trim()
        if (!text) return
        const segment: TranscriptSegment = {
          id: String(item?.id || makeSegmentId()),
          text,
          createdAt: String(item?.createdAt || nowIso()),
          offsetMs: Number(item?.offsetMs || 0),
          endOffsetMs: Number(item?.endOffsetMs || item?.offsetMs || 0),
          confidence: item?.confidence == null ? null : Number(item.confidence),
          source: String(item?.source || 'faster-whisper'),
          refined: item?.refined === true,
          provisional: false
        }
        setLastRecognizedAt(nowIso())
        setInterimText('')
        setInterimSegment(current => current && rangesOverlap(current, segment) ? null : current)
        setTranscriptSegments(previous => {
          if (previous.some(existing => existing.id === segment.id)) return previous
          const next = [...previous, segment]
          transcriptSegmentsRef.current = next
          return next
        })
        schedulePersist()
        return
      }
      if (type === 'refine_status') {
        const nextStatus = String(payload?.status || '').toUpperCase()
        if (nextStatus === 'RUNNING') {
          setRefineStatus('RUNNING')
          refineStatusRef.current = 'RUNNING'
        } else if (nextStatus === 'ERROR') {
          setRefineStatus('ERROR')
          refineStatusRef.current = 'ERROR'
        }
        setRefineMessage(String(payload?.message || ''))
        setSttStatus(String(payload?.message || '정밀 보정 중…'))
        return
      }
      if (type === 'refined') {
        const segments: TranscriptSegment[] = Array.isArray(payload?.segments)
          ? payload.segments.map((item: any) => ({
              id: String(item?.id || makeSegmentId()),
              text: String(item?.text || ''),
              createdAt: String(item?.createdAt || nowIso()),
              offsetMs: Number(item?.offsetMs || 0),
              endOffsetMs: Number(item?.endOffsetMs || item?.offsetMs || 0),
              confidence: item?.confidence == null ? null : Number(item.confidence),
              source: String(item?.source || 'faster-whisper'),
              refined: true,
              provisional: false
            })).filter((item: TranscriptSegment) => item.text.trim())
          : []
        const replacementEndMs = Number(
          payload?.rangeEndMs
          ?? payload?.durationMs
          ?? segments.reduce((maximum, item) => Math.max(maximum, Number(item.endOffsetMs ?? item.offsetMs ?? 0)), 0)
        )
        const replacementStartMs = Number(payload?.rangeStartMs ?? 0)
        const nextSegments = replaceTranscriptRange(
          transcriptSegmentsRef.current,
          segments,
          replacementStartMs,
          replacementEndMs
        )
        setTranscriptSegments(nextSegments)
        transcriptSegmentsRef.current = nextSegments
        setInterimText('')
        setInterimSegment(null)
        setLastRecognizedAt(nextSegments.length ? nowIso() : '')
        setRefineStatus('DONE')
        refineStatusRef.current = 'DONE'
        setRefineMessage(String(payload?.message || '정밀 보정 완료'))
        setSttStatus(String(payload?.message || '정밀 보정 완료'))
        void persistTranscriptSnapshot({ segments: nextSegments })
        resolveRefineWait()
        return
      }
      if (type === 'stopped') {
        resolveRefineWait()
        return
      }
      if (type === 'warning') {
        setSttStatus(String(payload?.message || 'STT 경고'))
        return
      }
      if (type === 'error') {
        const message = String(payload?.message || 'Backend STT 오류')
        setSttStatus(message)
        if (payload?.fallbackAllowed && sessionActiveRef.current && sourceTypeRef.current === 'MICROPHONE') {
          try { socket.close() } catch {}
          startSpeechRecognitionFallback(language, message)
        }
        resolveRefineWait()
      }
    }

    socket.onclose = () => {
      if (backendWsRef.current === socket) backendWsRef.current = null
      const unexpectedlyClosed = sessionActiveRef.current && enableSttRef.current && !backendFallbackStartedRef.current
      if (unexpectedlyClosed) {
        setSttReconnectCount(previous => previous + 1)
        if (sourceTypeRef.current === 'MICROPHONE') {
          startSpeechRecognitionFallback(language, 'Backend STT 연결이 끊겼습니다.')
        } else {
          setSttStatus('Backend STT 연결이 끊겼습니다. 화면 오디오는 보조 SpeechRecognition으로 대체할 수 없습니다.')
        }
      }
      resolveRefineWait()
    }

    const AudioContextCtor = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext | undefined
    if (!AudioContextCtor) {
      try { socket.close() } catch {}
      setSttStatus('AudioContext를 지원하지 않아 Backend PCM Streaming을 시작할 수 없습니다.')
      return false
    }

    try {
      const context = new AudioContextCtor({ latencyHint: 'interactive' })
      audioContextRef.current = context
      if (context.state === 'suspended') await context.resume()
      const audioOnlyStream = new MediaStream(audioTracks)
      const source = context.createMediaStreamSource(audioOnlyStream)
      const processor = context.createScriptProcessor(4096, 1, 1)
      const muteGain = context.createGain()
      muteGain.gain.value = 0
      audioSourceNodeRef.current = source
      audioProcessorRef.current = processor
      audioMuteGainRef.current = muteGain

      processor.onaudioprocess = event => {
        const channel = event.inputBuffer.getChannelData(0)
        if (!channel?.length) return
        let sumSquares = 0
        for (let index = 0; index < channel.length; index += 1) {
          const sample = channel[index] || 0
          sumSquares += sample * sample
        }
        const rms = Math.sqrt(sumSquares / Math.max(1, channel.length))
        const now = Date.now()
        if (now - audioLevelLastUpdateRef.current >= 120) {
          audioLevelLastUpdateRef.current = now
          setAudioLevel(Math.min(1, rms * 14))
        }
        if (socket.readyState !== WebSocket.OPEN) return
        if (socket.bufferedAmount > 8 * 1024 * 1024) {
          setSttDroppedChunks(previous => previous + 1)
          return
        }
        const pcm = downsampleToPcm16(channel, context.sampleRate, TARGET_STT_SAMPLE_RATE)
        if (pcm.byteLength) socket.send(pcm.buffer)
      }
      source.connect(processor)
      processor.connect(muteGain)
      muteGain.connect(context.destination)
      setSttEngine('Backend faster-whisper 준비 중')
      sttEngineRef.current = 'Backend faster-whisper 준비 중'
      setSttStatus('Backend Audio Stream 연결됨 · faster-whisper 모델 준비 중…')
      return true
    } catch (audioError) {
      try { socket.close() } catch {}
      await stopPcmCapture()
      setSttStatus(`PCM Streaming 시작 실패: ${String((audioError as Error)?.message || audioError)}`)
      return false
    }
  }, [persistTranscriptSnapshot, resolveRefineWait, schedulePersist, startSpeechRecognitionFallback, stopPcmCapture])

  const start = useCallback(async (options: StartMediaSessionOptions) => {
    if (sessionActiveRef.current || status === 'STARTING' || status === 'STOPPING') {
      setError('이미 진행 중인 녹음 세션이 있습니다.')
      return false
    }
    const root = String(options.projectRoot || '').trim()
    if (!root) {
      setError('녹음을 연결할 프로젝트를 먼저 선택하세요.')
      return false
    }
    if (!navigator.mediaDevices) {
      setError('이 브라우저에서는 미디어 장치 접근을 지원하지 않습니다.')
      return false
    }

    setStatus('STARTING')
    setError('')
    setRecordingUrl(previous => {
      if (previous) URL.revokeObjectURL(previous)
      return ''
    })
    setRecordingMimeType('')
    setTranscriptSegments([])
    transcriptSegmentsRef.current = []
    setInterimText('')
    setInterimSegment(null)
    setElapsedSeconds(0)
    setAudioLevel(0)
    setLastRecognizedAt('')
    setSttReconnectCount(0)
    setSttDroppedChunks(0)
    setRefineStatus('IDLE')
    refineStatusRef.current = 'IDLE'
    setRefineMessage('')
    backendReadyRef.current = false
    backendFallbackStartedRef.current = false
    setProjectRoot(root)
    projectRootRef.current = root
    setSourceType(options.sourceType)
    sourceTypeRef.current = options.sourceType
    setEnableStt(Boolean(options.enableStt))
    enableSttRef.current = Boolean(options.enableStt)

    try {
      const stream = options.sourceType === 'SCREEN'
        ? await (navigator.mediaDevices as any).getDisplayMedia({
            video: true,
            audio: true,
            // Chrome hints: prefer sharing the current browser tab so YouTube iframe audio
            // can be included when the user enables "탭 오디오 공유" in the picker.
            preferCurrentTab: true,
            selfBrowserSurface: 'include',
            surfaceSwitching: 'include',
            systemAudio: 'include'
          }) as MediaStream
        : await navigator.mediaDevices.getUserMedia({
            audio: {
              // External speaker/lecture audio can be mistaken for echo and removed by the browser.
              // Keep the raw microphone signal; backend VAD/Whisper handles speech filtering.
              echoCancellation: false,
              noiseSuppression: false,
              autoGainControl: true,
              channelCount: 1
            }
          })

      if (options.sourceType === 'SCREEN' && options.enableStt && stream.getAudioTracks().length === 0) {
        stream.getTracks().forEach(track => {
          try { track.stop() } catch {}
        })
        setStatus('IDLE')
        setSttEngine('오디오 없음')
        sttEngineRef.current = '오디오 없음'
        setSttStatus('화면 공유에 오디오가 포함되지 않았습니다.')
        setError('YouTube/화면 음성을 텍스트로 변환하려면 공유 선택창에서 Chrome 탭을 선택하고 “탭 오디오 공유”를 켜세요. 현재 공유에는 Audio Track이 없어 실시간 STT와 종료 후 정밀 보정 모두 텍스트를 생성할 수 없습니다.')
        return false
      }

      mediaStreamRef.current = stream

      const preferredTypes = options.sourceType === 'SCREEN'
        ? ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
        : ['audio/webm;codecs=opus', 'audio/webm']
      const mimeType = preferredTypes.find(type => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported?.(type)) || ''
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      mediaChunksRef.current = []
      recorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) mediaChunksRef.current.push(event.data)
      }
      recorder.onerror = event => setError(`녹음 오류: ${String((event as any)?.error?.message || 'MediaRecorder 오류')}`)
      mediaRecorderRef.current = recorder
      recorder.start(1000)

      const started = nowIso()
      const startedMs = Date.now()
      setStartedAt(started)
      startedAtRef.current = started
      startedAtMsRef.current = startedMs
      sessionActiveRef.current = true
      setStatus('RECORDING')
      setSttStatus(options.enableStt ? 'Backend STT 연결 준비 중…' : 'STT 사용 안 함')
      setSttEngine(options.enableStt ? 'Backend faster-whisper 준비 중' : 'OFF')
      sttEngineRef.current = options.enableStt ? 'Backend faster-whisper 준비 중' : 'OFF'

      for (const track of stream.getTracks()) {
        track.onended = () => {
          if (sessionActiveRef.current) void stopRef.current()
        }
      }

      if (options.enableStt) {
        const backendStarted = await startBackendStt(stream, options.language || 'ko-KR')
        if (!backendStarted && options.sourceType === 'MICROPHONE') {
          startSpeechRecognitionFallback(options.language || 'ko-KR', 'Backend Streaming 시작 실패')
        }
      }
      void persistTranscriptSnapshot({ status: 'RECORDING', segments: [] })
      return true
    } catch (startError) {
      sessionActiveRef.current = false
      setStatus('IDLE')
      setError(`녹음 시작 실패: ${String((startError as Error)?.message || startError)}`)
      await stopPcmCapture()
      mediaStreamRef.current?.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
      return false
    }
  }, [persistTranscriptSnapshot, startBackendStt, startSpeechRecognitionFallback, status, stopPcmCapture])

  const stop = useCallback(async () => {
    if (!sessionActiveRef.current && status !== 'STARTING') return
    setStatus('STOPPING')
    sessionActiveRef.current = false
    stopSpeechRecognition()
    await stopPcmCapture()

    const recorder = mediaRecorderRef.current
    mediaRecorderRef.current = null
    if (recorder && recorder.state !== 'inactive') {
      await new Promise<void>(resolve => {
        recorder.addEventListener('stop', () => resolve(), { once: true })
        try { recorder.stop() } catch { resolve() }
      })
    }
    mediaStreamRef.current?.getTracks().forEach(track => {
      try { track.stop() } catch {}
    })
    mediaStreamRef.current = null

    const chunks = mediaChunksRef.current
    mediaChunksRef.current = []
    if (chunks.length) {
      const mime = recorder?.mimeType || chunks[0]?.type || (sourceTypeRef.current === 'SCREEN' ? 'video/webm' : 'audio/webm')
      const blob = new Blob(chunks, { type: mime })
      const url = URL.createObjectURL(blob)
      setRecordingUrl(previous => {
        if (previous) URL.revokeObjectURL(previous)
        return url
      })
      setRecordingMimeType(mime)
    }

    const socket = backendWsRef.current
    const canRefine = Boolean(enableSttRef.current && socket && socket.readyState === WebSocket.OPEN && !backendFallbackStartedRef.current)
    if (canRefine && socket) {
      setRefineStatus('RUNNING')
      refineStatusRef.current = 'RUNNING'
      setRefineMessage('녹음 전체 정밀 보정을 준비하고 있습니다…')
      setSttStatus('녹음 전체 정밀 보정 준비 중…')
      const waitForRefine = new Promise<void>(resolve => {
        refineWaitResolveRef.current = resolve
        refineWaitTimerRef.current = window.setTimeout(() => {
          refineWaitTimerRef.current = null
          refineWaitResolveRef.current = null
          setRefineStatus('ERROR')
          refineStatusRef.current = 'ERROR'
          setRefineMessage('정밀 보정 시간이 너무 길어 실시간 Transcript를 유지했습니다.')
          resolve()
        }, 180_000)
      })
      try { socket.send(JSON.stringify({ type: 'stop', refine: true })) } catch { resolveRefineWait() }
      await waitForRefine
    }

    const currentSocket = backendWsRef.current
    backendWsRef.current = null
    if (currentSocket) {
      try { currentSocket.close() } catch {}
    }
    if (!canRefine && refineStatusRef.current === 'IDLE') {
      setRefineStatus('IDLE')
      setRefineMessage(backendFallbackStartedRef.current ? '브라우저 보조 STT에서는 전체 정밀 보정을 지원하지 않습니다.' : '')
    }

    setInterimText('')
    setInterimSegment(null)
    setAudioLevel(0)
    setSttStatus(refineStatusRef.current === 'DONE' ? '정밀 보정 완료' : '정지됨')
    setStatus('IDLE')
    await persistTranscriptSnapshot({ status: 'STOPPED', stoppedAt: nowIso() })
  }, [persistTranscriptSnapshot, resolveRefineWait, status, stopPcmCapture, stopSpeechRecognition])

  useEffect(() => { stopRef.current = stop }, [stop])

  const clearTranscript = useCallback(async () => {
    setTranscriptSegments([])
    transcriptSegmentsRef.current = []
    setInterimText('')
    setInterimSegment(null)
    setLastRecognizedAt('')
    setRefineStatus('IDLE')
    refineStatusRef.current = 'IDLE'
    setRefineMessage('')
    await persistTranscriptSnapshot({ segments: [] })
  }, [persistTranscriptSnapshot])

  const loadProjectTranscript = useCallback(async (root: string) => {
    const normalizedRoot = String(root || '').trim()
    if (!normalizedRoot || sessionActiveRef.current) return
    try {
      const result = await api<any>(`/project-live-transcript?root=${encodeURIComponent(normalizedRoot)}`)
      const session = result?.session && typeof result.session === 'object' ? result.session : {}
      const segments: TranscriptSegment[] = Array.isArray(session.segments)
        ? session.segments.map((item: any) => ({
            id: String(item?.id || makeSegmentId()),
            text: String(item?.text || ''),
            createdAt: String(item?.createdAt || ''),
            offsetMs: Number(item?.offsetMs || 0),
            endOffsetMs: Number(item?.endOffsetMs || item?.offsetMs || 0),
            confidence: item?.confidence == null ? null : Number(item.confidence),
            source: String(item?.source || ''),
            refined: item?.refined === true
          })).filter((item: TranscriptSegment) => item.text.trim())
        : []
      setProjectRoot(normalizedRoot)
      projectRootRef.current = normalizedRoot
      setSourceType(session.sourceType === 'SCREEN' ? 'SCREEN' : 'MICROPHONE')
      sourceTypeRef.current = session.sourceType === 'SCREEN' ? 'SCREEN' : 'MICROPHONE'
      setEnableStt(session.enableStt !== false)
      enableSttRef.current = session.enableStt !== false
      setStartedAt(String(session.startedAt || ''))
      startedAtRef.current = String(session.startedAt || '')
      setTranscriptSegments(segments)
      transcriptSegmentsRef.current = segments
      setInterimText('')
      setInterimSegment(null)
      const restoredEngine = String(session.sttEngine || (segments.some(item => item.source === 'faster-whisper') ? 'faster-whisper' : '대기'))
      setSttEngine(restoredEngine)
      sttEngineRef.current = restoredEngine
      const restoredRefineStatus = String(session.refineStatus || '').toUpperCase() === 'DONE' || segments.some(item => item.refined)
        ? 'DONE' as RefineStatus
        : 'IDLE' as RefineStatus
      setRefineStatus(restoredRefineStatus)
      refineStatusRef.current = restoredRefineStatus
      setRefineMessage(restoredRefineStatus === 'DONE' ? '이전 녹음의 정밀 보정 Transcript를 불러왔습니다.' : '')
      setLastRecognizedAt(segments.length ? String(segments[segments.length - 1]?.createdAt || '') : '')
      setSttStatus(
        String(session.status || '').toUpperCase() === 'RECORDING'
          ? '이전 녹음 세션은 새로고침/종료로 중단되었습니다. 저장된 Transcript를 복원했습니다.'
          : segments.length ? '이전 실시간 기록을 불러왔습니다.' : '대기'
      )
    } catch {
      // Live transcript restore is optional; file memo use must remain available.
    }
  }, [])

  useEffect(() => () => {
    sessionActiveRef.current = false
    stopSpeechRecognition()
    void stopPcmCapture()
    const socket = backendWsRef.current
    backendWsRef.current = null
    try { socket?.close() } catch {}
    try {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop()
    } catch {}
    mediaStreamRef.current?.getTracks().forEach(track => track.stop())
    if (persistTimerRef.current) window.clearTimeout(persistTimerRef.current)
    if (refineWaitTimerRef.current) window.clearTimeout(refineWaitTimerRef.current)
    if (recordingUrlRef.current) URL.revokeObjectURL(recordingUrlRef.current)
  }, [stopPcmCapture, stopSpeechRecognition])

  const transcriptText = useMemo(
    () => formatTranscript(transcriptSegments, interimText, interimSegment),
    [interimSegment, interimText, transcriptSegments]
  )

  const transcriptStage = useMemo<TranscriptStage>(() => {
    if (status === 'ERROR' || refineStatus === 'ERROR') return 'ERROR'
    if (refineStatus === 'RUNNING' || (status === 'STOPPING' && enableStt)) return 'REFINING'
    if (status === 'STARTING' || status === 'RECORDING') return 'COLLECTING'
    if (refineStatus === 'DONE' || (status === 'IDLE' && (transcriptSegments.length > 0 || Boolean(interimText.trim())))) return 'COMPLETED'
    return 'IDLE'
  }, [enableStt, interimText, refineStatus, status, transcriptSegments.length])

  const value = useMemo<MediaSessionContextValue>(() => ({
    status,
    sourceType,
    projectRoot,
    startedAt,
    elapsedSeconds,
    enableStt,
    sttSupported,
    sttStatus,
    sttEngine,
    audioLevel,
    lastRecognizedAt,
    sttReconnectCount,
    sttDroppedChunks,
    refineStatus,
    refineMessage,
    transcriptStage,
    interimText,
    interimSegment,
    transcriptSegments,
    transcriptText,
    recordingUrl,
    recordingMimeType,
    error,
    start,
    stop,
    clearTranscript,
    loadProjectTranscript
  }), [
    audioLevel,
    clearTranscript,
    elapsedSeconds,
    enableStt,
    error,
    interimSegment,
    interimText,
    lastRecognizedAt,
    loadProjectTranscript,
    projectRoot,
    recordingMimeType,
    recordingUrl,
    refineMessage,
    refineStatus,
    sourceType,
    start,
    startedAt,
    status,
    sttDroppedChunks,
    sttEngine,
    sttReconnectCount,
    sttStatus,
    sttSupported,
    stop,
    transcriptSegments,
    transcriptStage,
    transcriptText
  ])

  return <MediaSessionContext.Provider value={value}>{children}</MediaSessionContext.Provider>
}

export function useMediaSession() {
  const context = useContext(MediaSessionContext)
  if (!context) throw new Error('useMediaSession must be used inside MediaSessionProvider')
  return context
}
