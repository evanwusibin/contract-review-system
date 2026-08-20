# Agent 协作约束

## 读取顺序

1. `docs/DESIGN_DELIVERY_BLUEPRINT.md`
2. `CONTEXT.md`（项目根目录）
3. 当前 Slice Spec（`specs/切片Spec_函数级/`）
4. `02_合同评审开发任务/` 中的 PRD、技术方案和切片规划
5. 对应测试（`tests/`）

## 强制不变量

- 原始附件、解析结果、规则命中、人工结论和审计日志分开保存，任何派生结果不得覆盖原始文件。
- 任务状态与审批建议状态分离：`blocked` 不等于 `rejected`，`rejected_recommendation` 不等于最终审批驳回。
- 证据不足（`insufficient_evidence`）不得生成 `confirmed` 建议。
- `HP-001`（付款比例/账期阈值）在来源确认前只能是候选规则，不得发布为正式自动驳回规则。
- 所有模拟回写必须标记 `SIMULATED_ONLY`，不得伪装为真实审批或真实评论回写。
- 日志不写入合同全文、密钥、密码或完整个人信息。
- 每个切片必须先有可执行测试与 Spec，再写业务实现。

## 当前边界

- Slice 1-7 已完成工程实现和 pytest 验证（37 项通过）。
- OCR 适配器已优化：新增 `custom_logit_processor`、`images_config`、HTTP 错误分类、`health_check()` 方法。测试数据就绪（`tests/data/` 含真实合同 PDF）。联调验证脚本：`verify_ocr.py`。
- MinIO 健康检查通过，但对象读写尚未完成端到端验证。
- 前端工程已创建在 `frontend/`（Vite 6，18 模块，构建通过），覆盖 6 页面 + 登录页，对接后端 6 个端点。
- 规则中心、审计记录页面标记为"待实现"，等待后端提供对应 API。
- 设计基准仍为 `02_合同评审开发任务/合同评审工作台_阶段1原型.html`，历史前端尝试已归档至 `archive/frontend-deprecated/`。
- 禁止连接真实审批系统、执行真实审批、发送真实评论或自动修改原合同。
- 后续新增能力必须通过适配器模式接入，不得在 API 层直接拼接外部服务调用。