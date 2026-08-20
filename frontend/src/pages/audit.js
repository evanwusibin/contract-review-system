export function renderAudit(el) {
  el.innerHTML = `
  <div class="audit-panel">
    <div class="heading">
      <div><h1>审计记录</h1><p>查看操作日志、状态变更和会签记录。</p></div>
      <div class="actions"><button class="btn" id="refreshAudit">刷新记录</button></div>
    </div>
    <div class="prototype-card">
      <div class="card-head"><div><h2>系统审计事件</h2><p>登录、退出、补录、重试、保存、建议提交等操作全部留痕</p></div><span id="auditCount" class="pill blue">加载中…</span></div>
      <div id="auditList" class="audit-list"><div class="loading">加载中…</div></div>
    </div>
  </div>`

  loadAudit()
  document.getElementById('refreshAudit').addEventListener('click', loadAudit)
}

async function loadAudit() {
  const listEl = document.getElementById('auditList')
  const countEl = document.getElementById('auditCount')
  if (!listEl) return
  listEl.innerHTML = '<div class="loading">加载中…</div>'
  try {
    const { api } = await import('../api.js')
    const resp = await api.listAuditEvents(100, 0)
    const logs = resp.data?.items || []

    if (countEl) countEl.textContent = `${resp.data?.total || 0} 条`
    if (logs.length === 0) {
      listEl.innerHTML = '<div class="empty-state">暂无审计记录</div>'
      return
    }

    const actionLabel = {
      imported: '导入合同', import_blocked: '导入阻塞', quality_usable: '质量可用',
      quality_blocked: '质量阻塞', quality_retry: '质量重试', parse_started: '解析开始',
      parse_succeeded: '解析成功', parse_failed: '解析失败', recommendation_created: '生成建议',
      comment_confirm: '会签确认', comment_reject: '驳回建议', comment_request_evidence: '要求补证',
      result_confirmed: '结论确认', confirmation_rejected: '确认被拒', review_version_saved: '保存版本'
    }

    let html = ''
    for (const log of logs) {
      const action = actionLabel[log.action] || log.action
      const time = (log.created_at || '').slice(0, 19).replace('T', ' ')
      const after = log.after_state?.status || log.after_state?.recommendation || ''
      html += `<div class="audit-item">
        <time>${time}</time>
        <div><b>${action}</b><span>　${log.actor_id || 'system'} · ${(log.resource_id || '').slice(0, 8)}</span></div>
        <span class="pill ${log.action.includes('fail') || log.action.includes('block') ? 'red' : 'green'}">${after || '完成'}</span>
      </div>`
    }
    listEl.innerHTML = html
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">加载失败：${err.message}</div>`
  }
}