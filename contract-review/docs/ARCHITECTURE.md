# 架构说明 — DDD 分层

> 对齐 2.4.8 服务模块要求与通用技能库 TypeA+Agent 混合模型。

```
src/contract_review/
├── domain.py / domain/          # 领域层：ApprovalTask/WriteStatus/状态机/去重不变量
├── engine/                      # 引擎层：parser / quality / rules / results / versions / workflow
│   └── workflow.py              # 编排导入→质检→解析→规则→会签→版本→回写
├── application/                 # 应用层：tools.py(7工具) + agent.py(工具链Agent)
│   ├── tools.py                 # 2.4.10 7工具接口
│   └── agent.py                 # ReAct 轨迹 + blocked重试
├── infra/                       # 基础设施层：db.py / postgres_store.py / storage.py / mock_approvals.py / ocr.py
│   └── mock_approvals.py        # 无真实审批时的15条模拟数据
└── api.py                       # API 层：FastAPI 路由，薄适配，不含业务逻辑
```

**依赖方向**：api -> application -> engine/domain <- infra（通过端口）

**Agent 特性**：
- 工具即能力（Tool-Calling），轨迹可观测
- 状态机：pending->parsing->reviewing->done / blocked->retry->parsing
- 异常统一进 blocked，支持人工重试

**数据一致性**：
- approval_tasks.write_status 贯穿工具与 Agent
- 去重键 external_task_key (=approval_code)
- 日志 task_logs + comment_logs 全链路
