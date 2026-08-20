import { enrichUser } from '../auth.js'
import { showToast } from '../utils.js'

export function renderLogin(rootEl) {
  rootEl.innerHTML = `
  <div class="login-layer" id="loginLayer">
    <section class="login-visual">
      <div class="visual-ai">
        <svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg>
        合同审查工作台 · AI
      </div>
      <h1>让每一份合同<br>都有可追溯的依据</h1>
      <p>基于原文证据、规则命中与人工会签，帮助法务和业务更快发现合同风险。</p>
      <div class="visual-note">覆盖售后服务合同、销售合同首期场景，支持低置信度提示、待确认字段、版本留痕与异常阻塞管理。</div>
      <div class="login-flow">
        <div class="login-flow-item"><div class="step-mark">1</div><strong>导入合同</strong><span>接收审批附件</span></div>
        <div class="login-flow-item"><div class="step-mark">2</div><strong>智能解析</strong><span>提取字段条款</span></div>
        <div class="login-flow-item"><div class="step-mark">3</div><strong>风险识别</strong><span>规则与证据联动</span></div>
        <div class="login-flow-item"><div class="step-mark">4</div><strong>人工确认</strong><span>会签并留痕</span></div>
      </div>
    </section>
    <form class="login-box" id="loginForm">
      <h2>登录合同审查工作台<span class="login-title-ai">AI 智能审查</span></h2>
      <p>使用已登记的企业账号进入审查环境</p>
      <div class="login-field">
        <label for="loginName">账号</label>
        <input id="loginName" placeholder="请输入账号" autocomplete="username" required>
      </div>
      <div class="login-field">
        <label for="loginPassword">密码</label>
        <input id="loginPassword" type="password" placeholder="请输入密码" autocomplete="current-password" required>
      </div>
      <button class="btn primary" type="submit">登录</button>
      <div class="login-links">
        <button type="button" id="registerBtn">注册账号</button>
        <button type="button" id="forgotBtn">忘记密码</button>
      </div>
      <div class="login-db-note">
        <svg class="svg-icon" style="width:12px;height:12px" aria-hidden="true"><use href="#icon-shield"></use></svg>
        账号和密码必须由数据库中的有效用户记录校验，禁止前端固定账号绕过认证
      </div>
      <div class="login-message" id="loginMessage"></div>
    </form>
  </div>`

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault()
    const name = document.getElementById('loginName').value.trim()
    const password = document.getElementById('loginPassword').value
    const msgEl = document.getElementById('loginMessage')
    const submitBtn = e.target.querySelector('button[type=submit]')

    if (!name || !password) {
      msgEl.textContent = '登录失败：请输入账号和密码'
      msgEl.className = 'login-message'
      return
    }

    submitBtn.disabled = true
    submitBtn.textContent = '登录中…'
    try {
      const { api } = await import('../api.js')
      const resp = await api.login(name, password)
      if (!resp.ok || !resp.data?.user) {
        throw new Error(resp.error?.message || '登录失败')
      }
      enrichUser(resp.data.user)
      msgEl.textContent = '登录成功，正在进入工作台…'
      msgEl.className = 'login-message success'
      showToast('登录成功', 'success')
      setTimeout(() => {
        import('../app.js').then(({ mount }) => mount(document.getElementById('app')))
      }, 350)
    } catch (err) {
      msgEl.textContent = `登录失败：${err.message}`
      msgEl.className = 'login-message'
      showToast(`登录失败：${err.message}`, 'error')
      submitBtn.disabled = false
      submitBtn.textContent = '登录'
    }
  })

  document.getElementById('registerBtn').addEventListener('click', () => {
    showToast('注册申请将由管理员在数据库中创建有效用户记录')
    const msgEl = document.getElementById('loginMessage')
    msgEl.textContent = '原型提示：请联系管理员完成账号登记'
    msgEl.className = 'login-message'
  })

  document.getElementById('forgotBtn').addEventListener('click', () => {
    showToast('密码找回需接入企业身份或管理员重置流程')
    const msgEl = document.getElementById('loginMessage')
    msgEl.textContent = '原型提示：请联系管理员重置数据库中的账号密码'
    msgEl.className = 'login-message'
  })
}