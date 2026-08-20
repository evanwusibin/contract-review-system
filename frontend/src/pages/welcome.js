export function renderWelcome(el) {
  el.innerHTML = `
  <div class="welcome">
    <span class="eyebrow">合同风险识别与人工评审工作台</span>
    <h1>让每一份合同，都有<br><span class="gradient-text">可追溯的评审依据</span></h1>
    <p class="welcome-intro">面向售后服务合同与销售合同，连接原文、结构化字段、规则风险和责任人会签。系统负责发现问题与整理证据，最终业务效力始终由责任人确认。</p>

    <div class="welcome-grid">
      <div class="welcome-card">
        <h2>一套工作台，覆盖四类核心能力</h2>
        <p>从低清扫描件开始，到可留痕的人工结论。</p>
        <div class="capabilities">
          <div class="cap"><div class="cap-icon"><svg class="svg-icon" aria-hidden="true"><use href="#icon-search"></use></svg></div><b>原文与证据</b><span>页码、段落与高亮定位</span></div>
          <div class="cap"><div class="cap-icon"><svg class="svg-icon" aria-hidden="true"><use href="#icon-file"></use></svg></div><b>字段结构化</b><span>主体、金额、期限可修正</span></div>
          <div class="cap"><div class="cap-icon"><svg class="svg-icon" aria-hidden="true"><use href="#icon-rules"></use></svg></div><b>规则风险</b><span>命中条款与依据透明</span></div>
          <div class="cap"><div class="cap-icon"><svg class="svg-icon" aria-hidden="true"><use href="#icon-users"></use></svg></div><b>人工协同</b><span>补录、补证与逐级会签</span></div>
          <div class="cap"><div class="cap-icon"><svg class="svg-icon" aria-hidden="true"><use href="#icon-history"></use></svg></div><b>版本管理</b><span>新合同与修订版可追溯</span></div>
          <div class="cap"><div class="cap-icon"><svg class="svg-icon" aria-hidden="true"><use href="#icon-shield"></use></svg></div><b>审计留痕</b><span>操作与结论完整记录</span></div>
        </div>
      </div>
      <div class="welcome-card">
        <h2>适用业务场景</h2>
        <p>从首期垂直场景逐步扩展至售前与售后。</p>
        <div class="scene-list">
          <div class="scene"><i><svg class="svg-icon" aria-hidden="true"><use href="#icon-file"></use></svg></i><div><b>售后服务合同</b><span>质保期限、责任范围、服务结算</span></div></div>
          <div class="scene"><i><svg class="svg-icon" aria-hidden="true"><use href="#icon-rules"></use></svg></i><div><b>销售合同</b><span>主体、金额、币种、订单与付款</span></div></div>
          <div class="scene"><i><svg class="svg-icon" aria-hidden="true"><use href="#icon-spark"></use></svg></i><div><b>后续扩展</b><span>技术协议、框架合同、索赔单、维修工单</span></div></div>
        </div>
      </div>
    </div>

    <div class="hero-flow">
      <div class="flow-title">
        <h2>完整合同评审流程</h2>
        <span>每一步都产生可复核的业务价值</span>
      </div>
      <div class="flow">
        <div class="step"><div class="step-num">1</div><b>导入合同</b><p>上传 PDF/Word/图片，系统计算哈希并创建版本</p></div>
        <div class="step"><div class="step-num">2</div><b>质量诊断</b><p>检测清晰度、空页、倾斜，不可用时进入阻塞</p></div>
        <div class="step"><div class="step-num">3</div><b>解析抽取</b><p>OCR 识别字段、条款、证据位置和置信度</p></div>
        <div class="step"><div class="step-num">4</div><b>规则审查</b><p>确定性规则执行，生成风险项和建议结论</p></div>
        <div class="step"><div class="step-num">5</div><b>人工确认</b><p>按责任域分派，逐级会签，意见留痕</p></div>
      </div>
      <div class="welcome-actions">
        <button class="btn primary" id="welcomeNewReview">新建合同评审</button>
        <button class="btn" id="welcomeViewTasks">查看待审任务</button>
      </div>
    </div>

    <div class="stats" id="welcomeStats" style="margin-top:18px">
      <div class="stat card"><div class="stat-label">任务总数</div><div class="stat-value blue">…</div></div>
      <div class="stat card"><div class="stat-label">评审中</div><div class="stat-value">…</div></div>
      <div class="stat card"><div class="stat-label">阻塞</div><div class="stat-value red">…</div></div>
      <div class="stat card"><div class="stat-label">已确认</div><div class="stat-value">…</div></div>
    </div>
  </div>`

  document.getElementById('welcomeNewReview').addEventListener('click', async () => {
    const { showReviewForm } = await import('./review-form.js')
    showReviewForm()
  })
  document.getElementById('welcomeViewTasks').addEventListener('click', () => {
    document.querySelector('.nav button[data-page="tasks"]')?.click()
  })

  loadStats()
}

async function loadStats() {
  const statsEl = document.getElementById('welcomeStats')
  if (!statsEl) return
  try {
    const { api } = await import('../api.js')
    const resp = await api.listTasks()
    const tasks = resp.data?.items || []
    const total = tasks.length
    const reviewing = tasks.filter(t => ['imported', 'parsing', 'reviewing', 'awaiting_confirmation', 'confirming'].includes(t.status)).length
    const blocked = tasks.filter(t => t.status === 'blocked').length
    const confirmed = tasks.filter(t => t.status === 'confirmed').length
    statsEl.innerHTML = `
      <div class="stat card"><div class="stat-label">任务总数</div><div class="stat-value blue">${total}</div></div>
      <div class="stat card"><div class="stat-label">评审中</div><div class="stat-value">${reviewing}</div></div>
      <div class="stat card"><div class="stat-label">阻塞</div><div class="stat-value red">${blocked}</div></div>
      <div class="stat card"><div class="stat-label">已确认</div><div class="stat-value">${confirmed}</div></div>`
  } catch {
    statsEl.innerHTML = '<div class="empty-state">后端服务未连接，统计数据暂不可用</div>'
  }
}