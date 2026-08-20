export async function renderEvidenceGraph(container, taskId) {
  const { getEvidenceGraph } = await import('../../services/api.js')
  try {
    const resp = await getEvidenceGraph(taskId)
    const data = resp.data || {}
    const nodes = data.nodes || []
    const edges = data.edges || []
    if (!nodes.length) {
      container.innerHTML = `<div class="card" style="margin-top:12px"><div class="card-head"><h2>证据图谱</h2><span class="subtle">字段 ↔ 证据 ↔ 规则</span></div><div class="review-body" style="color:#6b7280;font-size:12px">${data.empty_reason || '暂无图谱数据'}</div></div>`
      return
    }
    const fieldNodes = nodes.filter(n => n.type === 'field')
    const hitNodes = nodes.filter(n => n.type === 'hit')
    container.innerHTML = `
      <div class="card" style="margin-top:12px">
        <div class="card-head"><div><h2>证据图谱</h2><span class="subtle">${fieldNodes.length} 字段 · ${hitNodes.length} 命中 · ${edges.length} 关联</span></div><span class="pill blue">可定位</span></div>
        <div class="review-body">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div>
              <div style="font-size:11px;color:#6b7280;margin-bottom:6px">结构化字段</div>
              ${fieldNodes.map(n => `<div style="border:1px solid #eef2f7;border-radius:8px;padding:8px;margin-bottom:6px;display:flex;justify-content:space-between"><span><b>${n.label}</b> <small style="color:#6b7280">${n.status}</small></span><span style="font-size:11px;color:#374151">${n.value || '—'}</span></div>`).join('')}
            </div>
            <div>
              <div style="font-size:11px;color:#6b7280;margin-bottom:6px">规则命中</div>
              ${hitNodes.map(n => `<div style="border:1px solid #fee2e2;border-radius:8px;padding:8px;margin-bottom:6px;background:#fff7f7"><b style="font-size:12px">${n.label}</b><div style="font-size:11px;color:#991b1b">${n.severity}</div></div>`).join('')}
            </div>
          </div>
          ${edges.length ? `<div style="margin-top:8px;font-size:11px;color:#6b7280">关联：${edges.map(e => `${e.from} → ${e.to}`).slice(0,4).join(' · ')}</div>` : ''}
        </div>
      </div>`
  } catch (e) {
    container.innerHTML = `<div class="card" style="margin-top:12px"><div class="review-body" style="color:#6b7280;font-size:12px">证据图谱加载失败：${e.message}</div></div>`
  }
}
