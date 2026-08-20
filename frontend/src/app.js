import { getUser, clearUser, checkSession } from './auth.js'
import { renderLogin } from './pages/login.js'
import { renderDashboard } from './pages/dashboard.js'
import { renderWorkbench } from './pages/workbench.js'
import { renderGovernance } from './pages/governance.js'
import { renderTasks } from './pages/tasks.js'
import { renderDocuments } from './pages/documents.js'
import { renderVersions } from './pages/versions.js'
import { renderRules } from './pages/rules.js'
import { renderAudit } from './pages/audit.js'
import { renderWelcome } from './pages/welcome.js'

const PAGES = {
  dashboard: renderDashboard,
  tasks: renderTasks,
  documents: renderDocuments,
  workbench: (el) => renderWorkbench(el, currentTaskId),
  versions: renderVersions,
  rules: renderRules,
  audit: renderAudit,
  governance: renderGovernance,
  welcome: renderWelcome
}

const CRUMB = {
  dashboard: '智能评审指挥中心',
  tasks: '待审任务',
  documents: '合同评审文档',
  workbench: 'AI 深度评审工作台',
  versions: '合同版本',
  rules: '规则中心',
  audit: '审计记录',
  governance: 'AI 知识与治理中心',
  welcome: '欢迎'
}

let currentTaskId = null

export function mount(rootEl) {
  const user = getUser()
  if (!user) {
    renderLogin(rootEl)
    return
  }
  checkSession()
    .then((sessionUser) => {
      if (!sessionUser) {
        clearUser()
        renderLogin(rootEl)
        return
      }
      renderApp(rootEl, 'dashboard')
    })
    .catch(() => {
      clearUser()
      renderLogin(rootEl)
    })
}

function renderApp(rootEl, page) {
  rootEl.innerHTML = ''
  const wrap = document.createElement('div')
  wrap.className = 'flex min-h-screen bg-[#F8FAFC]'
  const sidebar = createSidebar(page)
  wrap.appendChild(sidebar)
  const main = document.createElement('main')
  main.className = 'flex-1 flex flex-col min-w-0'
  const topbar = document.createElement('header')
  topbar.className = 'h-[56px] bg-white border-b border-[#E2E8F0] flex items-center px-6 justify-between shrink-0'
  topbar.innerHTML = `<div class="text-sm text-[#64748B]">合同智能评审 <span class="mx-2">/</span><b class="text-[#0F172A]">${CRUMB[page] || ''}</b></div><div class="text-xs text-[#94A3B8] hidden sm:block"></div>`
  main.appendChild(topbar)
  const content = document.createElement('section')
  content.className = 'flex-1 p-6 overflow-auto bg-[#F8FAFC] min-w-0'
  content.id = 'page-content'
  main.appendChild(content)
  wrap.appendChild(main)
  rootEl.appendChild(wrap)
  const renderer = PAGES[page] || renderDashboard
  renderer(content)
  bindNavigation(page)
}

const NAV_ITEMS = [
  { page: 'dashboard', icon: 'icon-dashboard', label: '指挥中心' },
  { page: 'tasks', icon: 'icon-inbox', label: '待审任务' },
  { page: 'documents', icon: 'icon-file', label: '合同文档' },
  { page: 'workbench', icon: 'icon-workbench', label: '深度工作台' },
  { page: 'versions', icon: 'icon-history', label: '合同版本' },
  { page: 'rules', icon: 'icon-rules', label: '规则中心' },
  { page: 'audit', icon: 'icon-shield', label: '审计记录' },
  { page: 'governance', icon: 'icon-governance', label: '知识与治理' }
]

function createSidebar(activePage) {
  const aside = document.createElement('aside')
  aside.className = 'w-[264px] shrink-0 bg-white border-r border-[#E2E8F0] flex flex-col'
  const user = getUser()
  const roleName = user?.roleName || '法务审核人'
  const avatarLetter = (user?.name || '法')[0]
  aside.innerHTML = `
    <div class="h-[72px] flex items-center px-[18px] border-b border-[#E2E8F0]">
      <div>
        <div class="text-[15px] font-extrabold tracking-[-0.5px] text-[#0F172A] leading-none">合同智能评审</div>
      </div>
    </div>
    <div class="flex-1 p-3 space-y-4">
      <div class="text-[9px] font-bold tracking-[0.9px] text-[#94A3B8] px-2">智能中枢</div>
      <nav class="space-y-1">
        ${NAV_ITEMS.map(item => `
          <button data-page="${item.page}" class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm ${activePage === item.page ? 'bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]' : 'text-[#475569] hover:bg-[#F8FAFC]'}">
            <svg class="w-4 h-4" aria-hidden="true"><use href="#${item.icon}"></use></svg>
            <span>${item.label}</span>
          </button>`).join('')}
      </nav>
      <div class="rounded-xl bg-gradient-to-br from-[#EEF2FF] to-[#FFF1F2] border border-[#E2E8F0] p-4">
        <div class="text-xs font-semibold text-[#0F172A]">评审边界</div>
        <div class="text-[11px] text-[#64748B] mt-1">系统提供带证据的风险建议，不替代责任人的最终审批。</div>
      </div>
    </div>
    <div class="border-t border-[#E2E8F0] p-3">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-full bg-[#4F46E5] text-white flex items-center justify-center font-bold">${avatarLetter}</div>
        <div class="flex-1 min-w-0"><div class="text-sm font-semibold text-[#0F172A] truncate">${roleName}</div><div class="text-xs text-[#94A3B8]">已认证</div></div>
        <button class="text-[#94A3B8] hover:text-[#0F172A]" id="logoutBtn"><svg class="w-4 h-4" aria-hidden="true"><use href="#icon-logout"></use></svg></button>
      </div>
    </div>
  `
  return aside
}

function bindNavigation() {
  document.querySelectorAll('button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const rootEl = document.getElementById('app')
      renderApp(rootEl, btn.dataset.page)
    })
  })
  window.addEventListener('open-workbench', (e) => {
    currentTaskId = e.detail?.taskId
    if (currentTaskId) {
      renderApp(document.getElementById('app'), 'workbench')
    }
  })
  const logoutBtn = document.getElementById('logoutBtn')
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try { const { api } = await import('./api.js'); await api.logout() } catch {}
      clearUser()
      const { showToast } = await import('./utils.js')
      showToast('已退出登录')
      const { renderLogin } = await import('./pages/login.js')
      renderLogin(document.getElementById('app'))
    })
  }
}
