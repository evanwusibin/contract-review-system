# 切片7 · MinIO 存储与完整性校验

> **状态**：blocked。MinIO 健康检查已通过，但对象读写端到端验证尚未完成（Docker daemon 不可用）。
>
> 注：MinIO 存储是 Slice 7 的依赖能力之一，非 Slice 7 的核心验收目标。

## 目标

原始文件存入 MinIO，支持上传、下载、哈希校验。

## 函数级Spec

### `upload_object(file, storage_key, sha256)`

| 项 | 契约 |
|---|---|
| 输入 | 文件流、存储键、文件哈希 |
| 输出 | `storage_key`、`content_length`、`sha256_verified` |
| 异常 | MinIO 不可达 → `UPSTREAM_TIMEOUT`；哈希不匹配 → `INTEGRITY_ERROR` |

### `download_object(storage_key)`

返回文件流和元数据。

### `verify_integrity(storage_key, expected_sha256)`

验证存储文件哈希与预期一致。

## 待完成验收

- bucket 创建
- 文件上传
- 文件下载
- sha256 完整性验证
- MinIO 不可达时的降级行为