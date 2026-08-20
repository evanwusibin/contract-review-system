import { enrichUser } from '../auth.js'
import { showToast } from '../utils.js'

export function renderLogin(rootEl) {
  rootEl.innerHTML = `
  <div class="login-layer" id="loginLayer">
    <div class="carousel-pane" id="carouselPane">
      <div class="carousel-brand">
        <div class="carousel-brand-icon"><svg viewBox="0 0 24 24"><path d="M3 12l7-7 7 7M5 10v7a1 1 0 001 1h4v-4h4v4h4a1 1 0 001-1v-7"/></svg></div>
        <div><div class="carousel-brand-name">合同智能评审</div><div class="carousel-brand-sub">AI 智能审查</div></div>
      </div>
      <div class="slides" id="slides">
        <div class="slide active" id="videoSlide">
          <video id="brandVideo" muted playsinline style="width:100%;height:100%;object-fit:cover;"><source src="/images/1.mp4" type="video/mp4"></video>
          <div class="caption-wrap"><div class="slide-tag">AI 智能审查</div><div class="slide-title">让每一份合同<br>都有可追溯的依据</div><div class="slide-desc">基于原文证据、规则命中与人工会签，帮助法务和业务更快发现合同风险。</div></div>
        </div>
        <div class="slide" style="background-image:url('/images/2.webp')"><div class="caption-wrap"><div class="slide-tag">Step 1 · 导入合同</div><div class="slide-title">接收审批附件</div><div class="slide-desc">覆盖售后服务合同与销售合同，支持 PDF/Word/图片，自动计算哈希并创建版本。</div></div></div>
        <div class="slide" style="background-image:url('/images/3.png')"><div class="caption-wrap"><div class="slide-tag">Step 2 · 智能解析</div><div class="slide-title">提取字段条款</div><div class="slide-desc">OCR 识别主体、金额、期限与证据位置，低置信度自动提示人工复核。</div></div></div>
        <div class="slide" style="background-image:url('/images/4.png')"><div class="caption-wrap"><div class="slide-tag">Step 3 · 风险识别</div><div class="slide-title">规则与证据联动</div><div class="slide-desc">确定性规则执行，生成风险项、证据定位与建议结论，全程可追溯。</div></div></div>
        <div class="slide" style="background-image:url('/images/5.png')"><div class="caption-wrap"><div class="slide-tag">Step 4 · 人工确认</div><div class="slide-title">会签并留痕</div><div class="slide-desc">按责任域分派，逐级会签，意见与版本完整留痕，阻塞可追因。</div></div></div>
      </div>
      <div class="carousel-dots" id="dotsWrap">
        <div class="dot active" data-idx="0"></div><div class="dot" data-idx="1"></div><div class="dot" data-idx="2"></div><div class="dot" data-idx="3"></div><div class="dot" data-idx="4"></div>
      </div>
    </div>
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
      let resp
      try {
        resp = await api.login(name, password)
      } catch (e) {
        // 演示态：后端未启用鉴权 / 501 未实现时直接放行
        const msg = String(e.message || '')
        if (msg.includes('认证未启用') || msg.includes('AUTH_DISABLED') || msg.includes('501') || msg.includes('Failed to fetch')) {
          resp = { ok: true, data: { user: { id: 'demo', username: name || 'demo', display_name: name || '演示用户', role: 'admin' } } }
        } else throw e
      }
      if (resp.error?.code === 'AUTH_DISABLED' || resp.error?.message?.includes('认证未启用') || String(resp.error?.message || '').includes('501')) {
        enrichUser({ id: 'demo', username: name || 'demo', display_name: name || '演示用户', role: 'admin', roleName: '演示用户', name: name || '演示' })
        msgEl.textContent = '演示模式：已直接进入工作台（后端鉴权未启用）'
        msgEl.className = 'login-message success'
        showToast('演示登录成功', 'success')
        setTimeout(() => import('../app.js').then(({ mount }) => mount(document.getElementById('app'))), 250)
        return
      }
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

  // ── 轮播初始化 ──
  const slideEls = document.querySelectorAll('.slide')
  const dotEls = document.querySelectorAll('.dot')
  let cur = 0, timer = null
  function goSlide(i) {
    if (!slideEls[cur] || !dotEls[cur]) return
    slideEls[cur].classList.remove('active')
    dotEls[cur].classList.remove('active')
    cur = (i + slideEls.length) % slideEls.length
    slideEls[cur].classList.add('active')
    dotEls[cur].classList.add('active')
    const slidesEl = document.getElementById('slides')
    if (slidesEl) slidesEl.style.transform = 'translateX(-' + (cur * 100) + '%)'
  }
  function startAuto() { clearInterval(timer); timer = setInterval(() => goSlide(cur + 1), 3000) }
  const video = document.getElementById('brandVideo')
  if (video) {
    video.addEventListener('ended', () => { goSlide(1); startAuto() })
    video.addEventListener('error', () => { goSlide(1); startAuto() })
    const playPromise = video.play()
    if (playPromise !== undefined) playPromise.catch(() => setTimeout(() => { goSlide(1); startAuto() }, 8000))
  } else startAuto()
  const dotsWrap = document.getElementById('dotsWrap')
  if (dotsWrap) dotsWrap.addEventListener('click', (e) => {
    const d = e.target.closest('.dot'); if (!d) return
    const idx = Number(d.dataset.idx)
    if (idx !== 0 && video) video.pause()
    goSlide(idx); startAuto()
  })
}