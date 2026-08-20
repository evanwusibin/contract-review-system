import { api } from '../api.js'
import { showToast } from '../utils.js'

let overlay = null
let modal = null

export async function showReviewForm() {
  if (overlay) return

  overlay = document.createElement('div')
  overlay.className = 'modal-overlay'
  modal = document.createElement('div')
  modal.className = 'modal'
  modal.innerHTML = `
    <div class="modal-header">
      <h2>新建合同评审</h2>
      <button class="modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label>外部任务编号 <span class="req">*</span></label>
        <input id="reviewKey" placeholder="如 CR-2026-0019">
      </div>
      <div class="form-group">
        <label>合同标题 <span class="req">*</span></label>
        <input id="reviewTitle" placeholder="如 售后服务合同">
      </div>
      <div class="form-group">
        <label>申请人编号 <span class="req">*</span></label>
        <input id="reviewApplicant" placeholder="如 user-001">
      </div>
      <div class="form-group">
        <label>合同文件 <span class="req">*</span></label>
        <input type="file" id="reviewFile" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg">
      </div>
      <div class="form-group">
        <label>会签确认（JSON，可选）</label>
        <textarea id="reviewConfirm" placeholder='{"法务审核人": ["actor-001", "同意"]}'>{"法务审核人": ["legal.reviewer", "确认条款风险"]}</textarea>
      </div>
      <div class="form-actions">
        <button class="btn" id="reviewCancel">取消</button>
        <button class="btn primary" id="reviewSubmit">提交评审</button>
      </div>
      <div id="reviewStatus"></div>
    </div>`
  overlay.appendChild(modal)
  document.body.appendChild(overlay)

  document.querySelector('.modal-close').addEventListener('click', closeModal)
  document.getElementById('reviewCancel').addEventListener('click', closeModal)
  document.getElementById('reviewSubmit').addEventListener('click', submitReview)
}

function closeModal() {
  if (overlay) {
    document.body.removeChild(overlay)
    overlay = null
    modal = null
  }
}

async function submitReview() {
  const statusEl = document.getElementById('reviewStatus')
  const key = document.getElementById('reviewKey').value.trim()
  const title = document.getElementById('reviewTitle').value.trim()
  const applicant = document.getElementById('reviewApplicant').value.trim()
  const fileInput = document.getElementById('reviewFile')

  if (!key || !title || !applicant || !fileInput.files[0]) {
    statusEl.innerHTML = '<span class="error">请填写所有必填项并选择文件</span>'
    return
  }

  statusEl.innerHTML = '<span class="loading">正在提交评审…</span>'

  try {
    const confirmRaw = document.getElementById('reviewConfirm').value.trim()
    let confirmations = {}
    try { confirmations = JSON.parse(confirmRaw) } catch { confirmations = {} }

    // 确保所有 required_roles 都有确认信息
    // workflow.run 要求 confirmations 包含每个 required_role 的 (actor_id, comment) 元组
    const user = JSON.parse(localStorage.getItem('contract_review_user') || '{}')
    const userId = user.name || applicant || 'user'
    const roles = ['business', 'legal', 'warranty']
    const normalized = {}
    for (const role of roles) {
      const entry = confirmations[role]
      if (entry) {
        // 已有确认信息：兼容 [actor, comment] 和 [user, comment] 两种格式
        normalized[role] = Array.isArray(entry) ? [userId, entry[1] || '确认'] : [userId, '确认']
      } else {
        normalized[role] = [userId, '确认']
      }
    }

    const resp = await api.runReview(key, title, applicant, fileInput.files[0], normalized, applicant || 'user')
    const data = resp.data || {}
    statusEl.innerHTML = `
      <div class="success-box">
        <strong>评审完成</strong>
        <p>任务ID：${data.task_id}</p>
        <p>版本ID：${data.version_id}</p>
        <p>评审状态：${data.review_status || 'unknown'}</p>
        <p>是否重复：${data.duplicate ? '是' : '否'}</p>
        ${data.writeback ? `<p>回写：${JSON.stringify(data.writeback)}</p>` : ''}
        <span class="simulated-tag">SIMULATED_ONLY</span>
      </div>`
    showToast('评审提交成功')
  } catch (err) {
    statusEl.innerHTML = `<span class="error">提交失败：${err.message}</span>`
    showToast('评审提交失败', 'error')
  }
}