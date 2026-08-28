import { useEffect } from 'react'

const LEARNED_MODEL = 'theanova-learn:latest'
const BASE_MODEL = 'qwen3.5:4b'

export function LearningModelStackEnhancer() {
  useEffect(() => {
    const apply = () => {
      const page = document.querySelector('.llm-learning-page')
      if (!page) return
      const modelPanel = page.querySelector('.llm-learning-model-upgrade')
      if (!modelPanel) return

      let node = modelPanel.querySelector('[data-learning-model-stack="true"]')
      if (!node) {
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
      const strong = node.querySelector('strong')
      const em = node.querySelector('em')
      if (strong) strong.textContent = `${LEARNED_MODEL} + ${BASE_MODEL}`
      if (em) em.textContent = active
        ? `적용됨 · ${BASE_MODEL} 기반 + 누적 Dataset 학습층`
        : `학습 적용 시 AgentStudio가 ${BASE_MODEL}를 자동 준비 후 결합합니다.`
    }

    const observer = new MutationObserver(apply)
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })
    apply()
    return () => observer.disconnect()
  }, [])

  return null
}
