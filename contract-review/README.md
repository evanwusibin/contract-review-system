# Contract Review

合同审批审查系统的独立工程。它把合同文档组织为"导入 → 质量诊断 → 解析 → 规则审查 → 审批建议 → 人工确认 → 版本保存"的可追溯流程。

# 当前交付边界

- Slice 1：PDF 导入与任务幂等（已实现）
- Slice 2：文件质量诊断与阻塞（已实现）
- Slice 3：解析字段与证据定位（已实现，RapidOCR 真实合同验证）
- Slice 4：单条规则命中与风险联动（已实现）
- Slice 5：建议结果、责任域与会签（已实现）
- Slice 6：版本保存与历史恢复（已实现）
- Slice 7：MinIO 存储与完整性校验（已验证上传、下载与 SHA-256 一致性）

## 目录职责

```
src/contract_review/
├── api.py        # FastAPI 路由与 HTTP 序列化
├── workflow.py   # 评审编排与状态机
├── parser.py     # 文档解析与 OCR 适配
├── rules.py      # 确定性规则引擎
├── quality.py    # 文件质量诊断
├── results.py    # 审查结果与会签
├── versions.py   # 版本快照管理
├── storage.py    # MinIO 对象存储适配
├── ocr.py        # OCR Provider 适配器
├── domain.py     # 领域模型
├── config.py     # 运行配置
tests/
├── test_slice2.py ~ test_slice7.py  # 切片测试
├── test_api.py / test_api_http.py / test_http_api.py  # API 测试
├── test_import_contract.py           # 导入流程测试
docs/
├── DESIGN_DELIVERY_BLUEPRINT.md      # 设计交付蓝图
├── PROJECT_FRAMEWORK.md              # 项目框架
├── DOCUMENT_AUTHORITY.md             # 文档权威性
└── api/
    └── CONTRACT_REVIEW_API_V1.md     # API 契约
specs/
├── G1_领域模型、状态机与验收契约.md   # 领域对象与状态机
├── G1_原型评审与界面状态契约.md      # 界面状态契约
└── 切片Spec_函数级/                  # 逐切片函数级 Spec
```

**前端说明**：前端工程位于项目根目录 `frontend/`（Vite 6 + 原生 JS），以 `02_合同评审开发任务/合同评审工作台_阶段1原型.html` 为一比一视觉基准实现。覆盖登录页、工作台首页、待审任务、合同评审文档、**双栏评审工作台**（左原文证据 / 右审核工作区）、合同版本、规则中心、审计记录。全部图标使用专业 SVG symbol，无 Emoji。历史前端尝试已归档至项目根目录 `archive/frontend-deprecated/`。

## 本地运行

```bash
# 安装依赖
pip install -e ".[test]"

# 运行测试
pytest

# 启动后端 + MinIO（当前演示栈）
docker compose -f docker-compose.demo.yml up -d --build

# 启动前端（项目根目录 frontend/）
cd ../frontend
npm install
npm run dev
```

## 环境依赖

- MinIO：默认 `http://127.0.0.1:9000`（可通过环境变量覆盖）
- OCR：当前默认 RapidOCR；可通过 `OCR_PROVIDER=mock|rapid|unlimited` 切换
- 附件：MinIO 已联调
- 业务元数据：**PostgreSQL 已就绪**（生产栈）；本地演示可用内存存储

## Docker 部署

```bash
# 生产栈（PostgreSQL + MinIO + 后端，需设置环境变量）
cp .env.production.example .env.production   # 编辑填写密码/密钥
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# 演示栈（MinIO + 后端，零配置）
docker compose -f docker-compose.demo.yml up -d --build
```

`docker-compose.demo.yml` 编排 MinIO + RapidOCR 后端，不依赖 GPU；`docker-compose.prod.yml` 为生产栈（PostgreSQL + 认证 + RBAC）。

## 生产级状态

- ✅ 后端 API 全部对接真实数据库（PostgreSQL 持久化）
- ✅ 正式认证（PBKDF2 密码哈希 + HttpOnly Session Cookie + RBAC）
- ✅ 规则持久化（发布/退役/版本管理）
- ✅ 审计持久化（task_logs + comment_logs 全部落库）
- ✅ 重启后任务、版本、审计数据可恢复
- ✅ Docker 生产栈运行中（`docker-compose.prod.yml`）

## 安全边界

- 系统只输出 `建议通过`、`建议驳回`、`建议人工复核`，不替代最终审批
- 不接真实审批系统、不执行真实审批、不发送真实评论
- 日志不写合同全文、密钥、密码和完整个人信息
