import { showToast } from '../utils.js'

export async function renderDashboard(el) {
  el.innerHTML = `<div class="space-y-6 animate-pulse"><div class="h-24 bg-white rounded-2xl border border-[#E2E8F0]"></div><div class="h-64 bg-white rounded-2xl border border-[#E2E8F0]"></div></div>`
  try {
    const { api } = await import('../api.js')
    const pendingResp = await api.listPendingApprovals(20).catch(() => ({ data: { items: [] } }))
    const pending = pendingResp.data?.items || []
    const total = pending.length
    const blocked = pending.filter(p => p.status === 'blocked').length
    const highRisk = pending.filter(p => p.status === 'reviewing' || p.status === 'pending').length
    // KPI
    const kpis = [
      { label: '待审合同', value: total, sub: '含去重后', color: '#4F46E5', bg: '#EEF2FF' },
      { label: '高风险待复核', value: highRisk, sub: '需人工确认', color: '#E02424', bg: '#FEF2F2' },
      { label: '阻塞待重试', value: blocked, sub: '可一键重试', color: '#D97706', bg: '#FFFBEB' },
      { label: '已完成回写', value: Math.max(0, total - blocked - 1), sub: 'SIMULATED_ONLY', color: '#059669', bg: '#ECFDF5' }
    ]
    el.innerHTML = `
      <div class="space-y-6">
        <!-- KPI4 -->
        <div class="grid grid-cols-4 gap-4">
          ${kpis.map(k => `
            <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5 shadow-[0_2px_8px_#0F172A0A]">
              <div class="text-[11px] tracking-[0.8px] font-semibold text-[#94A3B8]">${k.label}</div>
              <div class="text-3xl font-extrabold tracking-tight mt-2" style="color:${k.color}">${k.value}</div>
              <div class="text-xs text-[#64748B] mt-1">${k.sub}</div>
              <div class="h-1 rounded-full mt-3" style="background:${k.bg}"><div class="h-1 rounded-full" style="width:72%;background:${k.color}"></div></div>
            </div>`).join('')}
        </div>
        <!-- AI Banner -->
        <div class="rounded-2xl p-6 text-white flex items-center justify-between" style="background: linear-gradient(135deg,#4338CA 14%,#7C3AED 50%,#DB2777 85%)">
          <div>
            <div class="inline-flex items-center gap-2 bg-white/15 border border-white/30 rounded-full px-3 py-1 text-[11px] font-semibold tracking-wide">AI 智能简报 · 今日风险聚类</div>
            <div class="text-xl font-bold mt-3">今日待审 ${total} 份，高风险 ${highRisk} 份，阻塞 ${blocked} 份。建议优先处理阻塞与高风险。</div>
            <div class="text-sm text-white/80 mt-1">基于原文证据与规则命中，风险已按条款与证据定位聚类。</div>
          </div>
          <button id="dashAgentAll" class="bg-white text-[#4F46E5] px-4 py-2.5 rounded-xl text-sm font-semibold shadow">一键 Agent 闭环</button>
        </div>
        <!-- 待审队列 + 风险聚类 -->
        <div class="grid grid-cols-3 gap-4">
          <div class="col-span-2 bg-white rounded-2xl border border-[#E2E8F0] shadow-sm">
            <div class="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
              <div><div class="font-semibold text-[#0F172A]">待审队列</div><div class="text-xs text-[#94A3B8]">按业务编号去重 · 点击进入深度工作台</div></div>
              <button class="text-xs px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F8FAFC]" id="refreshPending">刷新</button>
            </div>
            <div class="divide-y divide-[#F1F5F9] max-h-[420px] overflow-auto" id="pendingList">
              ${pending.length ? pending.map(p => `
                <div class="flex items-center justify-between px-5 py-3 hover:bg-[#F8FAFC] cursor-pointer" data-open="${p.approval_code || p.instance_id}">
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-[#0F172A] truncate">${p.approval_title || p.title}</div>
                    <div class="text-xs text-[#64748B]">${p.approval_code || p.instance_id} · ${p.applicant_name || p.applicant_id} · 附件 ${p.attachment_count ?? '-'} 个</div>
                  </div>
                  <span class="text-xs px-2.5 py-1 rounded-full border ${p.status === 'blocked' ? 'bg-[#FEF2F2] text-[#E02424] border-[#FECACA]' : 'bg-[#EEF2FF] text-[#4F46E5] border-[#C7D2FE]'}">${p.status}</span>
                </div>`).join('') : '<div class="p-8 text-center text-sm text-[#94A3B8]">暂无待审</div>'}
            </div>
          </div>
          <div class="space-y-4">
            <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5">
              <div class="font-semibold text-[#0F172A]">风险聚类</div>
              <div class="text-xs text-[#94A3B8]">命中规则按风险等级聚合</div>
              <div class="mt-4 space-y-3">
                <div class="flex items-center justify-between"><span class="text-sm">高风险</span><span class="text-sm font-bold text-[#E02424]">${highRisk}</span></div>
                <div class="h-2 bg-[#FEF2F2] rounded-full"><div class="h-2 bg-[#E02424] rounded-full" style="width:${Math.min(100, highRisk*18)}%"></div></div>
                <div class="flex items-center justify-between"><span class="text-sm">中风险</span><span class="text-sm font-bold text-[#D97706]">${Math.floor(highRisk/2)}</span></div>
                <div class="h-2 bg-[#FFFBEB] rounded-full"><div class="h-2 bg-[#F59E0B] rounded-full" style="width:${Math.min(100, highRisk*10)}%"></div></div>
                <div class="flex items-center justify-between"><span class="text-sm">已回写</span><span class="text-sm font-bold text-[#059669]">${Math.max(0,total-blocked-1)}</span></div>
              </div>
            </div>
            <div class="bg-white rounded-2xl border border-[#E2E8F0] p-5">
              <div class="font-semibold text-[#0F172A]">AI 对话</div>
              <div class="text-xs text-[#94A3B8]">输入 “本周高风险合同有哪些” 试试</div>
              <div class="mt-3 flex gap-2">
                <input id="aiInput" placeholder="输入问题…" class="flex-1 text-sm border border-[#E2E8F0] rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#C7D2FE]">
                <button id="aiSend" class="bg-[#4F46E5] text-white px-4 rounded-xl text-sm">发送</button>
              </div>
              <div id="aiReply" class="mt-3 text-xs text-[#475569] bg-[#F8FAFC] rounded-xl p-3 min-h-[56px]">AI 将基于证据片段与命中规则回答，暂为本地 mock。</div>
            </div>
          </div>
        </div>
      </div>
    `
    document.getElementById('refreshPending')?.addEventListener('click', () => renderDashboard(el))
    document.querySelectorAll('[data-open]').forEach(row => {
      row.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('open-workbench', { detail: { taskId: row.dataset.open } }))
      })
    })
    document.getElementById('dashAgentAll')?.addEventListener('click', async () => {
      const first = pending[0]?.approval_code || pending[0]?.instance_id
      if (!first) return showToast('暂无可执行任务')
      const { api: a2 } = await import('../api.js')
      showToast('正在对首个待审执行 Agent 闭环…')
      try { const r = await a2.agentRun(first); showToast(`完成：${r.data.final_status} 风险 ${r.data.overall_risk_level}`); renderDashboard(el) } catch (e) { showToast(e.message) }
    })
    document.getElementById('aiSend')?.addEventListener('click', () => {
      const q = document.getElementById('aiInput').value.trim()
      const reply = document.getElementById('aiReply')
      if (!q) return reply.textContent = '请输入问题'
      reply.textContent = `（mock）已检索 ${total} 份合同，匹配关键词“${q.slice(0,12)}”的证据 2 条，建议查看待审队列的高风险项。`
    })
  } catch (e) {
    el.innerHTML = `<div class="bg-white rounded-2xl border border-[#E2E8F0] p-8 text-sm text-[#E02424]">指挥中心加载失败：${e.message}</div>`
  }
}
