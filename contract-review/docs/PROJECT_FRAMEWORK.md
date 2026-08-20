# 项目框架

> 状态：Slice 1-7 已实现。本文定义模块职责、依赖方向和后续切片准入。

## 1. 目标与边界

系统将合同审查组织为一条可追溯的数据流：

```
PDF/合同文件
  → approval_task 生命周期
    → approval_attachment 版本管理
      → contract_parse 解析与证据
        → rule_hits 规则命中
          → review_result 审批建议
            → comment_logs 会签审计
```

以下能力仍在对应切片完成后才可进入：

- PostgreSQL 持久化与数据库迁移
- 真实审批系统适配器
- Unlimited-OCR 生产接入
- 正式认证与权限服务
- 真实评论回写

## 2. 目录与职责

```
src/contract_review/
├── api.py        # HTTP 边界：路由、协议校验、系统响应
├── workflow.py   # 编排：任务状态机、评审流程、幂等控制
├── parser.py     # 解析：OCR 适配、字段抽取、证据定位
├── rules.py      # 规则：确定性规则引擎、风险等级
├── quality.py    # 质量：文件质量诊断、分页检查
├── results.py    # 结果：审批建议、会签计算、保存
├── versions.py   # 版本：快照管理、时间线
├── storage.py    # 存储：MinIO 适配、上传/下载/哈希
├── ocr.py        # OCR：Provider 适配器（Mock + 待接入）
├── domain.py     # 领域模型
└── config.py     # 运行配置
```

## 3. 依赖方向

```
api → workflow → parser → ocr (external)
                → rules
                → results → storage (MinIO)
                → versions
```

约束：

1. `domain.py` 不导入 FastAPI、数据库驱动或外部服务 SDK。
2. `api.py` 不直接访问数据库或调用外部服务，只装配 HTTP 入口。
3. `workflow.py` 编排业务流程，不执行具体解析或规则逻辑。
4. 外部能力（OCR、MinIO）通过适配器模式接入，支持 Mock 替换。
5. 日志脱敏，不保存合同全文、密码或完整个人信息。

## 4. 后续切片准入条件

进入 Slice 8+ 前必须同时满足：

- Slice 7 MinIO 对象读写完成端到端验证；
- OCR 集成通过脱敏 PDF 多页请求、响应解析和失败重试；
- 前端浏览器验收完成：导入→解析→规则命中→会签→保存→展示 SIMULATED_ONLY；
- HP-001 付款阈值来源确认或明确标记为候选；
- 通过评审后先写契约测试，再接入新能力。