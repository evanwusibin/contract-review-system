export function renderVersions(el) {
  el.innerHTML = `
  <div class="versions-panel">
    <div class="heading">
      <div><h1>合同版本管理</h1><p>查看和管理合同评审的历史版本，支持版本对比和恢复。</p></div>
    </div>
    <div class="card" style="padding:16px">
      <div class="form-row">
        <label>选择任务</label>
        <select id="versionTaskSelect"><option value="">请选择任务…</option></select>
      </div>
      <div class="archive">
        <div class="card-head"><div><h2>评审归档</h2><span class="subtle">版本只追加，不覆盖历史</span></div><span id="archiveCount" class="pill blue">0 份</span></div>
        <div id="versionList" class="archive-list"><div class="empty-state" style="grid-column:1/-1">请选择一个任务查看版本</div></div>
      </div>
    </div>
  </div>`

  loadTaskList()
  document.getElementById('versionTaskSelect').addEventListener('change', async (e) => {
    const taskId = e.target.value
    if (taskId) await loadVersions(taskId)
  })
}

async function loadTaskList() {
  const select = document.getElementById('versionTaskSelect')
  if (!select) return
  try {
    const { api } = await import('../api.js')
    const resp = await api.listTasks()
    const tasks = resp.data?.items || []
    select.innerHTML = '<option value="">请选择任务…</option>'
    for (const task of tasks) {
      select.innerHTML += `<option value="${task.id}">${task.external_task_key || task.title || task.id}</option>`
    }
  } catch { /* 静默失败 */ }
}

async function loadVersions(taskId) {
  const listEl = document.getElementById('versionList')
  const countEl = document.getElementById('archiveCount')
  if (!listEl) return
  listEl.innerHTML = '<div class="loading" style="grid-column:1/-1">加载中…</div>'
  try {
    const { api } = await import('../api.js')
    const resp = await api.listVersions(taskId)
    const versions = resp.data?.items || []
    if (countEl) countEl.textContent = `${versions.length} 份`

    if (versions.length === 0) {
      listEl.innerHTML = '<div class="empty-state" style="grid-column:1/-1">暂无版本记录</div>'
      return
    }

    const recLabel = {
      pass: '建议通过', reject: '建议驳回', manual_review: '建议人工复核'
    }
    const recColor = { pass: 'green', reject: 'red', manual_review: 'amber' }

    let html = ''
    for (const v of versions) {
      const r = recLabel[v.recommendation] || v.recommendation || ''
      const rc = recColor[v.recommendation] || 'blue'
      html += `<div class="archive-item">
        <b>v${v.version_no} · <span class="pill ${rc}">${r}</span></b>
        <span>${(v.created_at || '').slice(0, 19).replace('T', ' ')}</span>
        <button class="link" data-task="${taskId}" data-version="${v.id}">恢复查看</button>
      </div>`
    }
    listEl.innerHTML = html

    document.querySelectorAll('[data-version]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const { api } = await import('../api.js')
        const { showToast } = await import('../utils.js')
        try {
          await api.getVersion(btn.dataset.task, btn.dataset.version)
          showToast('已恢复版本视图，只读模式')
        } catch (err) {
          showToast('版本加载失败：' + err.message, 'error')
        }
      })
    })
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state" style="grid-column:1/-1">加载失败：${err.message}</div>`
  }
}