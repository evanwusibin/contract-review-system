export function renderDocuments(el) {
  el.innerHTML = `
  <div class="documents-panel">
    <div class="heading">
      <div><h1>合同评审文档</h1><p>集中查看合同原文、评审状态与已保存结论，按合同编号管理独立评审版本。</p></div>
      <div class="actions">
        <button class="btn" id="refreshDocs">刷新列表</button>
        <button class="btn primary" id="newReview">导入合同</button>
      </div>
    </div>
    <div class="page-kpis" id="docKpis">
      <div class="page-kpi card"><b class="blue">…</b><span>全部合同</span></div>
      <div class="page-kpi card"><b>…</b><span>评审中</span></div>
      <div class="page-kpi card"><b class="red">…</b><span>阻塞</span></div>
      <div class="page-kpi card"><b>…</b><span>已确认</span></div>
    </div>
    <div class="prototype-card">
      <div class="card-head"><div><h2>合同文档列表</h2><p>文档状态与评审结论分开记录，点击“查看评审”进入对应工作台。</p></div></div>
      <div id="docList"><div class="loading">加载中…</div></div>
    </div>
  </div>`

  document.getElementById('refreshDocs').addEventListener('click', loadDocuments)
  document.getElementById('newReview').addEventListener('click', async () => {
    const { showReviewForm } = await import('./review-form.js')
    showReviewForm()
  })

  loadDocuments()
}

async function loadDocuments() {
  const listEl = document.getElementById('docList')
  const kpis = document.getElementById('docKpis')
  if (!listEl) return
  listEl.innerHTML = '<div class="loading">加载中…</div>'

  try {
    const { api } = await import('../api.js')
    const resp = await api.listTasks()
    const tasks = resp.data?.items || []

    const total = tasks.length
    const reviewing = tasks.filter(t => ['imported', 'parsing', 'reviewing', 'awaiting_confirmation', 'confirming'].includes(t.status)).length
    const blocked = tasks.filter(t => t.status === 'blocked').length
    const confirmed = tasks.filter(t => t.status === 'confirmed').length

    if (kpis) {
      kpis.innerHTML = `
        <div class="page-kpi card"><b class="blue">${total}</b><span>全部合同</span></div>
        <div class="page-kpi card"><b>${reviewing}</b><span>评审中</span></div>
        <div class="page-kpi card"><b class="red">${blocked}</b><span>阻塞</span></div>
        <div class="page-kpi card"><b>${confirmed}</b><span>已确认</span></div>`
    }

    if (tasks.length === 0) {
      listEl.innerHTML = '<div class="empty-state">暂无合同文档</div>'
      return
    }

    const statusMap = {
      'imported': { label: '已导入', cls: 'blue' },
      'parsing': { label: '解析中', cls: 'amber' },
      'reviewing': { label: '评审中', cls: 'amber' },
      'awaiting_confirmation': { label: '待确认', cls: 'amber' },
      'confirming': { label: '会签中', cls: 'amber' },
      'confirmed': { label: '已确认', cls: 'green' },
      'blocked': { label: '阻塞', cls: 'red' },
      'rejected_recommendation': { label: '建议驳回', cls: 'red' }
    }

    let html = `<table class="prototype-table"><thead><tr><th>合同编号</th><th>合同标题</th><th>创建时间</th><th>状态</th><th>操作</th></tr></thead><tbody>`
    for (const task of tasks) {
      const s = statusMap[task.status] || { label: task.status, cls: 'gray' }
      html += `<tr>
        <td>${task.external_task_key || '-'}</td>
        <td>${task.title || '-'}</td>
        <td>${(task.created_at || '').slice(0, 19).replace('T', ' ')}</td>
        <td><span class="pill ${s.cls}">${s.label}</span></td>
        <td><button class="link" data-task-id="${task.id}">查看评审</button></td>
      </tr>`
    }
    html += '</tbody></table>'
    listEl.innerHTML = html

    document.querySelectorAll('[data-task-id]').forEach(btn => {
      btn.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('open-workbench', { detail: { taskId: btn.dataset.taskId } }))
      })
    })
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">加载失败：${err.message}</div>`
  }
}