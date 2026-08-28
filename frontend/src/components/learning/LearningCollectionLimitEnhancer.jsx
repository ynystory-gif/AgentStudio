import { useEffect } from 'react'

/**
 * Keeps learning problem collection aligned with the visible misjudgment list.
 *
 * - The number of misjudgment topics is taken from the current list automatically.
 * - At most 10 topics are collected in one run.
 * - Zero visible cases means zero collection targets; the collection button is disabled.
 * - The learning page itself scrolls vertically so the case list is not squeezed into
 *   the tiny remaining viewport below the header/metrics/toolbars.
 *
 * This is intentionally implemented as a compatibility enhancer so the existing
 * LlmLearningCenter job/progress state remains the single owner of collection jobs.
 */
export function LearningCollectionLimitEnhancer() {
  useEffect(() => {
    const styleId = 'theanova-learning-collection-limit-style'
    let style = document.getElementById(styleId)
    if (!style) {
      style = document.createElement('style')
      style.id = styleId
      style.textContent = `
        .llm-learning-page{
          overflow-y:auto!important;
          overflow-x:hidden!important;
        }
        .llm-learning-page .llm-learning-body{
          flex:0 0 auto!important;
          min-height:max(680px, calc(100vh - 220px))!important;
          overflow:visible!important;
          padding-bottom:48px!important;
        }
        .llm-learning-page .llm-case-table{
          margin-bottom:32px;
        }
        .llm-learning-page .llm-case-table th{
          top:0!important;
        }
        @media(max-height:800px){
          .llm-learning-page .llm-learning-body{
            min-height:720px!important;
          }
        }
      `
      document.head.appendChild(style)
    }

    const visibleCaseCount = () => {
      const rows = Array.from(document.querySelectorAll('.llm-case-table tbody tr'))
      const actualRows = rows.filter(row => row.querySelector('td'))
      return Math.min(10, actualRows.length)
    }

    const refreshLabels = () => {
      const count = visibleCaseCount()
      const buttons = Array.from(document.querySelectorAll('.llm-learning-toolbar button'))
      const problemButton = buttons.find(button => String(button.textContent || '').includes('문제 수집'))
      if (problemButton) {
        problemButton.textContent = `＋ 문제 수집 (오판 ${count}개)`
        problemButton.title = count > 0
          ? `현재 오판 목록 기준 ${count}개 주제를 처리합니다. 한 번에 최대 10개까지 처리합니다.`
          : '현재 문제를 생성할 오판 항목이 없습니다.'
        // Preserve the learning center's own busy/processing disabled state and add
        // the zero-target guard without enabling a button React has disabled.
        if (count === 0) {
          problemButton.setAttribute('data-learning-zero-target', 'true')
          problemButton.setAttribute('disabled', '')
        } else if (problemButton.getAttribute('data-learning-zero-target') === 'true') {
          problemButton.removeAttribute('data-learning-zero-target')
          const busy = Boolean(document.querySelector('.llm-job-progress:not(.completed):not(.failed)'))
          if (!busy) problemButton.removeAttribute('disabled')
        }
      }

      const help = document.querySelector('.llm-problem-help')
      if (help) {
        help.innerHTML = count > 0
          ? `<b>문제 수집:</b> 현재 오판 목록의 아이템 수를 자동으로 사용합니다. 한 번에 최대 <b>10개 주제</b>까지 처리하며, 현재 대상은 <b>${count}개</b>입니다. 주제당 생성할 문제 수만 선택하면 됩니다.`
          : '<b>문제 수집:</b> 현재 문제를 생성할 오판 항목이 없습니다. 오판이 수집되면 목록 개수 기준으로 최대 <b>10개 주제</b>까지 자동 선택합니다.'
      }
    }

    /*
     * LlmLearningCenter currently asks two prompts synchronously when the problem
     * collection button is clicked. Intercept only the first (topic-count) prompt and
     * supply the visible list count. The second problem-count prompt remains unchanged,
     * so the existing job state/progress UI continues to work without duplication.
     */
    const onClickCapture = (event) => {
      const target = event.target
      const button = target?.closest?.('.llm-learning-toolbar button.primary')
      if (!button || !String(button.textContent || '').includes('문제 수집')) return

      const automaticCount = visibleCaseCount()
      if (automaticCount <= 0) {
        event.preventDefault()
        event.stopPropagation()
        return
      }

      const previousPrompt = window.prompt
      let topicPromptHandled = false
      const patchedPrompt = (message, defaultValue) => {
        if (!topicPromptHandled && String(message || '').includes('처리할 오판 주제 수')) {
          topicPromptHandled = true
          return String(automaticCount)
        }
        return previousPrompt.call(window, message, defaultValue)
      }
      window.prompt = patchedPrompt
      window.setTimeout(() => {
        if (window.prompt === patchedPrompt) window.prompt = previousPrompt
      }, 0)
    }

    refreshLabels()
    const timer = window.setInterval(refreshLabels, 500)
    document.addEventListener('click', onClickCapture, true)

    return () => {
      window.clearInterval(timer)
      document.removeEventListener('click', onClickCapture, true)
      document.getElementById(styleId)?.remove()
    }
  }, [])

  return null
}
