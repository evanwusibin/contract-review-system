import { getUser } from '../auth.js'

export function renderRules(el) {
  el.innerHTML = `
  <div class="rules-panel">
    <div class="heading">
      <div><h1>规则中心</h1><p>管理合同审查规则，包括规则版本、生效时间和适用范围。</p></div>
      <div class="actions"><button class="btn primary" id="newRule">新增规则</button></div>
    </div>
    <div id="rulesList"><div class="loading">加载中…</div></div>
    <div class="notice-box" style="margin-top:16px">
      <span class="notice-tag">HP-001</span>
      <p>付款比例和账期阈值在正式制度来源确认前，仅能作为人工复核提示，不能作为自动驳回规则。</p>
    </div>
  </div>`

  loadRules()
  document.getElementById('newRule').addEventListener('click', () => {
    import('../utils.js').then(({ showToast }) => showToast('新增规则需管理员权限，暂未开放'))
  })
}

async function loadRules() {
  const listEl = document.getElementById('rulesList')
  if (!listEl) return
  listEl.innerHTML = '<div class="loading">加载中…</div>'
  try {
    const { api } = await import('../api.js')
    const resp = await api.listRules()
    const rules = resp.data?.items || []

    if (rules.length === 0) {
      listEl.innerHTML = '<div class="empty-state">暂无规则</div>'
      return
    }

    const sevMap = { high: 'red', medium: 'amber', low: 'green' }
    const sevLabel = { high: '高风险', medium: '中风险', low: '低风险' }
    const statusLabel = { published: '已发布', draft: '草稿', retired: '已退役' }
    const isAdmin = getUser()?.role === 'admin'

    let html = `<div class="prototype-card"><div class="card-head"><div><h2>已发布规则</h2><p>规则来源可追溯到制度、标准合同或正式规则清单</p></div><span class="pill blue">${rules.length} 条</span></div>`
    html += `<div class="rule-card" style="margin-top:14px">`
    for (const rule of rules) {
      const dotColor = sevMap[rule.severity] === 'red' ? 'var(--red)' : sevMap[rule.severity] === 'amber' ? '#f59e0b' : 'var(--green)'
      const actions = isAdmin
        ? `<div class="rule-actions">
             ${rule.status === 'published'
               ? `<button class="rule-action-btn danger" data-rule-id="${rule.id}" data-status="retired">退役</button>`
               : rule.status === 'retired'
                 ? `<button class="rule-action-btn" data-rule-id="${rule.id}" data-status="published">重新发布</button>`
                 : `<button class="rule-action-btn" data-rule-id="${rule.id}" data-status="published">发布</button>`}
           </div>`
        : ''
      html += `<div class="risk"><i class="risk-dot" style="background:${dotColor}"></i><div>
        <div class="risk-title">${rule.name}　<span class="pill ${sevMap[rule.severity]}">${sevLabel[rule.severity]}</span> <span class="pill green">${statusLabel[rule.status] || rule.status}</span></div>
        <div class="risk-meta"><span class="rule-code">${rule.rule_code} · v${rule.version}</span> <span>来源：${rule.source_ref || '-'}</span></div>
        <div class="risk-desc">适用类型：${(rule.contract_types || []).join(' / ') || '-'}</div>
        ${actions}
      </div></div>`
    }
    html += `</div></div>`
    listEl.innerHTML = html

    listEl.querySelectorAll('.rule-action-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const ruleId = btn.dataset.ruleId
        const status = btn.dataset.status
        const { api, showToast } = await Promise.all([import('../api.js'), import('../utils.js')])
        btn.disabled = true
        try {
          await api.setRuleStatus(ruleId, status)
          showToast(status === 'published' ? '规则已发布' : '规则已退役', 'success')
          loadRules()
        } catch (err) {
          showToast(`操作失败：${err.message}`, 'error')
          btn.disabled = false
        }
      })
    })
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">加载失败：${err.message}</div>`
  }
}
