# 设计交付蓝图与追踪矩阵

> **状态**：active。本文是设计交付入口，记录当前实际交付状态。
>
> **重要说明**：当前代码使用**内存存储**（非 PostgreSQL），`fetch` 和 `audit` 模块**尚未实现**。这些差距已在本文档中明确标注，待后续切片补全。

## 1. 交付链

```
A1 业务蓝图与范围
  → A2 PRD 与验收目标
    → A3 概要设计
      → A4 数据模型与黄金数据集
        → A5 垂直切片规划
          → Slice 1-7 实现
            → 运行验收证据
```

## 2. 权威文档与状态

| 编号 | 交付物 | 权威来源 | 当前状态 | 下一步准出条件 |
|---|---|---|---|---|
| A1 | 业务蓝图、范围、里程碑 | `02_合同评审开发任务/00_项目章程与范围.md` | active | — |
| A2 | PRD、功能需求、验收目标 | `02_合同评审开发任务/01_PRD_合同审批审查系统.md` | active | — |
| A4 | 数据模型、八张表、黄金集 | `02_合同评审开发任务/02_数据模型与黄金数据集.md` | active | 内存→PostgreSQL 迁移 |
| A3 | 架构、模块边界、接口契约 | `02_合同评审开发任务/03_技术方案与架构.md` | active | fetch/audit 模块实现 |
| A5 | 七个切片规划 | `02_合同评审开发任务/04_垂直切片规划.md` | in_progress | 前端浏览器验收 + OCR + MinIO |

## 3. 模块实现状态（vs 03 技术方案）

| 技术方案模块 | 代码对应文件 | 状态 |
|---|---|---|
| `fetch`（审批系统拉取） | **不存在** | MISSING |
| `attachment`（附件管理） | `domain.py` + `storage.py` + `quality.py` | 部分实现（拆分在 3 个文件） |
| `parse`（文档解析） | `parser.py` + `ocr.py` | 已实现（Mock OCR） |
| `rules`（规则引擎） | `rules.py` | 已实现 |
| `result`（结果/回写） | `results.py` + `versions.py` | 已实现 |
| `audit`（审计日志） | **不存在**（散落在 6 个文件中） | MISSING |

## 4. 追踪矩阵

| 需求/风险 | 领域对象与状态 | 数据/规则来源 | 切片 | 测试与验收证据 |
|---|---|---|---|---|
| PDF 导入与幂等 | `approval_task`、`approval_attachment` | 文件哈希 | S1 | `test_import_contract.py` |
| 质量诊断 | `quality_status`、`blocked` | 质量分 | S2 | `test_slice2.py` |
| 字段解析 | `contract_parse`、字段证据 | OCR/解析 | S3 | `test_slice3.py` |
| 规则命中 | `review_rules`、`rule_hits` | published 规则 | S4 | `test_slice4.py` |
| 会签 | `review_results`、`comment_logs` | 角色权限 | S5 | `test_slice5.py` |
| 版本保存 | `approval_attachments`、版本时间线 | 文件哈希 | S6 | `test_slice6.py` |
| 端到端闭环 | 全链路 | Mock 回写 | S7 | `test_slice7.py` |
| MinIO 存储 | `storage_key`、`file_sha256` | 对象存储 | S7-依赖 | blocked |
| HP-001 付款阈值 | `review_rules` (draft) | 待业务确认 | — | 不可发布为正式规则 |

## 5. 数据层现状

| 项目 | 目标（A4） | 当前实现 | 差距 |
|---|---|---|---|
| 存储引擎 | PostgreSQL + SQLAlchemy | 内存字典 (`InMemoryReviewStore`) | 需迁移 |
| 唯一约束 | DB 层强制 | 无 | 需迁移后补 |
| 逻辑删除 | `deleted_at` 字段 | 无实现 | 需补 |
| 审计持久化 | `task_logs` 表 | 内存列表 | 需迁移 |

## 6. 状态语义

| 状态 | 含义 | 允许推进到 |
|---|---|---|
| `draft` | 已有内容，但未完成核验 | `review` |
| `review` | 已具备准出材料，等待评审 | `approved` |
| `approved` | 允许编写测试与最小实现 | `implemented` |
| `implemented` | 已有实现，尚无运行验收 | `accepted` |
| `accepted` | 有可复现运行证据 | 后续版本维护 |
| `blocked` | 前置依赖未完成 | 回到 `draft` |

## 7. 当前禁止事项

- 不把 Mock OCR 结果表述为真实 OCR 能力。
- 不把 MinIO 健康检查通过表述为对象存储可用。
- 不把 `SIMULATED_ONLY` 回写表述为真实审批。
- 不把 HP-001 候选规则发布为正式驳回规则。
- 不把内存数据表述为持久化存储。