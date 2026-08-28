import { useEffect, useRef } from 'react'
import { api } from '../../api'

const mark = 'data-learning-trace'

function codeCell(value, title = '') {
  const td = document.createElement('td')
  td.setAttribute(mark, '1')
  const code = document.createElement('code')
  code.className = 'learning-trace-id'
  code.textContent = String(value || '-')
  code.title = title || String(value || '')
  td.appendChild(code)
  return td
}

export function LearningDatasetTraceEnhancer() {
  const datasetsRef = useRef([])

  useEffect(() => {
    let disposed = false

    const refreshDatasets = async () => {
      try {
        const result = await api('/learning/datasets')
        if (!disposed) datasetsRef.current = Array.isArray(result?.items) ? result.items : []
      } catch (_) {}
    }

    const enhanceDatasetTable = () => {
      const table = document.querySelector('.llm-dataset-table')
      if (!(table instanceof HTMLTableElement)) return
      const headRow = table.querySelector('thead tr')
      if (!(headRow instanceof HTMLTableRowElement)) return

      if (!headRow.querySelector(`[${mark}]`)) {
        const status = headRow.children[0]
        const datasetTh = document.createElement('th')
        datasetTh.setAttribute(mark, '1')
        datasetTh.textContent = 'Dataset ID'
        const caseTh = document.createElement('th')
        caseTh.setAttribute(mark, '1')
        caseTh.textContent = '오판 ID'
        if (status?.nextSibling) {
          headRow.insertBefore(caseTh, status.nextSibling)
          headRow.insertBefore(datasetTh, caseTh)
        } else {
          headRow.append(datasetTh, caseTh)
        }
      }

      const rows = Array.from(table.querySelectorAll('tbody tr'))
      const datasets = datasetsRef.current
      rows.forEach((row, index) => {
        if (!(row instanceof HTMLTableRowElement) || row.querySelector(`[${mark}]`)) return
        const dataset = datasets[index] || {}
        const status = row.children[0]
        const datasetTd = codeCell(dataset.id, `Dataset ID: ${dataset.id || '-'}`)
        const caseTd = codeCell(dataset.source_case_id, `원본 오판 ID: ${dataset.source_case_id || '-'}`)
        if (status?.nextSibling) {
          row.insertBefore(caseTd, status.nextSibling)
          row.insertBefore(datasetTd, caseTd)
        } else {
          row.append(datasetTd, caseTd)
        }
      })
    }

    const enhanceProblemViewer = () => {
      const viewer = document.querySelector('.llm-problem-viewer')
      const table = viewer?.querySelector('.llm-problem-list table')
      if (!(viewer instanceof HTMLElement) || !(table instanceof HTMLTableElement)) return

      const selectedRow = document.querySelector('.llm-dataset-table tbody tr.selected')
      const allRows = Array.from(document.querySelectorAll('.llm-dataset-table tbody tr'))
      const selectedIndex = selectedRow ? allRows.indexOf(selectedRow) : -1
      const dataset = selectedIndex >= 0 ? (datasetsRef.current[selectedIndex] || {}) : {}

      let trace = viewer.querySelector('.learning-problem-trace')
      if (!(trace instanceof HTMLElement)) {
        trace = document.createElement('div')
        trace.className = 'learning-problem-trace'
        const head = viewer.querySelector('.llm-problem-viewer-head')
        if (head?.nextSibling) viewer.insertBefore(trace, head.nextSibling)
        else viewer.prepend(trace)
      }
      trace.innerHTML = ''
      const datasetCode = document.createElement('code')
      datasetCode.textContent = `Dataset ID: ${dataset.id || '-'}`
      const caseCode = document.createElement('code')
      caseCode.textContent = `오판 ID: ${dataset.source_case_id || '-'}`
      trace.append(datasetCode, caseCode)

      const headRow = table.querySelector('thead tr')
      if (headRow instanceof HTMLTableRowElement && !headRow.querySelector(`[${mark}]`)) {
        const th = document.createElement('th')
        th.setAttribute(mark, '1')
        th.textContent = 'Problem ID'
        const first = headRow.children[0]
        if (first?.nextSibling) headRow.insertBefore(th, first.nextSibling)
        else headRow.appendChild(th)
      }

      const problems = Array.isArray(dataset.problems) ? dataset.problems : []
      Array.from(table.querySelectorAll('tbody tr')).forEach((row, index) => {
        if (!(row instanceof HTMLTableRowElement) || row.querySelector(`[${mark}]`)) return
        const first = row.children[0]
        const td = codeCell(problems[index]?.id, `Problem ID: ${problems[index]?.id || '-'}`)
        if (first?.nextSibling) row.insertBefore(td, first.nextSibling)
        else row.appendChild(td)
      })
    }

    const run = async () => {
      await refreshDatasets()
      enhanceDatasetTable()
      enhanceProblemViewer()
    }

    run()
    const timer = window.setInterval(() => {
      enhanceDatasetTable()
      enhanceProblemViewer()
      refreshDatasets()
    }, 1000)

    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [])

  return null
}
