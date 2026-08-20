import { api } from '../api.js'
import { showToast } from '../utils.js'

const ROLE_LABELS = {
  business: { label: '业务负责人', desc: '等待确认付款与商务条件' },
  legal: { label: '法务审核人', desc: '已确认条款风险' },
  warranty: { label: '售后/质保负责人', desc: '等待确认质保责任' }
}

const REC_LABELS = {
  pass: { text: '建议通过', cls: 'green' },
  reject: { text: '建议驳回', cls: 'red' },
  manual_review: { text: '建议人工复核', cls: 'amber' }
}

const FIELD_LABELS = {
  party_a: '甲方', party_b: '乙方', contract_no: '合同编号',
  amount: '金额', currency: '币种', signed_date: '签订日期', warranty_term: '质保期'
}

export function renderWorkbench(el, taskId) {
  el.innerHTML = `<div class="loading">正在载入评审工作台…</div>`
  loadWorkbench(el, taskId)
}

async function loadWorkbench(el, taskId) {
  try {
    const resp = await api.getTaskReview(taskId)
    const { task, attachments, latest_version: version, review, parse } = resp.data || {}

    const docName = attachments?.[0]?.file_name || task?.title || '合同文档'
    const statusMap = {
      'pending': { label: '待处理', cls: 'blue' }, 'imported': { label: '已导入', cls: 'blue' }, 'parsing': { label: '解析中', cls: 'amber' },
      'reviewing': { label: '评审中', cls: 'amber' }, 'awaiting_confirmation': { label: '待确认', cls: 'amber' },
      'confirming': { label: '会签中', cls: 'amber' }, 'confirmed': { label: '已确认', cls: 'green' }, 'done': { label: '已完成', cls: 'green' },
      'blocked': { label: '阻塞', cls: 'red' }, 'rejected_recommendation': { label: '建议驳回', cls: 'red' }
    }
    const writeMap = { 'not_written': { label: '未回写', cls: 'gray' }, 'writing': { label: '回写中', cls: 'amber' }, 'success': { label: '已回写', cls: 'green' }, 'failed': { label: '回写失败', cls: 'red' } }
    const st = statusMap[task?.status] || { label: task?.status || '-', cls: 'gray' }
    const ws = writeMap[task?.write_status] || null

    el.innerHTML = `
      <div class="heading">
        <div>
          <h1>${task?.title || '合同评审'}</h1>
          <p>${task?.external_task_key || ''} · 申请人：${task?.applicant_id || '-'} · <span class="pill ${st.cls}">${st.label}</span>${ws ? ` <span class="pill ${ws.cls}" title="2.4.4 回写状态"><svg class="svg-icon" aria-hidden="true"><use href="#icon-shield"></use></svg> ${ws.label}</span>` : ''}</p>
          <p style="font-size:11px;color:#6b7280;margin-top:4px">5大工具链：待办→详情→解析→规则→保存→回写 · Agent 可一键闭环</p>
        </div>
        <div class="actions">
          <button class="btn" id="wbAgent"><svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg> Agent 闭环</button>
          <button class="btn" id="wbRetry" style="${task?.status === 'blocked' ? '' : 'display:none'}">重试解析</button>
          <button class="btn" id="wbBack">返回列表</button>
          <button class="btn primary" id="wbAudit">查看审计</button>
        </div>
      </div>
      <div class="workspace">
        ${renderSource(docName, task, parse, attachments)}
        ${renderReview(task, review, version, parse)}
      </div>
      <div id="wbInsights" style="display:grid;gap:12px;margin-top:12px">
        <div id="wbFlowDag"></div>
        <div id="wbRiskMatrix"></div>
        <div id="wbEvidenceGraph"></div>
      </div>
      <div id="wbTrajectory" class="card" style="margin-top:12px;display:none"><div class="card-head"><h2>Agent 轨迹</h2><span class="subtle">工具调用链路可观测</span></div><div class="review-body" id="wbTrajectoryBody"></div></div>
      <div class="footer-note">原型数据为脱敏示例，仅用于确认交互和业务流程，不代表正式评审结论。</div>`

    document.getElementById('wbBack').addEventListener('click', () => {
      document.querySelector('.nav button[data-page="tasks"]')?.click()
    })
    document.getElementById('wbAudit').addEventListener('click', () => {
      showToast('已进入任务审计视图')
    })
    const agentBtn = document.getElementById('wbAgent')
    if (agentBtn) agentBtn.addEventListener('click', async () => {
      agentBtn.textContent = '执行中…'; agentBtn.disabled = true
      try {
        const r = await api.agentRun(task.external_task_key || taskId)
        const d = r.data
        showToast(`Agent 完成：${d.final_status} 风险 ${d.overall_risk_level || '-'}`)
        document.getElementById('wbTrajectory').style.display = 'block'
        document.getElementById('wbTrajectoryBody').innerHTML = (d.trajectory || []).map(s => `<div style="padding:6px 0;border-bottom:1px solid #f0f0f0"><b>${s.step}</b> · ${s.tool} · <span class="pill ${s.status === 'success' ? 'green' : s.status === 'blocked' ? 'red' : 'gray'}">${s.status}</span><div style="font-size:11px;color:#6b7280">${s.thought}</div></div>`).join('')
        setTimeout(() => loadWorkbench(el, taskId), 800)
      } catch (e) { showToast(e.message) } finally { agentBtn.disabled = false; agentBtn.innerHTML = '<svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg> Agent 闭环' }
    })
    const retryBtn = document.getElementById('wbRetry')
    if (retryBtn) retryBtn.addEventListener('click', async () => {
      try { await api.retryTask(taskId); showToast('已重试，进入 parsing'); loadWorkbench(el, taskId) } catch (e) { showToast(e.message) }
    })

    // 业务深化：证据图谱 / 风险矩阵 / 审批流图
    try {
      const [{ renderFlowDag }, { renderRiskMatrix }, { renderEvidenceGraph }] = await Promise.all([
        import('../../components/insights/flow-dag.js'),
        import('../../components/insights/risk-matrix.js'),
        import('../../components/insights/evidence-graph.js')
      ])
      renderFlowDag(document.getElementById('wbFlowDag'), taskId)
      renderRiskMatrix(document.getElementById('wbRiskMatrix'), taskId)
      renderEvidenceGraph(document.getElementById('wbEvidenceGraph'), taskId)
    } catch { /* insights 失败不阻塞主流程 */ }
  } catch (err) {
    el.innerHTML = `<div class="empty-state">加载失败：${err.message}</div>`
  }
}

/* ── 左栏：原文证据 ── */
function renderSource(docName, task, parse, attachments) {
  const fields = parse?.extracted_payload || {}
  const hasFields = Object.keys(fields).length > 0
  const qualityScore = parse?.quality_score

  // 构造合同原文视图：基于抽取字段 + 证据片段
  let bodyHtml = ''
  if (hasFields) {
    bodyHtml = `<div class="doc-meta"><span>${docName}</span><span>合同编号：${task?.external_task_key || '-'}</span></div>
      <h3>${task?.title || '合同文档'}</h3>`
    for (const [key, field] of Object.entries(fields)) {
      const label = FIELD_LABELS[key] || key
      if (!field) continue
      if (field.evidence && field.evidence.snippet) {
        const status = field.status === 'missing' ? 'bad' : ''
        bodyHtml += `<h4>${label}</h4>
          <p>…${mark(field.evidence.snippet, status)}…</p>`
      } else {
        const value = field.value || '【未识别】'
        const status = field.status === 'missing' ? 'bad' : ''
        bodyHtml += `<h4>${label}</h4><p><span class="mark ${status}">${value}</span></p>`
      }
    }
    bodyHtml += `<div class="page-foot">— 第 1 页 / 共 ${attachments?.[0]?.page_count || 1} 页 —</div>`
  } else {
    bodyHtml = `<div class="doc-meta"><span>${docName}</span><span>尚未解析</span></div>
      <h3>${task?.title || '合同文档'}</h3>
      <p>该合同尚未完成 OCR 解析，或解析结果暂不可用。请先执行评审流程生成解析结果。</p>
      <div class="page-foot">— —</div>`
  }

  return `
    <section class="source card">
      <div class="card-head">
        <div><h2>原文证据</h2><span class="subtle">页码、段落与高亮定位</span></div>
        <div class="source-toolbar">
          <button class="icon-btn" title="缩小">−</button>
          <button class="icon-btn" title="放大">+</button>
        </div>
      </div>
      ${qualityScore !== undefined ? `<div class="quality"><b>解析质量</b>综合置信度 ${qualityScore} / 100 · 识别结果可人工修正</div>` : ''}
      <div class="document">${bodyHtml}</div>
    </section>`
}

function mark(text, cls) {
  return `<span class="mark ${cls || ''}">${escapeHtml(text)}</span>`
}

/* ── 右栏：审核工作区 ── */
function renderReview(task, review, version, parse) {
  const fields = parse?.extracted_payload || {}
  const riskSummary = review?.risk_summary || version?.risk_summary || {}
  const rec = review?.recommendation || version?.recommendation
  const recMeta = REC_LABELS[rec] || { text: rec || '待生成', cls: 'amber' }
  const requiredRoles = review?.required_roles || []
  const confirmedRoles = review?.confirmed_roles || []

  // 字段卡
  let fieldHtml = ''
  if (Object.keys(fields).length > 0) {
    const fieldItems = Object.entries(fields).map(([key, field]) => {
      if (!field) return ''
      const label = FIELD_LABELS[key] || key
      const value = field.value || '缺失'
      const warn = field.status === 'missing' ? ' warn' : ''
      const confText = field.status === 'missing'
        ? '<span style="color:var(--red)">关键字段 · 自动建议驳回</span>'
        : `识别置信度 ${Math.round((field.confidence || 0) * 100)}%`
      return `<div class="field"><div class="field-label">${label}</div><div class="field-value${warn}">${value}</div><div class="confidence">${confText}</div></div>`
    }).join('')
    fieldHtml = `<div class="field-grid">${fieldItems}</div>`
  } else {
    fieldHtml = `<div class="review-body"><p style="font-size:11px;color:var(--sub)">暂无结构化字段。请先执行评审。</p></div>`
  }

  // 风险卡
  const highCount = riskSummary.high || 0
  const medCount = riskSummary.medium || 0
  const lowCount = riskSummary.low || 0
  let riskHtml = ''
  if (highCount + medCount + lowCount > 0) {
    const risks = []
    if (highCount > 0) risks.push({ cls: '', title: '合同主体不完整', desc: '乙方名称未识别，无法确认合同责任主体。', meta: 'RULE-PARTY-001 · 高风险' })
    if (medCount > 0) risks.push({ cls: 'amber', title: '付款期限待确认', desc: '付款周期无法识别，正式阈值尚未发布。', meta: 'HP-001 · 待业务确认' })
    if (lowCount > 0) risks.push({ cls: '', title: '低风险提示', desc: '存在低风险事项，建议关注。', meta: '规则命中' })
    riskHtml = `<div class="review-body">${risks.map(r => `
      <div class="risk"><i class="risk-dot ${r.cls}"></i><div>
        <div class="risk-title">${r.title}</div>
        <div class="risk-desc">${r.desc}</div>
        <div class="risk-meta">${r.meta} <button class="link evidence">定位证据</button></div>
      </div></div>`).join('')}</div>`
  } else {
    riskHtml = `<div class="review-body"><p style="font-size:11px;color:var(--sub)">暂无规则命中</p></div>`
  }

  // 建议卡
  const commentVal = review?.review_comment || version?.comment || ''
  const statusText = review?.status === 'confirmed' ? '已确认' : '待确认'

  // 会签卡
  let eventsHtml = ''
  if (requiredRoles.length > 0) {
    eventsHtml = `<div class="review-body"><div class="events">${requiredRoles.map(role => {
      const meta = ROLE_LABELS[role] || { label: role, desc: '等待确认' }
      const done = Array.isArray(confirmedRoles) ? confirmedRoles.includes(role) : (confirmedRoles[role] !== undefined)
      return `<div class="event"><time>${done ? '已完成' : '待确认'}</time><div><b>${meta.label}</b>　${done ? '已确认' : meta.desc}</div></div>`
    }).join('')}</div></div>`
  } else {
    eventsHtml = `<div class="review-body"><p style="font-size:11px;color:var(--sub)">暂无会签信息</p></div>`
  }

  return `
    <section class="review">
      <div class="card">
        <div class="card-head">
          <div><h2>审批信息与结构化字段</h2><span class="subtle">识别结果可人工修正，修改进入审计记录</span></div>
          <span class="pill amber">${task?.status === 'confirmed' ? '已确认' : '部分解析'}</span>
        </div>
        ${fieldHtml}
      </div>
      <div class="card">
        <div class="card-head">
          <div><h2>风险与规则命中</h2><span class="subtle">点击风险项，左侧定位对应证据</span></div>
          <button class="link">查看全部 ${highCount + medCount + lowCount} 项</button>
        </div>
        ${riskHtml}
      </div>
      <div class="card">
        <div class="card-head">
          <div><h2>审批建议</h2><span class="subtle">建议不等于最终审批</span></div>
          <span class="pill ${recMeta.cls}">${statusText}</span>
        </div>
        <div class="review-body">
          <div class="recommend">
            <div><strong style="color:var(--red)">${recMeta.text}</strong>
              <small>${rec === 'reject' ? '原因：关键主体缺失 + 质保责任缺失' : '由确定性规则与人工会签共同形成'}</small></div>
            <div class="recommend-actions">
              <button class="btn" id="wbManual">要求补证</button>
              <button class="btn" id="wbReject">确认驳回建议</button>
            </div>
          </div>
          <label class="subtle" style="margin-top:12px">审核意见（必填）</label>
          <textarea class="comment" id="wbComment">${escapeHtml(commentVal)}</textarea>
        </div>
      </div>
      <div class="card">
        <div class="card-head">
          <div><h2>责任人与会签</h2><span class="subtle">所有必需角色确认后才可形成正式结论</span></div>
          <span class="pill amber">${confirmedRoles.length} / ${requiredRoles.length}</span>
        </div>
        ${eventsHtml}
      </div>
    </section>`
}

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]))
}