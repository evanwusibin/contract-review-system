import { getUser, clearUser, checkSession } from './auth.js'
import { renderWelcome } from './pages/welcome.js'
import { renderTasks } from './pages/tasks.js'
import { renderDocuments } from './pages/documents.js'
import { renderVersions } from './pages/versions.js'
import { renderRules } from './pages/rules.js'
import { renderAudit } from './pages/audit.js'
import { renderWorkbench } from './pages/workbench.js'
import { renderLogin } from './pages/login.js'
import { showToast } from './utils.js'

const PAGES = {
  welcome: renderWelcome,
  tasks: renderTasks,
  documents: renderDocuments,
  versions: renderVersions,
  rules: renderRules,
  audit: renderAudit,
  workbench: (el) => renderWorkbench(el, currentTaskId)
}

const CRUMB = {
  welcome: '首页',
  tasks: '待审任务',
  documents: '合同评审文档',
  versions: '合同版本',
  rules: '规则中心',
  audit: '审计记录',
  workbench: '评审工作台'
}

let currentTaskId = null

export function mount(rootEl) {
  const user = getUser()
  if (!user) {
    renderLogin(rootEl)
    return
  }
  // 有本地会话缓存：向后端确认 cookie 会话仍有效
  checkSession()
    .then((sessionUser) => {
      if (!sessionUser) {
        clearUser()
        renderLogin(rootEl)
        return
      }
      renderApp(rootEl, 'welcome')
    })
    .catch(() => {
      clearUser()
      renderLogin(rootEl)
    })
}

function renderApp(rootEl, page) {
  rootEl.innerHTML = ''

  const sidebar = createSidebar(page)
  rootEl.appendChild(sidebar)

  const main = document.createElement('main')
  main.className = 'main'

  const topbar = document.createElement('header')
  topbar.className = 'topbar'
  topbar.innerHTML = `<div class="crumb">合同评审工作台　/　<b>${CRUMB[page] || '首页'}</b></div>`
  main.appendChild(topbar)

  const content = document.createElement('section')
  content.className = 'content'
  content.id = 'page-content'
  main.appendChild(content)
  rootEl.appendChild(main)

  // 先挂载 DOM，页面渲染器内部使用 document.getElementById 才能找到节点
  const renderer = PAGES[page] || renderWelcome
  renderer(content)

  bindNavigation(page)
}

const NAV_ITEMS = [
  { page: 'welcome', icon: 'icon-home', label: '工作台首页' },
  { page: 'tasks', icon: 'icon-inbox', label: '待审任务' },
  { page: 'documents', icon: 'icon-file', label: '合同评审文档' },
  { page: 'versions', icon: 'icon-history', label: '合同版本' },
  { page: 'rules', icon: 'icon-rules', label: '规则中心' },
  { page: 'audit', icon: 'icon-shield', label: '审计记录' }
]

function createSidebar(activePage) {
  const aside = document.createElement('aside')
  aside.className = 'sidebar'

  const user = getUser()
  const roleName = user?.roleName || '法务审核人'
  const roleDesc = user?.roleDesc || '法务审核角色'
  const avatarLetter = (user?.name || '法')[0]

  aside.innerHTML = `
    <div class="brand">
      <div>
        <strong>合同审查工作台</strong>
        <span class="brand-ai">
          <svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg>
          AI 智能审查
        </span>
      </div>
    </div>
    <nav class="nav">
      ${NAV_ITEMS.map(item => `
        <button data-page="${item.page}" ${activePage === item.page ? 'class="active"' : ''}>
          <span class="nav-icon"><svg class="svg-icon" aria-hidden="true"><use href="#${item.icon}"></use></svg></span><span>${item.label}</span>
        </button>`).join('')}
    </nav>
    <div class="side-bottom">
      <b>评审边界</b>
      系统提供带证据的风险建议，不替代责任人的最终审批。
    </div>
    <div class="account">
      <div class="account-user">
        <div class="avatar">${avatarLetter}</div>
        <div><b>${roleName}</b><small>${roleDesc}</small></div>
        <button class="logout" id="logoutBtn">
          <svg class="svg-icon" aria-hidden="true"><use href="#icon-logout"></use></svg>
          退出登录
        </button>
      </div>
    </div>
  `
  return aside
}

function bindNavigation() {
  document.querySelectorAll('.nav button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const rootEl = document.getElementById('app')
      renderApp(rootEl, btn.dataset.page)
    })
  })

  // 从任务/文档列表进入评审工作台
  window.addEventListener('open-workbench', (e) => {
    currentTaskId = e.detail?.taskId
    if (currentTaskId) {
      renderApp(document.getElementById('app'), 'workbench')
    }
  })

  const logoutBtn = document.getElementById('logoutBtn')
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        const { api } = await import('./api.js')
        await api.logout()
      } catch { /* 会话可能已失效，忽略 */ }
      clearUser()
      showToast('已退出登录')
      renderLogin(document.getElementById('app'))
    })
  }
}