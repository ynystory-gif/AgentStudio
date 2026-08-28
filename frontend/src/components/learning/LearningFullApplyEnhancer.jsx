import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../../api'

const REOPEN_KEY = 'theanova.agentstudio.learning.reopen'

export function LearningFullApplyEnhancer() {
  const [host, setHost] = useState(null)
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let disposed = false
    const locate = () => {
      if (disposed) return
      const toolbar = document.querySelector('.llm-learning-toolbar')
      setHost(toolbar instanceof HTMLElement ? toolbar : null)
    }
    locate()
    const observer = new MutationObserver(locate)
    observer.observe(document.documentElement, { childList: true, subtree: true })
    return () => {
      disposed = true
      observer.disconnect()
    }
  }, [])

  useEffect(() => {
    if (!job?.id || job.status !== 'running') return
    const timer = window.setInterval(async () => {
      try {
        const next = await api(`/learning/learning-apply-job/${job.id}`)
        setJob(next)
        if (next?.status === 'completed') {
          window.clearInterval(timer)
          sessionStorage.setItem(REOPEN_KEY, '1')
          window.setTimeout(() => window.location.reload(), 700)
        } else if (next?.status === 'failed') {
          window.clearInterval(timer)
          setError(next?.error || next?.message || '전체 재학습 적용에 실패했습니다.')
        }
      } catch (e) {
        window.clearInterval(timer)
        setError(String(e))
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [job?.id, job?.status])

  if (!host) return null

  const running = job?.status === 'running'
  const progress = Math.max(0, Math.min(100, Number(job?.progress || 0)))
  const title = running
    ? `전체 재학습 ${progress}%`
    : '모두 학습 적용'

  const start = async () => {
    const ok = window.confirm(
      '공용 DB의 모든 유효 Dataset을 다시 읽어 현재 PC의 theanova-learn:latest를 전체 재생성합니다. 계속할까요?'
    )
    if (!ok) return
    setError('')
    try {
      const next = await api('/learning/full-learning-apply-job', { method: 'POST' })
      setJob(next)
    } catch (e) {
      setError(String(e))
    }
  }

  return createPortal(
    <>
      <button
        type="button"
        className="primary"
        disabled={running}
        onClick={start}
        title="모든 Dataset을 합쳐 theanova-learn:latest를 전체 재학습 적용합니다."
      >
        {running ? `↻ ${title}` : '⇄ 모두 학습 적용'}
      </button>
      {(running || error) && (
        <span style={{marginLeft: 8, fontSize: 12, opacity: 0.9}}>
          {error || `${job?.message || '전체 재학습 적용 중...'} · ${progress}%`}
        </span>
      )}
    </>,
    host,
  )
}
