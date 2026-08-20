export async function renderRiskMatrix(container, taskId) {
  const { getRiskMatrix } = await import('../../services/api.js')
  try {
    const resp = await getRiskMatrix(taskId)
    const data = resp.data || {}
    const counts = data.counts || { high: 0, medium: 0, low: 0 }
    const matrix = data.matrix || {}
    const overall = data.overall_risk_level || 'low'
    const color = { high: 'var(--red)', medium: '#d97706', low: 'var(--green)' }
    container.innerHTML = `
      <div class="card" style="margin-top:12px">
        <div class="card-head"><div><h2>风险矩阵</h2><span class="subtle">高/中/低分层 · 命中证据可定位</span></div><span class="pill ${overall === 'high' ? 'red' : overall === 'medium' ? 'amber' : 'green'}">${overall.toUpperCase()}</span></div>
        <div class="review-body">
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
            ${['high','medium','low'].map(k => `
              <div style="border:1px solid #eef2f7;border-radius:10px;padding:12px;background:${k === overall ? '#fff7ed' : '#fff'}">
                <div style="font-size:11px;color:#6b7280">${k.toUpperCase()}</div>
                <div style="font-size:22px;font-weight:700;color:${color[k]}">${counts[k] || 0}</div>
                <div style="font-size:11px;color:#6b7280">${(matrix[k] || []).slice(0,2).map(r => r.message).join(' / ') || '—'}</div>
              </div>`).join('')}
          </div>
        </div>
      </div>`
  } catch (e) {
    container.innerHTML = `<div class="card" style="margin-top:12px"><div class="review-body" style="color:#6b7280;font-size:12px">风险矩阵加载失败：${e.message}</div></div>`
  }
}
