# API v1 详细契约

> **状态**：draft。本文是合同评审系统版本化 API 契约。
>
> **重要**：本文件记录的是**当前代码实际实现的端点**，非目标态设计。端点路径、请求格式、响应结构均以 `src/contract_review/api.py` 为准。

## 1. 通用约定

| 项目 | 契约 |
|---|---|
| 基础路径 | `/v1` |
| 编码 | JSON / UTF-8 |
| 成功响应 | `{ "ok": true, "data": {} }` |
| 错误响应 | `{ "ok": false, "error": { "code": "...", "message": "..." } }` |

## 2. 当前已实现端点（以 api.py 为准）

### 2.1 健康检查

```
GET /v1/health
```

响应：`{ "ok": true, "data": { "status": "ok" } }`

### 2.2 任务列表

```
GET /v1/tasks
```

返回：`{ "data": { "items": [...], "total": N } }`

### 2.3 导入合同

```
POST /v1/imports
Content-Type: multipart/form-data
```

**注意**：路径是 `/v1/imports`，不是 `/v1/tasks/import`。

请求体：
- `file`：PDF/Word/图片文件
- `external_task_key`：外部任务键（幂等）
- `title`：标题

成功返回 `201 Created`，包含 `task_id`、`version_id`。

### 2.4 评审编排（全链路）

```
POST /v1/reviews/run
Content-Type: multipart/form-data
```

**注意**：路径是 `/v1/reviews/run`，不携带 `task_id` 路径参数。触发导入→解析→规则→建议全链路。

返回包含 `task_id`、`version_id`、`writeback`、`review`、`version`、`parse` 等字段。

### 2.5 任务详情（含附件）

```
GET /v1/tasks/{task_id}
```

返回任务详情和关联附件。

### 2.6 版本查询

```
GET /v1/tasks/{task_id}/versions
GET /v1/reviews/{task_id}/versions      # 并行路由
GET /v1/tasks/{task_id}/versions/{version_id}
GET /v1/reviews/{task_id}/versions/{version_id}   # 并行路由
```

## 3. 目标态端点（待实现）

以下为规范定义的目标端点，当前**尚未实现**：

| 端点 | 状态 | 说明 |
|---|---|---|
| `POST /v1/tasks/{task_id}/confirm` | MISSING | 模拟确认接口 |
| `POST /v1/tasks/{task_id}/reviews/run` | MISSING | 按任务ID触发评审（当前为全链路 `/v1/reviews/run`） |

## 4. 错误码

| 错误码（代码实际值） | 含义 |
|---|---|
| `UNSUPPORTED_FILE_TYPE` | 文件类型不支持 |
| `TASK_NOT_FOUND` | 任务不存在 |
| `PARSE_FAILED` | 解析失败 |

## 5. 幂等规则

- 导入：`external_task_key + file_sha256` 作用域唯一
- 评审：同一请求重复提交不重复执行