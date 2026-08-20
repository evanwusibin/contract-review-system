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
    let tasks = []
    let source = 'store'
    try {
      const pending = await api.listPendingApprovals(20)
      if (pending.data?.items?.length) {
        tasks = pending.data.items.map(it => ({
          id: it.instance_id,
          external_task_key: it.approval_code || it.instance_id,
          title: it.approval_title || it.title,
          applicant_id: it.applicant_name || it.applicant_id,
          applicant_time: it.applicant_time || it.apply_time,
          attachment_count: it.attachment_count,
          status: it.status || 'pending',
          write_status: it.write_status || 'not_written',
          _isMock: pending.data.source === 'mock'
        }))
        source = pending.data.source
      }
    } catch {}
    if (!tasks.length) {
      const resp = await api.listTasks()
      tasks = resp.data?.items || []
      source = 'store'
    }

    if (countEl) countEl.textContent = `${tasks.length} 项待处理`
    if (tasks.length === 0) {
      listEl.innerHTML = '<div class="empty-state">暂无待处理任务</div>'
      return
    }

    const statusMap = {
      'pending': { label: '待处理', cls: 'blue' },
      'imported': { label: '已导入', cls: 'blue' },
      'parsing': { label: '解析中', cls: 'amber' },
      'reviewing': { label: '评审中', cls: 'amber' },
      'awaiting_confirmation': { label: '待确认', cls: 'amber' },
      'confirming': { label: '会签中', cls: 'amber' },
      'confirmed': { label: '已确认', cls: 'green' },
      'done': { label: '已完成', cls: 'green' },
      'blocked': { label: '阻塞', cls: 'red' },
      'rejected_recommendation': { label: '建议驳回', cls: 'red' }
    }
    const writeMap = { 'not_written': '未回写', 'writing': '回写中', 'success': '已回写', 'failed': '回写失败' }

    let html = `<div class="hint" style="margin-bottom:8px;color:#6b7280;font-size:12px">数据来源：${source === 'mock' ? '模拟审批系统（演示）' : '真实任务库'} · 回写状态满足 2.4.4</div>`
    for (const task of tasks) {
      const s = statusMap[task.status] || { label: task.status, cls: 'gray' }
      const ws = task.write_status ? `<span class="pill gray" style="margin-left:6px">${writeMap[task.write_status] || task.write_status}</span>` : ''
      const meta = task.attachment_count != null
        ? `${task.external_task_key} · 申请人：${task.applicant_id || '-'} · 附件 ${task.attachment_count} 个 · ${(task.applicant_time || task.created_at || '').slice(0, 19).replace('T', ' ')}`
        : `${task.external_task_key} · 申请人：${task.applicant_id || '-'} · ${(task.created_at || '').slice(0, 19).replace('T', ' ')}`
      const retryBtn = task.status === 'blocked' ? `<button class="btn small" data-retry="${task.id}" style="margin-left:8px">重试</button>` : ''
      const agentBtn = `<button class="btn small primary" data-agent="${task.external_task_key}" style="margin-left:8px"><svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg> Agent 闭环</button>`
      html += `
        <div class="task-item" data-task-id="${task.id}" data-open-review="true">
          <div>
            <div class="task-title">${task.title || task.external_task_key}</div>
            <div class="task-meta">${meta}</div>
          </div>
          <div style="display:flex;align-items:center">
            <span class="pill ${s.cls} task-status">${s.label}</span>${ws}${retryBtn}${agentBtn}
          </div>
        </div>`
    }
    listEl.innerHTML = html

    document.querySelectorAll('[data-open-review="true"]').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('[data-retry]') || e.target.closest('[data-agent]')) return
        window.dispatchEvent(new CustomEvent('open-workbench', { detail: { taskId: item.dataset.taskId } }))
      })
    })
    document.querySelectorAll('[data-retry]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation()
        const { api } = await import('../api.js')
        const { showToast } = await import('../utils.js')
        try { await api.retryTask(btn.dataset.retry); showToast('已重试，进入 parsing'); loadTasks() } catch (err) { showToast(err.message) }
      })
    })
    document.querySelectorAll('[data-agent]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation()
        const { api } = await import('../api.js')
        const { showToast } = await import('../utils.js')
        btn.textContent = '执行中…'; btn.disabled = true
        try { const r = await api.agentRun(btn.dataset.agent); showToast(`Agent 完成：${r.data.final_status} 风险 ${r.data.overall_risk_level || '-'}`); loadTasks() } catch (err) { showToast(err.message) } finally { btn.disabled = false; btn.innerHTML = '<svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg> Agent 闭环' }
      })
    })
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">加载失败：${err.message}</div>`
  }
}