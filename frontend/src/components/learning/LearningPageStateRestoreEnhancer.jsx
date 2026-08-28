import { useEffect } from 'react'

const TAB_KEY = 'theanova.agentstudio.learning.active-tab'
const SCROLL_KEY = 'theanova.agentstudio.learning.scroll-top'

const tabFromButton = (button) => {
  const text = String(button?.textContent || '').trim()
  if (text.startsWith('1. 오판 수집')) return 'cases'
  if (text.startsWith('2. 수집 문제 / Dataset')) return 'datasets'
  if (text.startsWith('3. PC별 학습 적용 관리')) return 'training'
  return ''
}

const buttonForTab = (tab) => {
  const buttons = Array.from(document.querySelectorAll('.llm-learning-toolbar > button'))
  return buttons.find((button) => tabFromButton(button) === tab) || null
}

export function LearningPageStateRestoreEnhancer() {
  useEffect(() => {
    let restoreTimer = 0

    const rememberClick = (event) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const button = target.closest('.llm-learning-toolbar > button')
      if (!button) return
      const tab = tabFromButton(button)
      if (tab) sessionStorage.setItem(TAB_KEY, tab)
    }

    const rememberScroll = () => {
      const content = document.querySelector('.ux-content')
      if (!(content instanceof HTMLElement)) return
      if (!content.classList.contains('llm-learning-active')) return
      sessionStorage.setItem(SCROLL_KEY, String(Math.max(0, content.scrollTop || 0)))
    }

    const restore = () => {
      const page = document.querySelector('.llm-learning-page')
      if (!page) return

      const tab = sessionStorage.getItem(TAB_KEY) || 'cases'
      const button = buttonForTab(tab)
      if (button && !button.classList.contains('active')) {
        button.click()
      }

      window.clearTimeout(restoreTimer)
      restoreTimer = window.setTimeout(() => {
        const content = document.querySelector('.ux-content')
        if (!(content instanceof HTMLElement)) return
        const saved = Number(sessionStorage.getItem(SCROLL_KEY) || 0)
        if (Number.isFinite(saved) && saved > 0) content.scrollTop = saved
      }, 120)
    }

    document.addEventListener('click', rememberClick, true)
    document.addEventListener('scroll', rememberScroll, true)

    const observer = new MutationObserver(restore)
    observer.observe(document.documentElement, { childList: true, subtree: true })
    restore()

    return () => {
      window.clearTimeout(restoreTimer)
      observer.disconnect()
      document.removeEventListener('click', rememberClick, true)
      document.removeEventListener('scroll', rememberScroll, true)
    }
  }, [])

  return null
}
