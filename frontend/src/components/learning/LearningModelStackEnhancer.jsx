import { useEffect } from 'react'

const LEARNED_MODEL = 'theanova-learn:latest'
const BASE_MODEL = 'qwen3.5:4b'

/**
 * Adds the cumulative-model explanation to the Learning Center.
 *
 * Important: this enhancer is display-only. Applied-case visibility is owned by the
 * Backend learning visibility service and the React Learning Center data. Do not fetch
 * datasets/misjudgments from here: this component is mounted globally and document DOM
 * mutations are frequent, which previously created a request storm in every browser tab.
 */
export function LearningModelStackEnhancer() {
  useEffect(() => {
    let disposed = false

    const render = () => {
      if (disposed) return
      const page = document.querySelector('.llm-learning-page')
      if (!(page instanceof HTMLElement)) return

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
      const active = currentText.includes(LEARNED_MODEL)

      const downloadButton = modelPanel.querySelector('button')
      if (downloadButton instanceof HTMLButtonElement && active) {
        downloadButton.disabled = true
        downloadButton.textContent = `${BASE_MODEL} 포함 적용됨`
        downloadButton.title = `${LEARNED_MODEL}이 ${BASE_MODEL}를 Base Model로 사용 중입니다.`
      }

      const strong = node.querySelector('strong')
      const em = node.querySelector('em')
      const strongText = `${LEARNED_MODEL} + ${BASE_MODEL}`
      const statusText = active
        ? `적용됨 · ${BASE_MODEL} 기반 + 누적 Dataset 학습층`
        : `학습 적용 시 AgentStudio가 ${BASE_MODEL}를 자동 준비 후 결합합니다.`

      if (strong && strong.textContent !== strongText) strong.textContent = strongText
      if (em && em.textContent !== statusText) em.textContent = statusText
    }

    render()
    const timer = window.setInterval(render, 1000)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [])

  return null
}
