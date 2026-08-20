# 前端高分开源参考调研（企业级合同/审批/工作台）

> 目标：为合同评审工作台找可参考的企业级浅色 UI 与专业技术栈，解决“项目显小、业务单薄”。

## 1. 通用企业后台模板（UI 与布局参考，星数高、维护活跃）

| 项目 | Stars | 技术栈 | 亮点 | 适用借鉴 |
|------|-------|--------|------|----------|
| **ColorlibHQ/AdminLTE** | 45.5k | Bootstrap 5 + Astro | 最经典的企业后台，浅色卡片、侧边导航、统计胶囊 | 整体布局、卡片阴影、色板 |
| **akveo/ngx-admin** | 25.6k | Angular + Nebular | 企业级权限 + 主题切换 + 数据可视化 | 角色区分、仪表盘 |
| **Kiranism/next-shadcn-dashboard-starter** | 6.8k | **Next.js 16 + shadcn/ui + Tailwind + TypeScript** | 现代浅色企业仪表盘，表格/表单/鉴权/计费开箱即用，AI 友好 | **最推荐：直接作为工作台升级蓝本** |
| **epicmaxco/vuestic-admin** | 10.9k | Vue 3 + Vite + Pinia + Tailwind | Vue 生态最完整的 admin，图表/表格/权限齐全 | 若走 Vue 路线首选 |
| **Daymychen/art-design-pro** | 5.7k | Vue 3 + Vite + TS + Element Plus | 强调视觉设计与用户体验的国产 admin | 中文企业审美、Element Plus 组件 |
| **devias-io/material-kit-react** | 5.5k | React + MUI + TypeScript | Material 风格企业后台，含 Firebase/Auth0 | MUI 卡片与表单细节 |

> 搜索命令：`github_search_repositories: AdminLTE / next-shadcn-dashboard-starter / vuestic-admin`

## 2. 合同/审批/文档风项目（业务贴近，但星数分散）

- GitHub 直接搜 `contract management` / `document review` 多为低星或私有业务系统，无单一高分标杆。
- 建议参考 **审批流引擎**：`activiti` / `flowable` / `naive-ui + bpmn` 的流程图与节点状态色（pending 蓝、reviewing 琥珀、blocked 红、done 绿），已在当前 `tasks.js` 采用。
- 证据定位可参考 **RAG/文档问答**项目的“原文高亮 + 侧边证据卡”交互（类似 Ragflow 的文档切块高亮）。

## 3. 对本项目的启示

**为什么显小：**
- 当前 Vite + 原生 JS 无类型、无组件化、无状态层，难以承载“双栏证据联动、会签、版本、风险矩阵”等复杂交互，视觉上只有 6 个平铺页面。
- 后端虽已 DDD 分层，但前端未体现“审批流图 + 证据图谱 + 风险矩阵”的业务纵深。

**升级方向（保持浅色企业级）：**
1. **UI 体系**：抄 `next-shadcn-dashboard-starter` 的浅色卡片、柔和阴影、12px 辅助文字、胶囊状态色，与现有 `workbench` 双栏布局天然契合。
2. **技术栈**：见下方方案 A/B。
3. **业务加厚**：新增“审批流时间轴 + 证据图谱 + 风险矩阵 + 规则策略中心”四件套，让工作台从“表单”变“驾驶舱”。
