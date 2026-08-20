# 切片1 · PDF导入与任务幂等

## 目标

上传 PDF 后生成 `approval_task` 和 `approval_attachment`；同一外部键+文件哈希重复提交不创建重复记录。

## 函数级Spec

### `import_contract(file, external_task_key, title, contract_type, uploaded_by)`

| 项 | 契约 |
|---|---|
| 输入 | `file`（二进制流）、`external_task_key`（str）、`title`（str）、`contract_type`（str）、`uploaded_by`（str） |
| 输出 | `task_id`、`attachment_id`、`version_no`、`file_sha256` |
| 成功 | `201 Created`，任务状态 `imported` |
| 幂等 | 相同 `external_task_key + file_sha256` 返回已有记录 |
| 异常 | 文件类型不支持 → `FILE_UNSUPPORTED`；空文件 → `400` |

### `list_tasks()`

返回所有非删除任务摘要列表。

## 验收测试

- 有效 PDF 创建 `imported` 任务和 v0 版本
- 不支持类型进入 `blocked`
- 相同键+哈希重试返回已有对象
- 导入事件写入审计日志