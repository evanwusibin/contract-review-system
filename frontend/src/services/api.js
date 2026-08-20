const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const response = await fetch(url, {
    credentials: 'include', // cookie 会话（HttpOnly）
    headers: { 'Accept': 'application/json' },
    ...options
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.error?.message || body.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function health() {
  return request('/v1/health')
}

// ── Auth（cookie 会话）──
export async function login(username, password) {
  const form = new FormData()
  form.append('username', username)
  form.append('password', password)
  return request('/v1/auth/login', { method: 'POST', body: form })
}

export async function logout() {
  return request('/v1/auth/logout', { method: 'POST' })
}

export async function me() {
  return request('/v1/auth/me')
}

export async function listTasks() {
  return request('/v1/tasks')
}

export async function getTask(taskId) {
  return request(`/v1/tasks/${taskId}`)
}

export async function listVersions(taskId) {
  return request(`/v1/tasks/${taskId}/versions`)
}

export async function getVersion(taskId, versionId) {
  return request(`/v1/tasks/${taskId}/versions/${versionId}`)
}

export async function importContract(externalTaskKey, title, applicantId, file) {
  const form = new FormData()
  form.append('external_task_key', externalTaskKey)
  form.append('title', title)
  form.append('applicant_id', applicantId)
  form.append('file', file)
  return request('/v1/imports', { method: 'POST', body: form })
}

export async function runReview(externalTaskKey, title, applicantId, file, confirmations, actorId) {
  const form = new FormData()
  form.append('external_task_key', externalTaskKey)
  form.append('title', title)
  form.append('applicant_id', applicantId)
  form.append('file', file)
  form.append('confirmations', JSON.stringify(confirmations))
  form.append('actor_id', actorId)
  return request('/v1/reviews/run', { method: 'POST', body: form })
}

export async function listRules() {
  return request('/v1/rules')
}

export async function addRule(ruleCode, name, severity) {
  const form = new FormData()
  form.append('rule_code', ruleCode)
  form.append('name', name)
  form.append('severity', severity)
  return request('/v1/rules', { method: 'POST', body: form })
}

export async function setRuleStatus(ruleId, status) {
  const form = new FormData()
  form.append('status', status)
  return request(`/v1/rules/${ruleId}`, { method: 'PATCH', body: form })
}

export async function listAuditEvents(limit = 50, offset = 0) {
  return request(`/v1/audit/events?limit=${limit}&offset=${offset}`)
}

export async function getTaskAudit(taskId) {
  return request(`/v1/tasks/${taskId}/audit`)
}

export async function getTaskReview(taskId) {
  return request(`/v1/tasks/${taskId}/review`)
}

export async function listPendingApprovals(limit = 10) {
  return request(`/v1/approvals/pending?limit=${limit}`)
}
export async function getApproval(instanceId) {
  return request(`/v1/approvals/${instanceId}`)
}
export async function downloadAttachment(instanceId, attachmentId) {
  return request(`/v1/approvals/${instanceId}/attachments/${attachmentId}/download`, { method: 'POST' })
}
export async function parseDocument(documentId) {
  const form = new FormData()
  form.append('document_id', documentId)
  return request('/v1/tools/parse', { method: 'POST', body: form })
}
export async function runRules(caseId) {
  const form = new FormData()
  form.append('case_id', caseId)
  return request('/v1/tools/rules', { method: 'POST', body: form })
}
export async function saveResult(caseId, overall, summary, focus, comment) {
  const form = new FormData()
  form.append('case_id', caseId)
  form.append('overall_risk_level', overall)
  form.append('summary_text', summary)
  form.append('focus_points_json', JSON.stringify(focus))
  form.append('comment_text', comment)
  return request('/v1/tools/result', { method: 'POST', body: form })
}
export async function writeComment(instanceId, reviewId) {
  const form = new FormData()
  form.append('review_id', reviewId)
  return request(`/v1/approvals/${instanceId}/comments/write`, { method: 'POST', body: form })
}
export async function agentRun(instanceId) {
  const form = new FormData()
  form.append('instance_id', instanceId)
  return request('/v1/agent/run', { method: 'POST', body: form })
}
export async function retryTask(taskId) {
  return request(`/v1/tasks/${taskId}/retry`, { method: 'POST' })
}
export async function getEvidenceGraph(taskId) {
  return request(`/v1/tasks/${taskId}/evidence-graph`)
}
export async function getRiskMatrix(taskId) {
  return request(`/v1/tasks/${taskId}/risk-matrix`)
}
export async function getFlow(taskId) {
  return request(`/v1/tasks/${taskId}/flow`)
}

export const api = {
  health, login, logout, me, listTasks, getTask, listVersions, getVersion,
  importContract, runReview, listRules, addRule, setRuleStatus,
  listAuditEvents, getTaskAudit, getTaskReview,
  listPendingApprovals, getApproval, downloadAttachment, parseDocument, runRules, saveResult, writeComment, agentRun, retryTask
}