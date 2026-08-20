# 切片7 · 调用端演示闭环与 mock 回写

> **状态**：accepted（pytest 已验证）。
>
> 注：本切片定义以 `04_垂直切片规划.md` 为准，覆盖端到端调用闭环和模拟回写。
> MinIO 存储属于 Slice 7 的依赖能力，单独在 specs/切片Spec_函数级/切片7_MinIO存储与完整性.md 中描述。

## 目标

完成"导入 → 解析 → 规则命中 → 建议生成 → 模拟回写 → 版本保存"的完整端到端闭环，验证全流程可串联执行。

## 函数级Spec

### `workflow.review_pipeline(file, external_task_key, title)`

| 项 | 契约 |
|---|---|
| 输入 | 文件流、外部任务键、标题 |
| 输出 | `task_id`、`version_id`、`writeback_result`、`review_result`、`parse_result` |
| 流程 | 导入 → 质量诊断 → OCR → 字段抽取 → 规则执行 → 建议生成 → 模拟回写 |
| 约束 | 回写结果必须标记 `SIMULATED_ONLY` |

## 端到端链路

```
POST /v1/reviews/run
  → workflow.review_pipeline()
    → domain.import_contract()
    → quality.diagnose()
    → ocr.parse()
    → parser.extract_fields()
    → rules.execute()
    → results.generate_recommendation()
    → results.simulate_writeback()
    → versions.save_snapshot()
  → 返回 task_id + version_id + review + writeback
```

## 验收测试

- 端到端请求返回完整链路结果
- 模拟回写标记 `SIMULATED_ONLY`
- 版本保存成功
- 幂等：相同请求不重复创建