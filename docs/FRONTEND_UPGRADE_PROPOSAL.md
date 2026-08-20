# 前端专业化升级方案（保持浅色企业级 + SVG）

## 现状诊断
- Vite 6 + 原生 JS：无类型、无组件复用、无状态管理，难以支撑复杂工作台。
- 视觉虽已对齐原型，但组件粒度粗，缺“设计系统”约束，扩展性弱。

## 方案 A（推荐）：React + TypeScript 企业栈（对标 next-shadcn-dashboard-starter）
- **框架**：React 18 + TypeScript + Vite
- **UI**：Tailwind CSS + shadcn/ui（卡片、表格、对话框、表单）+ Lucide SVG 图标（替代现有 symbol，仍保持专业 SVG）
- **状态/数据**：Zustand（轻量本地） + TanStack Query（服务端状态：待办/详情/解析/规则）
- **表格**：TanStack Table（规则命中、审计日志）
- **图表**：Recharts（风险分布、流转漏斗）
- **优势**：与 `next-shadcn-dashboard-starter` 同源，招聘与社区最广，AI 代码生成友好，浅色主题成熟。
- **迁移成本**：中等。现有 6 页面可逐个迁移为 React 组件，`services/api.js` 直接复用。

## 方案 B：Vue 3 生态（若团队偏 Vue）
- **框架**：Vue 3 + TypeScript + Vite + Pinia
- **UI**：Element Plus 或 Vuestic UI + Tailwind
- **参考**：`vuestic-admin` / `art-design-pro`，中文后台审美更贴近国内企业。
- **优势**：与本校多数 Vue 课程衔接，组件开箱即用。
- **劣势**：shadcn 生态在 Vue 侧较弱。

## 建议落地节奏（不推倒重来）
1. **阶段 1（本周）**：保持现有 Vite 原生页，增加 `components/` 分层 + `services/api` + `stores/`，先把文件从散落改为 `pages/workbench/`、`components/cards/` 等（已完成目录创建），视觉上引入 Tailwind 变量与 shadcn 卡片样式。
2. **阶段 2（下周）**：选一个最复杂页（`workbench` 双栏）用 React+TS 重写为试点，验证 TanStack Query 与证据联动。
3. **阶段 3**：全量迁移，补充 单元/组件测试（Vitest + Testing Library），Storybook 做设计稿对齐。

## 业务加厚（让项目不再显小）
- **审批流图**：DAG 节点（pending→parsing→reviewing→done/blocked），可点击重试。
- **证据图谱**：解析字段 ↔ 原文片段 ↔ 规则命中的三元关联，左侧高亮联动。
- **风险矩阵**：高/中/低风险热力 + 规则策略版本对比。
- **规则策略中心**：从“列表”升级为“策略集 + 生效范围 + 灰度 + 审计”。
- **会签深化**：业务/法务/质保 三角色时序图 + 意见沉淀。

> 选择 A 还是 B，我可直接按选定栈重构 `frontend/` 并保留浅色 SVG 风格。
