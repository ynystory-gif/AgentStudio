import { useEffect } from 'react'

export function LearningUnlearnedListEnhancer() {
  useEffect(() => {
    const apply = () => {
      const page = document.querySelector('.llm-learning-page')
      if (!(page instanceof HTMLElement)) return

      const activeTab = Array.from(page.querySelectorAll('.llm-learning-toolbar button'))
        .find((button: LegacyValue) => button.classList.contains('active'))
      if (!String(activeTab?.textContent || '').includes('오판 수집')) return

      const table = page.querySelector('.llm-case-table')
      if (!(table instanceof HTMLElement)) return

      let notice = page.querySelector<HTMLElement>('[data-current-pc-unlearned-notice="true"]')
      if (!(notice instanceof HTMLElement)) {
        notice = document.createElement('div')
        notice.setAttribute('data-current-pc-unlearned-notice', 'true')
        notice.style.margin = '8px 0'
        notice.style.padding = '8px 10px'
        notice.style.border = '1px solid rgba(96,165,250,.35)'
        notice.style.borderRadius = '6px'
        notice.style.background = 'rgba(37,99,235,.08)'
        notice.style.fontSize = '12px'
        notice.innerHTML = '<b>현재 PC 미학습 오판만 표시</b> · 이미 Dataset으로 생성되어 현재 PC의 <code>theanova-learn:latest</code>에 학습 적용된 오판은 이 목록에서 숨깁니다. 이 목록에 남아 있는 항목은 아직 Dataset이 없거나 현재 PC에 학습 적용되지 않은 항목입니다.'
        table.parentElement?.insertBefore(notice, table)
      }

      for (const row of table.querySelectorAll('tbody tr')) {
        const statusCell = row.querySelector('td:first-child')
        if (!(statusCell instanceof HTMLElement)) continue
        if (statusCell.querySelector('[data-current-pc-unlearned-badge="true"]')) continue
        const badge = document.createElement('small')
        badge.setAttribute('data-current-pc-unlearned-badge', 'true')
        badge.textContent = '현재 PC 미학습'
        badge.style.display = 'block'
        badge.style.marginTop = '4px'
        badge.style.fontWeight = '700'
        badge.style.opacity = '.85'
        statusCell.appendChild(badge)
      }
    }

    apply()
    const timer = window.setInterval(apply, 800)
    return () => window.clearInterval(timer)
  }, [])

  return null
}
