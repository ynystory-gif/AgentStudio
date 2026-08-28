import { useEffect } from 'react'

const LEARNED_MODEL = 'theanova-learn:latest'
const BASE_MODEL = 'qwen3.5:4b'

export function LearningModelStackEnhancer() {
  useEffect(() => {
    let disposed = false
    let scheduled = 0
    let lastPanel = null
    let lastCurrentText = ''

    const render = () => {
      if (disposed) return
      const page = document.querySelector('.llm-learning-page')
      if (!page) {
        lastPanel = null
        lastCurrentText = ''
        return
      }

      const modelPanel = page.querySelector('.llm-learning-model-upgrade')
      if (!(modelPanel instanceof HTMLElement)) return

      let node = modelPanel.querySelector('[data-learning-model-stack="true"]')
      if (!(node instanceof HTMLElement)) {
        node = document.createElement('div')
        node.setAttribute('data-learning-model-stack', 'true')
        node.style.minWidth = '260px'
        node.style.display = 'flex'
        node.style.flexDirection = 'column'
        node.style.gap = '3px'
        node.innerHTML = '<small>자동 학습 모델 구성</small><strong></strong><em style="font-style:normal;opacity:.72;font-size:11px"></em>'
        const button = modelPanel.querySelector('button')
        if (button) modelPanel.insertBefore(node, button)
        else modelPanel.appendChild(node)
      }

      const currentBlock = modelPanel.querySelector('div:first-child')
      const currentText = String(currentBlock?.textContent || '')

      // Do not rewrite our own DOM on every MutationObserver callback. Rewriting
      // textContent triggers another mutation and previously caused a tight loop
      // when the LLM Learning page was opened.
      if (modelPanel === lastPanel && currentText === lastCurrentText) return
      lastPanel = modelPanel
      lastCurrentText = currentText

      const active = currentText.includes(LEARNED_MODEL)
      const strong = node.querySelector('strong')
      const em = node.querySelector('em')
      const strongText = `${LEARNED_MODEL} + ${BASE_MODEL}`
      const statusText = active
        ? `적용됨 · ${BASE_MODEL} 기반 + 누적 Dataset 학습층`
        : `학습 적용 시 AgentStudio가 ${BASE_MODEL}를 자동 준비 후 결합합니다.`

      if (strong && strong.textContent !== strongText) strong.textContent = strongText
      if (em && em.textContent !== statusText) em.textContent = statusText
    }

    const scheduleRender = () => {
      if (disposed || scheduled) return
      scheduled = window.requestAnimationFrame(() => {
        scheduled = 0
        render()
      })
    }

    const observer = new MutationObserver((mutations) => {
      // Ignore mutations generated inside the enhancer itself. Only react when
      // the Learning page/model panel is mounted, replaced, or its source state changes.
      const relevant = mutations.some((mutation) => {
        const target = mutation.target
        if (target instanceof Element && target.closest('[data-learning-model-stack="true"]')) return false
        if (target.parentElement?.closest('[data-learning-model-stack="true"]')) return false
        return true
      })
      if (relevant) scheduleRender()
    })

    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })
    scheduleRender()

    return () => {
      disposed = true
      observer.disconnect()
      if (scheduled) window.cancelAnimationFrame(scheduled)
    }
  }, [])

  return null
}
