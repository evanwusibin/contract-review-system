export function renderTasks(el) {
  el.innerHTML = `
  <div class="task-panel">
    <div class="heading">
      <div><h1>待审合同任务</h1><p>来自审批系统的待处理审批单 · 按业务编号去重</p></div>
      <div class="actions">
        <button class="btn" id="refreshTasks">刷新待办</button>
        <button class="btn primary" id="newReview">新建合同评审</button>
      </div>
    </div>
    <div class="card" style="padding:16px">
      <div class="flow-title">
        <h2>待处理审批单</h2>
        <span id="taskCount" class="pill blue">加载中…</span>
      </div>
      <div id="taskList" class="task-list"><div class="loading">加载中…</div></div>
    </div>
  </div>`

  loadTasks()

  document.getElementById('refreshTasks').addEventListener('click', loadTasks)
  document.getElementById('newReview').addEventListener('click', async () => {
    const { showReviewForm } = await import('./review-form.js')
    showReviewForm()
  })
}

async function loadTasks() {
  const listEl = document.getElementById('taskList')
  const countEl = document.getElementById('taskCount')
  if (!listEl) return
  listEl.innerHTML = '<div class="loading">加载中…</div>'

  try {
    const { api } = await import('../api.js')
    const resp = await api.listTasks()
    const tasks = resp.data?.items || []

    if (countEl) countEl.textContent = `${tasks.length} 项待处理`
    if (tasks.length === 0) {
      listEl.innerHTML = '<div class="empty-state">暂无待处理任务</div>'
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

    let html = ''
    for (const task of tasks) {
      const s = statusMap[task.status] || { label: task.status, cls: 'gray' }
      html += `
        <div class="task-item" data-task-id="${task.id}" data-open-review="true">
          <div>
            <div class="task-title">${task.title || task.external_task_key}</div>
            <div class="task-meta">${task.external_task_key} · 申请人：${task.applicant_id || '-'} · ${(task.created_at || '').slice(0, 19).replace('T', ' ')}</div>
          </div>
          <span class="pill ${s.cls} task-status">${s.label}</span>
        </div>`
    }
    listEl.innerHTML = html

    document.querySelectorAll('[data-open-review="true"]').forEach(item => {
      item.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('open-workbench', { detail: { taskId: item.dataset.taskId } }))
      })
    })
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">加载失败：${err.message}</div>`
  }
}