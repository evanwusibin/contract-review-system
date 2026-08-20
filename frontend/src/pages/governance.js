export async function renderGovernance(el) {
  el.innerHTML = `<div class="space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5">
        <div class="text-xs font-bold tracking-[0.9px] text-[#94A3B8]">规则策略</div>
        <div class="text-lg font-bold text-[#0F172A] mt-1">12 条已发布</div>
        <div class="text-xs text-[#64748B]">覆盖 预付款/账期/续约/违约/管辖 等</div>
        <div class="mt-3 flex gap-2"><span class="text-xs px-2 py-1 rounded-full bg-[#EEF2FF] text-[#4F46E5]">3 高风险</span><span class="text-xs px-2 py-1 rounded-full bg-[#FFFBEB] text-[#D97706]">5 中风险</span></div>
        <button class="mt-4 w-full text-sm border border-[#E2E8F0] rounded-xl py-2 hover:bg-[#F8FAFC]" id="goRules">进入规则中心</button>
      </div>
      <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5">
        <div class="text-xs font-bold tracking-[0.9px] text-[#94A3B8]">审计留痕</div>
        <div class="text-lg font-bold text-[#0F172A] mt-1">全链路可追溯</div>
        <div class="text-xs text-[#64748B]">解析结果与建议分离存储</div>
        <div class="mt-3 text-xs text-[#475569] bg-[#F8FAFC] rounded-xl p-3">最近：导入 → 解析 → 规则 → 回写，SIMULATED_ONLY</div>
        <button class="mt-4 w-full text-sm border border-[#E2E8F0] rounded-xl py-2 hover:bg-[#F8FAFC]" id="goAudit">查看审计</button>
      </div>
      <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5">
        <div class="text-xs font-bold tracking-[0.9px] text-[#94A3B8]">AI 知识库</div>
        <div class="text-lg font-bold text-[#0F172A] mt-1">3 个知识库</div>
        <div class="text-xs text-[#64748B]">合同条款 · 风险案例 · 制度文件</div>
        <div class="mt-3 flex gap-2">
          <input id="kbInput" placeholder="提问：保密条款缺失如何判定？" class="flex-1 text-xs border border-[#E2E8F0] rounded-xl px-3 py-2">
          <button id="kbAsk" class="bg-[#4F46E5] text-white px-3 rounded-xl text-xs">提问</button>
        </div>
        <div id="kbAns" class="mt-3 text-xs text-[#475569] bg-[#F8FAFC] rounded-xl p-3">输入问题后，AI 将基于治理中心的规则与审计回答（本地 mock）。</div>
      </div>
    </div>
    <div class="bg-white rounded-2xl border border-[#E2E8F0]">
      <div class="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
        <div class="font-semibold text-[#0F172A]">审计时间线</div>
        <span class="text-xs text-[#94A3B8]">最近 20 条</span>
      </div>
      <div class="p-5" id="auditTimeline"><div class="text-sm text-[#94A3B8]">加载中…</div></div>
    </div>
  </div>`
  document.getElementById('goRules')?.addEventListener('click', () => {
    document.querySelector('button[data-page="governance"]')?.click()
    import('./rules.js').then(m => m.renderRules(document.getElementById('page-content')))
  })
  document.getElementById('goAudit')?.addEventListener('click', async () => {
    const { api } = await import('../api.js')
    const { showToast } = await import('../utils.js')
    try { const r = await api.listAuditEvents(10); showToast(`审计 ${r.data.total} 条`)} catch (e){ showToast(e.message)}
  })
  document.getElementById('kbAsk')?.addEventListener('click', () => {
    const q = document.getElementById('kbInput').value.trim()
    const ans = document.getElementById('kbAns')
    if (!q) return ans.textContent = '请输入问题'
    ans.textContent = `（mock）根据知识库：问题“${q.slice(0,16)}”涉及 保密条款与数据条款，建议核对证据定位与命中规则的 suggested_action。`
  })
  // 加载审计
  try {
    const { api } = await import('../api.js')
    const resp = await api.listAuditEvents(20)
    const items = resp.data?.items || []
    const box = document.getElementById('auditTimeline')
    if (!items.length) box.innerHTML = '<div class="text-sm text-[#94A3B8]">暂无审计</div>'
    else box.innerHTML = `<div class="space-y-3">${items.slice(0,8).map(it => `
      <div class="flex gap-3">
        <div class="w-2 h-2 rounded-full bg-[#4F46E5] mt-1.5"></div>
        <div class="flex-1">
          <div class="text-sm font-medium text-[#0F172A]">${it.action} <span class="text-xs text-[#94A3B8]">${(it.created_at||'').slice(0,19).replace('T',' ')}</span></div>
          <div class="text-xs text-[#64748B]">${it.task_id || ''} · ${it.actor_id || 'system'}</div>
        </div>
      </div>`).join('')}</div>`
  } catch {}
}
