export async function renderFlowDag(container, taskId) {
  const { getFlow } = await import('../../services/api.js')
  try {
    const resp = await getFlow(taskId)
    const data = resp.data || {}
    const flow = data.flow || []
    const logs = data.logs || []
    const statusColor = { done: '#10b981', current: '#f59e0b', pending: '#9ca3af', blocked: '#ef4444' }
    container.innerHTML = `
      <div class="card" style="margin-top:12px">
        <div class="card-head"><div><h2>审批流图</h2><span class="subtle">pending → parsing → reviewing → done / blocked · write: ${data.write_status || '-'}</span></div><span class="pill ${data.current_status === 'blocked' ? 'red' : data.current_status === 'done' ? 'green' : 'amber'}">${data.current_status || '-'}</span></div>
        <div class="review-body">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            ${flow.map((n, i) => `
              <div style="display:flex;align-items:center;gap:8px">
                <div style="min-width:88px;text-align:center;border:1px solid ${n.status === 'current' ? '#f59e0b' : '#e5e7eb'};border-radius:10px;padding:8px 10px;background:${n.status === 'done' ? '#f0fdf4' : n.status === 'blocked' ? '#fef2f2' : n.status === 'current' ? '#fffbeb' : '#fff'}">
                  <div style="width:10px;height:10px;border-radius:50%;background:${statusColor[n.status] || '#9ca3af'};margin:0 auto 4px"></div>
                  <div style="font-size:12px;font-weight:600">${n.label}</div>
                  <div style="font-size:10px;color:#6b7280">${n.status}</div>
                </div>
                ${i < flow.length - 1 ? `<div style="width:24px;height:2px;background:#e5e7eb"></div>` : ''}
              </div>`).join('')}
          </div>
          ${flow.find(n => n.reason) ? `<div style="margin-top:8px;font-size:11px;color:#991b1b;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:8px">阻塞原因：${flow.find(n => n.reason).reason}</div>` : ''}
          <div style="margin-top:10px">
            <div style="font-size:11px;color:#6b7280;margin-bottom:4px">最近流转</div>
            ${logs.slice(0,4).map(l => `<div style="font-size:11px;color:#374151;border-left:2px solid #e5e7eb;padding:4px 8px;margin-bottom:4px">${l.action} · ${l.created_at || ''}</div>`).join('') || '<div style="font-size:11px;color:#9ca3af">暂无日志</div>'}
          </div>
        </div>
      </div>`
  } catch (e) {
    container.innerHTML = `<div class="card" style="margin-top:12px"><div class="review-body" style="color:#6b7280;font-size:12px">审批流加载失败：${e.message}</div></div>`
  }
}
