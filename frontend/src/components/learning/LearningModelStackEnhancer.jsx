import { useEffect } from 'react'
import { api } from '../../api'

const LEARNED_MODEL = 'theanova-learn:latest'
const BASE_MODEL = 'qwen3.5:4b'

export function LearningModelStackEnhancer() {
  useEffect(() => {
    let disposed = false
    let scheduled = 0
    let visibilityTimer = 0
    let lastPanel = null
    let lastCurrentText = ''
    let visibilityBusy = false

    const syncAppliedCaseVisibility = async () => {
      if (disposed || visibilityBusy) return
      const page = document.querySelector('.llm-learning-page')
      const table = page?.querySelector('.llm-case-table')
      if (!(table instanceof HTMLTableElement)) return

      visibilityBusy = true
      try {
        const providerSelect = page?.querySelector('.llm-learning-filter select')
        const provider = providerSelect instanceof HTMLSelectElement ? providerSelect.value : ''
        const query = `/learning/misjudgments?limit=1000${provider ? `&provider=${encodeURIComponent(provider)}` : ''}`
        const [datasetsResult, casesResult] = await Promise.all([
          api('/learning/datasets'),
          api(query),
        ])
        if (disposed) return

        const appliedSourceIds = new Set(
          (Array.isArray(datasetsResult?.items) ? datasetsResult.items : [])
            .filter((dataset) => {
              const app = dataset?.current_pc_application
              return Boolean(app?.enabled && app?.installed)
            })
            .map((dataset) => String(dataset?.source_case_id || '').trim())
            .filter(Boolean),
        )

        const cases = Array.isArray(casesResult?.items) ? casesResult.items : []
        const rows = Array.from(table.querySelectorAll('tbody > tr'))
        rows.forEach((row, index) => {
          const item = cases[index]
          const ids = new Set([
            String(item?.id || '').trim(),
            ...(Array.isArray(item?.group_case_ids) ? item.group_case_ids.map((id) => String(id || '').trim()) : []),
          ].filter(Boolean))
          const applied = Array.from(ids).some((id) => appliedSourceIds.has(id))
          row.style.display = applied ? 'none' : ''
          if (applied) row.setAttribute('data-learning-applied-hidden', 'true')
          else row.removeAttribute('data-learning-applied-hidden')
        })
      } catch {
        // Visibility synchronization is a UI safeguard. Backend/API errors must not
        // block the Learning Center itself.
      } finally {
        visibilityBusy = false
      }
    }

    const scheduleVisibilitySync = () => {
      if (disposed) return
      window.clearTimeout(visibilityTimer)
      visibilityTimer = window.setTimeout(() => {
        visibilityTimer = 0
        void syncAppliedCaseVisibility()
      }, 180)
    }

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
      const active = currentText.includes(LEARNED_MODEL)

      const downloadButton = modelPanel.querySelector('button')
      if (downloadButton instanceof HTMLButtonElement && active) {
        downloadButton.disabled = true
        downloadButton.textContent = `${BASE_MODEL} 포함 적용됨`
        downloadButton.title = `${LEARNED_MODEL}이 ${BASE_MODEL}를 Base Model로 사용 중입니다.`
      }

      if (modelPanel === lastPanel && currentText === lastCurrentText) {
        scheduleVisibilitySync()
        return
      }
      lastPanel = modelPanel
      lastCurrentText = currentText

      const strong = node.querySelector('strong')
      const em = node.querySelector('em')
      const strongText = `${LEARNED_MODEL} + ${BASE_MODEL}`
      const statusText = active
        ? `적용됨 · ${BASE_MODEL} 기반 + 누적 Dataset 학습층`
        : `학습 적용 시 AgentStudio가 ${BASE_MODEL}를 자동 준비 후 결합합니다.`

      if (strong && strong.textContent !== strongText) strong.textContent = strongText
      if (em && em.textContent !== statusText) em.textContent = statusText
      scheduleVisibilitySync()
    }

    const scheduleRender = () => {
      if (disposed || scheduled) return
      scheduled = window.requestAnimationFrame(() => {
        scheduled = 0
        render()
      })
    }

    const observer = new MutationObserver((mutations) => {
      const relevant = mutations.some((mutation) => {
        const target = mutation.target
        if (target instanceof Element && target.closest('[data-learning-model-stack="true"]')) return false
        if (target.parentElement?.closest('[data-learning-model-stack="true"]')) return false
        if (target instanceof Element && target.closest('[data-learning-applied-hidden="true"]')) return false
        return true
      })
      if (relevant) scheduleRender()
    })

    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true })
    scheduleRender()

    return () => {
      disposed = true
      observer.disconnect()
      window.clearTimeout(visibilityTimer)
      if (scheduled) window.cancelAnimationFrame(scheduled)
    }
  }, [])

  return null
}
