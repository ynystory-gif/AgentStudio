import { asLegacyError } from '../../utils/errors'
import { useEffect } from 'react'
import { api } from '../../api'

const installed = new WeakSet()
const POLL_INTERVAL_MS = 1000
const STATUS_REQUEST_TIMEOUT_MS = 3000
const FRONTEND_HARD_TIMEOUT_MS = 300000

const sleep = (ms: LegacyValue) => new Promise((resolve: LegacyValue) => window.setTimeout(resolve, ms))
const elapsedText = (startedAt: LegacyValue) => {
  const sec = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
}

function esc(value: LegacyValue = '') {
  return String(value || '').replace(/[&<>"']/g, (ch: LegacyValue) => {
    if (ch === '&') return '&amp;'
    if (ch === '<') return '&lt;'
    if (ch === '>') return '&gt;'
    if (ch === '"') return '&quot;'
    return '&#39;'
  })
}

function ensureStyle() {
  if (document.getElementById('agentstudio-dynamic-theme-source-v2-style')) return
  const style = document.createElement('style')
  style.id = 'agentstudio-dynamic-theme-source-v2-style'
  style.textContent = `
    .ui-layout-dynamic-source-v2{border:1px solid #294258;border-radius:9px;padding:10px;margin:8px 0;background:#0d1822;display:grid;gap:10px}
    .ui-layout-dynamic-source-v2 .head{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .ui-layout-dynamic-source-v2 .head b{font-size:13px}.ui-layout-dynamic-source-v2 .head span{font-size:13px;color:#7e9ab2}
    .ui-layout-dynamic-source-v2 .section{display:grid;gap:7px}.ui-layout-dynamic-source-v2 .title{display:flex;align-items:center;justify-content:space-between;gap:8px}
    .ui-layout-dynamic-source-v2 .row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px;align-items:center}.ui-layout-dynamic-source-v2 .row.image{grid-template-columns:minmax(0,1fr) 140px auto}
    .ui-layout-dynamic-source-v2 input,.ui-layout-dynamic-source-v2 select{min-width:0;width:100%}
    .ui-layout-dynamic-source-v2 .status{font-size:13px;color:#91a8bc;min-height:16px}.ui-layout-dynamic-source-v2 .status.error{color:#ff9b9b}.ui-layout-dynamic-source-v2 .status.ok{color:#7ee2a8}
    .ui-layout-dynamic-source-v2 .progress{display:none;border:1px solid #294258;border-radius:8px;background:#09131c;padding:9px;gap:7px}.ui-layout-dynamic-source-v2 .progress.active{display:grid}.ui-layout-dynamic-source-v2 .progress.done{border-color:#31556f}
    .ui-layout-dynamic-source-v2 .progress-head{display:flex;justify-content:space-between;gap:10px;font-size:13px}.ui-layout-dynamic-source-v2 .track{height:9px;background:#172838;border-radius:999px;overflow:hidden}.ui-layout-dynamic-source-v2 .bar{height:100%;width:0%;background:#4aa3df;transition:width .2s ease}
    .ui-layout-dynamic-source-v2 .message{font-size:13px;color:#a8c0d4;line-height:1.45}.ui-layout-dynamic-source-v2 .meta{font-size:13px;color:#7894aa;display:flex;gap:12px;flex-wrap:wrap}.ui-layout-dynamic-source-v2 .backend-state{font-size:13px;border:1px solid #294258;background:#0a151f;border-radius:6px;padding:6px 8px;color:#8fa9bd}.ui-layout-dynamic-source-v2 .backend-state.running{border-color:#72582b;color:#f0c873}.ui-layout-dynamic-source-v2 .backend-state.ended{border-color:#285b46;color:#7ee2a8}.ui-layout-dynamic-source-v2 .actions{display:flex;justify-content:flex-end}
  `
  document.head.appendChild(style)
}

async function imageReference(file: LegacyValue, role: LegacyValue) {
  const bitmap = await createImageBitmap(file)
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('이미지 분석 Canvas를 만들 수 없습니다.')
  ctx.drawImage(bitmap, 0, 0, 64, 64)
  bitmap.close?.()
  const data = ctx.getImageData(0, 0, 64, 64).data
  const counts = new Map<LegacyValue,LegacyValue>()
  for (let i = 0; i < data.length; i += 16) {
    if ((data[i + 3] ?? 0) < 180) continue
    const r = Math.min(255, Math.round((data[i] ?? 0) / 32) * 32)
    const g = Math.min(255, Math.round((data[i + 1] ?? 0) / 32) * 32)
    const b = Math.min(255, Math.round((data[i + 2] ?? 0) / 32) * 32)
    const key = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  const palette = [...counts.entries()].sort((a: LegacyValue, b: LegacyValue) => b[1] - a[1]).slice(0, 8).map((x: LegacyValue) => x[0])
  const background = palette[0] || '#ffffff'
  const surface = palette[1] || background
  const primary = palette.find((x: LegacyValue) => x !== background && x !== surface) || '#2563eb'
  return {
    file_name: file.name,
    reference_role: role || 'default',
    tokens: {
      colors: { primary, background, surface },
      typography: { fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", headingWeight: 700, bodyWeight: 400 },
      radius: { button: 8, card: 12, input: 8 },
      spacing: { unit: 4, density: 'comfortable' },
    },
    component_rules: {},
    layout_rules: {},
    preview_colors: palette,
  }
}

async function fetchJobStatus(jobId: LegacyValue) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), STATUS_REQUEST_TIMEOUT_MS)
  try {
    return await api(`/ui-themes/import-dynamic/jobs/${encodeURIComponent(jobId)}`, { signal: controller.signal })
  } finally {
    window.clearTimeout(timer)
  }
}

function renderProgress(host: LegacyValue, current: LegacyValue, startedAt: LegacyValue, { done = false, failed = false }:LegacyRecord = {}) {
  const box = host.querySelector('[data-v2-progress]')
  if (!(box instanceof HTMLElement)) return
  const pct = Math.max(0, Math.min(100, Number(current?.progress || 0)))
  box.classList.add('active')
  box.classList.toggle('done', done)
  box.style.borderColor = failed ? '#6f3030' : ''
  const bar = box.querySelector<HTMLElement>('[data-v2-bar]')
  const percent = box.querySelector('[data-v2-percent]')
  const message = box.querySelector('[data-v2-message]')
  const stage = box.querySelector('[data-v2-stage]')
  const meta = box.querySelector('[data-v2-meta]')
  const backend = box.querySelector('[data-v2-backend]')
  if (bar) bar.style.width = `${pct}%`
  if (percent) percent.textContent = `${Math.round(pct)}% · 경과 ${elapsedText(startedAt)}`
  if (message) message.textContent = current?.message || current?.error || '분석 중입니다.'
  if (stage) stage.textContent = `단계: ${current?.stage || 'analysis'}`
  if (meta) meta.textContent = `Backend Job: ${current?.job_id || '-'} · 상태: ${current?.status || '-'} · Job 경과: ${current?.job_age_seconds ?? '-'}초 · 최대 ${Math.round(Number(current?.backend_hard_timeout_seconds || 300) / 60)}분`
  if (backend) {
    const cleanupState = String(current?.backend_cleanup_state || '')
    const ended = current?.backend_analysis_ended === true || current?.backend_cleanup_completed === true
    const workerCount = Number(current?.backend_worker_process_count ?? (Array.isArray(current?.active_theme_worker_pids) ? current.active_theme_worker_pids.length : 0))
    backend.classList.toggle('running', Boolean(current?.hard_timeout_triggered) && !ended)
    backend.classList.toggle('ended', ended)
    backend.textContent = ended
      ? `Backend 작업 종료 확인됨 · Worker Process ${workerCount}개 · 종료시각 ${current?.backend_terminated_at ? new Date(current.backend_terminated_at).toLocaleTimeString('ko-KR',{hour12:false}) : '-'}`
      : current?.hard_timeout_triggered
        ? `Backend 실패 처리 완료 · 실행 Task/Worker 종료 확인 중 · cleanup=${cleanupState || 'running'}`
        : `Backend 작업 실행 중 · Worker Process ${workerCount}개`
  }
}

async function waitForJob(host: LegacyValue, job: LegacyValue, startedAt: LegacyValue, state: LegacyValue) {
  let current = job
  let consecutiveStatusTimeouts = 0
  while (true) {
    const status = String(current?.status || '')
    const backendAgeSeconds = Number(current?.job_age_seconds)
    const backendLimitSeconds = Number(current?.backend_hard_timeout_seconds || 300)
    const deadlineReached = Number.isFinite(backendAgeSeconds)
      ? backendAgeSeconds >= backendLimitSeconds
      : Date.now() - startedAt >= FRONTEND_HARD_TIMEOUT_MS
    const timeoutLikeFailure = status === 'failed' && (
      current?.hard_timeout_triggered === true
      || String(current?.stage || '').toLowerCase().startsWith('timeout')
      || deadlineReached
    )
    const timeoutCleanupPending = timeoutLikeFailure
      && current?.backend_analysis_ended !== true
      && current?.backend_cleanup_completed !== true
    if (['completed', 'failed', 'cancelled'].includes(status) && !timeoutCleanupPending) break
    if (state.cancelRequested) throw new Error('통합 분석 작업 취소를 요청했습니다.')

    // Backend owns the 5-minute deadline. Never call the user-cancel endpoint because
    // the UI clock reached the deadline; that would incorrectly turn timeout FAILED
    // into a normal cancellation. Keep polling until Backend returns the terminal state.
    renderProgress(host, current, startedAt)
    if (deadlineReached) {
      const msg = host.querySelector('[data-v2-message]')
      if (msg) msg.textContent = timeoutCleanupPending
        ? '5분 제한으로 실패 처리되었습니다. Backend 실행 Task와 Worker Process가 실제로 종료되었는지 확인하고 있습니다.'
        : '최대 분석시간 5분에 도달했습니다. Backend 실패 종료 상태를 확인하고 있습니다.'
    }
    await sleep(POLL_INTERVAL_MS)

    try {
      current = await fetchJobStatus(job.job_id)
      consecutiveStatusTimeouts = 0
    } catch (error) {
      const aborted = asLegacyError(error).name === 'AbortError' || String(asLegacyError(error).message || '').toLowerCase().includes('abort')
      if (!aborted) throw error
      consecutiveStatusTimeouts += 1
      const msg = host.querySelector('[data-v2-message]')
      if (msg) msg.textContent = `Backend 상태 조회가 3초 안에 응답하지 않았습니다. 다음 조회를 계속합니다. (${consecutiveStatusTimeouts}회)`
    }
  }

  state.jobId = ''
  const terminal = String(current?.status || '')
  renderProgress(host, current, startedAt, { done: true, failed: terminal === 'failed' })
  if (terminal === 'completed') return current?.result || current
  if (terminal === 'cancelled') throw new Error(current?.message || '통합 분석 작업이 취소되었습니다.')
  if (current?.hard_timeout_triggered) {
    const workerCount = Number(current?.backend_worker_process_count ?? 0)
    throw new Error(`${current?.error || current?.message || 'Theme 통합 분석이 5분 제한으로 실패했습니다.'} · Backend 작업 종료 확인됨 · Worker Process ${workerCount}개`)
  }
  throw new Error(current?.error || current?.message || '통합 분석 작업이 실패했습니다.')
}

function install(panel: LegacyValue) {
  if (installed.has(panel)) return
  installed.add(panel)
  ensureStyle()

  const labels = [...panel.querySelectorAll('label')]
  const oldDynamic = panel.querySelector('.ui-layout-dynamic-source')
  if (oldDynamic) oldDynamic.remove()
  const urlLabel = labels.find((label: LegacyValue) => label.querySelector('span')?.textContent?.includes('웹사이트 URL'))
  const originalFiles = panel.querySelector('.ui-layout-theme-file-slots')
  if (urlLabel) urlLabel.style.display = 'none'
  if (originalFiles) originalFiles.style.display = 'none'

  const state: { urls:string[]; files:(File|null)[]; roles:string[]; busy:boolean; jobId:string; cancelRequested:boolean; tickTimer:number } = { urls: [''], files: [null], roles: ['default'], busy: false, jobId: '', cancelRequested: false, tickTimer: 0 }
  const host = document.createElement('div')
  host.className = 'ui-layout-dynamic-source-v2'
  host.innerHTML = `
    <div class="head"><b>동적 스타일 참고 자료</b><span>단일 Job Controller V2</span></div>
    <div class="section"><div class="title"><strong>웹사이트 URL</strong><button type="button" data-add-url>＋ URL 추가</button></div><div data-url-rows></div></div>
    <div class="section"><div class="title"><strong>화면 캡처 이미지</strong><button type="button" data-add-image>＋ 이미지 추가</button></div><div data-image-rows></div></div>
    <div class="progress" data-v2-progress><div class="progress-head"><strong>통합 분석 · 저장 진행률</strong><span data-v2-percent>0% · 경과 00:00</span></div><div class="track"><div class="bar" data-v2-bar></div></div><div class="message" data-v2-message>대기 중</div><div class="meta"><span data-v2-stage>단계: READY</span><span data-v2-meta>Backend Job: - · 최대 분석 5분</span></div><div class="backend-state" data-v2-backend>Backend 작업 상태 확인 대기</div><div class="actions"><button type="button" data-v2-cancel>작업 취소</button></div></div>
    <div class="status"></div>`

  const themeNameLabel = labels.find((label: LegacyValue) => label.querySelector('span')?.textContent?.includes('Theme 이름'))
  if (themeNameLabel?.parentElement === panel) themeNameLabel.insertAdjacentElement('afterend', host)
  else panel.insertBefore(host, panel.children[1] || null)

  const status = host.querySelector<HTMLElement>('.status')
  if (!status) return
  const renderRows = () => {
    const urlRows = host.querySelector('[data-url-rows]')
    const imageRows = host.querySelector('[data-image-rows]')
    if (urlRows) urlRows.innerHTML = state.urls.map((value: LegacyValue, index: LegacyValue) => `<div class="row"><input type="text" data-url-index="${index}" value="${esc(value)}" placeholder="https://example.com"/><button type="button" data-remove-url="${index}" ${state.urls.length === 1 ? 'disabled' : ''}>×</button></div>`).join('')
    if (imageRows) imageRows.innerHTML = state.files.map((file: LegacyValue, index: LegacyValue) => `<div class="row image"><input type="file" accept="image/*" data-image-index="${index}"/><select data-role-index="${index}"><option value="default">기본 화면</option><option value="menu_hover">메뉴 Hover</option><option value="user_menu_open">사용자 메뉴 Open</option><option value="active">Active 상태</option></select><button type="button" data-remove-image="${index}" ${state.files.length === 1 ? 'disabled' : ''}>×</button>${file ? `<small>선택: ${esc(file.name)}</small>` : ''}</div>`).join('')
  }
  renderRows()

  host.addEventListener('input', (event: LegacyValue) => {
    if (state.busy) return
    const t = event.target
    if (t instanceof HTMLInputElement && t.dataset.urlIndex !== undefined) state.urls[Number(t.dataset.urlIndex)] = t.value
  })
  host.addEventListener('change', (event: LegacyValue) => {
    if (state.busy) return
    const t = event.target
    if (t instanceof HTMLInputElement && t.dataset.imageIndex !== undefined) { state.files[Number(t.dataset.imageIndex)] = t.files?.[0] || null; renderRows() }
    if (t instanceof HTMLSelectElement && t.dataset.roleIndex !== undefined) state.roles[Number(t.dataset.roleIndex)] = t.value
  })
  host.addEventListener('click', async (event: LegacyValue) => {
    const target = event.target
    if (!(target instanceof HTMLElement)) return
    if (target.closest('[data-v2-cancel]')) {
      if (!state.busy || !state.jobId || state.cancelRequested) return
      state.cancelRequested = true
      try { await api(`/ui-themes/import-dynamic/jobs/${encodeURIComponent(state.jobId)}/cancel`, { method: 'POST' }) } catch {}
      return
    }
    if (state.busy) return
    if (target.closest('[data-add-url]')) { state.urls.push(''); renderRows(); return }
    if (target.closest('[data-add-image]')) { state.files.push(null); state.roles.push('default'); renderRows(); return }
    const ru = target.closest<HTMLElement>('[data-remove-url]'); if (ru && state.urls.length > 1) { state.urls.splice(Number(ru.dataset.removeUrl), 1); renderRows(); return }
    const ri = target.closest<HTMLElement>('[data-remove-image]'); if (ri && state.files.length > 1) { const i = Number(ri.dataset.removeImage); state.files.splice(i, 1); state.roles.splice(i, 1); renderRows() }
  })

  const action = panel.querySelector('.ui-layout-theme-import-actions button.primary')
  action?.addEventListener('click', async (event: LegacyValue) => {
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation?.()
    if (state.busy) return

    const nameInput = labels.find((label: LegacyValue) => label.querySelector('span')?.textContent?.includes('Theme 이름'))?.querySelector('input')
    const name = String(nameInput?.value || '').trim()
    const urls = state.urls.map((x: LegacyValue) => x.trim()).filter(Boolean)
    const selected = state.files.map((file: LegacyValue, index: LegacyValue) => ({ file, index })).filter((x: LegacyValue) => x.file)
    if (!name) { status.textContent = 'Theme 이름을 입력하세요.'; status.className = 'status error'; return }
    if (!urls.length && !selected.length) { status.textContent = 'URL 또는 이미지를 하나 이상 추가하세요.'; status.className = 'status error'; return }

    state.busy = true
    state.cancelRequested = false
    const startedAt = Date.now()
    if (action) { action.disabled = true; action.textContent = '통합 분석·저장 중...' }
    state.tickTimer = window.setInterval(() => {
      const percent = host.querySelector('[data-v2-percent]')
      if (percent && state.busy) {
        const pct = (String(percent.textContent || '').match(/(\d+)%/) || [])[1] || '0'
        percent.textContent = `${pct}% · 경과 ${elapsedText(startedAt)}`
      }
    }, 1000)

    try {
      const images:LegacyValue[]=[]
      for (const item of selected) images.push(await imageReference(item.file, state.roles[item.index] || 'default'))
      const job = await api('/ui-themes/import-dynamic/jobs', { method: 'POST', body: JSON.stringify({ name, urls, images, scope: 'GLOBAL' }) })
      state.jobId = job?.job_id || ''
      const result = await waitForJob(host, job, startedAt, state)
      status.textContent = result?.message || 'Theme 저장이 완료되었습니다.'
      status.className = 'status ok'
      window.setTimeout(() => window.location.reload(), 900)
    } catch (error) {
      status.textContent = String(asLegacyError(error).message || error)
      status.className = 'status error'
    } finally {
      if (state.tickTimer) window.clearInterval(state.tickTimer)
      state.tickTimer = 0
      state.busy = false
      state.jobId = ''
      state.cancelRequested = false
      if (action) { action.disabled = false; action.textContent = '분석 후 Theme 저장' }
    }
  }, true)
}

export function LayoutThemeDynamicSourceV2() {
  useEffect(() => {
    ensureStyle()
    const scan = () => document.querySelectorAll('.ui-layout-theme-import-panel.unified-source').forEach((panel: LegacyValue) => install(panel))
    scan()
    const observer = new MutationObserver(scan)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  return null
}
