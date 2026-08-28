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

function datasetTraceCell(dataset) {
  const td = document.createElement('td')
  td.setAttribute(mark, '1')
  td.className = 'learning-dataset-trace-cell'

  const caseBlock = document.createElement('div')
  caseBlock.className = 'learning-dataset-trace-block'
  const caseLabel = document.createElement('small')
  caseLabel.textContent = '오판 ID'
  const caseCode = document.createElement('code')
  caseCode.className = 'learning-trace-id'
  caseCode.textContent = String(dataset?.source_case_id || '-')
  caseCode.title = `원본 오판 ID: ${dataset?.source_case_id || '-'}`
  caseBlock.append(caseLabel, caseCode)

  const datasetBlock = document.createElement('div')
  datasetBlock.className = 'learning-dataset-trace-block'
  const datasetLabel = document.createElement('small')
  datasetLabel.textContent = 'Dataset ID'
  const datasetCode = document.createElement('code')
  datasetCode.className = 'learning-trace-id'
  datasetCode.textContent = String(dataset?.id || '-')
  datasetCode.title = `Dataset ID: ${dataset?.id || '-'}`
  datasetBlock.append(datasetLabel, datasetCode)

  td.append(caseBlock, datasetBlock)
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
        const traceTh = document.createElement('th')
        traceTh.setAttribute(mark, '1')
        traceTh.textContent = '오판 / Dataset ID'
        if (status?.nextSibling) headRow.insertBefore(traceTh, status.nextSibling)
        else headRow.appendChild(traceTh)
      }

      const rows = Array.from(table.querySelectorAll('tbody tr'))
      const datasets = datasetsRef.current
      rows.forEach((row, index) => {
        if (!(row instanceof HTMLTableRowElement) || row.querySelector(`[${mark}]`)) return
        const dataset = datasets[index] || {}
        const status = row.children[0]
        const traceTd = datasetTraceCell(dataset)
        if (status?.nextSibling) row.insertBefore(traceTd, status.nextSibling)
        else row.appendChild(traceTd)
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
      const caseCode = document.createElement('code')
      caseCode.textContent = `오판 ID: ${dataset.source_case_id || '-'}`
      const datasetCode = document.createElement('code')
      datasetCode.textContent = `Dataset ID: ${dataset.id || '-'}`
      trace.append(caseCode, datasetCode)

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
