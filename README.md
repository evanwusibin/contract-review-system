# 合同评审系统 · Contract Review System

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](contract-review/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-green)](contract-review/src/contract_review/api)
[![Vite 6](https://img.shields.io/badge/Vite-6-646cff)](frontend/package.json)

AI 驱动的合同风险识别与审批工作台。基于原文证据、规则命中与人工会签，帮助法务和业务更快发现合同风险。

> **视觉基准**：`02_合同评审开发任务/合同评审工作台_阶段1原型.html`（渐变 `--grad`、`220px` 侧边栏、`64px` 品牌 + `AI 智能审查` 渐变徽标、欢迎页静态、登录轮播）

## 功能

- **欢迎页**：静态复刻原型（`eyebrow`、渐变标题、6 能力卡、3 场景、5 步流程、统计），登录后默认页
- **合同导入**：支持 PDF 上传，自动解析提取字段（RapidOCR + 质量诊断）
- **风险识别**：基于确定性规则引擎自动标记高/中/低风险（`RULE-PARTY-*` 等）
- **双栏工作台**：左侧原文证据（高亮定位）/ 右侧审核工作区（字段、风险、建议、会签），`h-screen` 视口 + 内部滚动
- **人工会签**：业务、法务、质保三方确认，会签状态分离（`blocked` ≠ `rejected`）
- **版本管理**：历史版本留痕，支持恢复
- **审计追踪**：完整操作日志（`task_logs` + `comment_logs` 落库）

## 快速开始

### 本地开发

```bash
# 后端（PostgreSQL + MinIO 需先起，见 Docker）
cd contract-review
uv sync --extra dev
uv run python scripts/init_demo_db.py  # 可选：初始化演示库
uv run pytest
uv run uvicorn contract_review.api.app:app --host 127.0.0.1 --port 8001 --reload

# 前端
cd frontend
npm install
npm run dev  # http://127.0.0.1:5173
npm run build
```

演示账号（`contract-review/.env.production`）：`admin / fa21bc041474b3ae94d7e043`、`business / business123`、`legal / legal123`、`warranty / warranty123`

### Docker 开发栈

```bash
cd contract-review
docker compose -f docker-compose.demo.yml up -d  # MinIO + 后端（零配置）
# 前端仍用 npm run dev
```

### Docker 生产栈

```bash
cd contract-review
cp .env.production.example .env.production
# 编辑 .env.production 填写 POSTGRES_PASSWORD / MINIO_SECRET_KEY / SESSION_SECRET / ADMIN_PASSWORD
# CORS_ORIGINS 需包含 http://127.0.0.1:5173,http://127.0.0.1:5174
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
# 前端 dist 可 serve 于 5173/5174 或 CDN
```

## 技术栈

- **后端**：FastAPI 0.141 + SQLAlchemy 2.0 + PostgreSQL 16 + Alembic + RapidOCR + MinIO
- **前端**：Vite 6 + 原生 JavaScript + Tailwind CDN + 原型 1:1 样式（`--grad` 渐变、`220px` 侧边栏、登录轮播 `1.mp4` + `2.webp-5.png`）
- **存储**：PostgreSQL（元数据）+ MinIO（附件，`contract-review` 桶）
- **部署**：Docker Compose（`demo.yml` / `prod.yml`）

## 项目结构

```
├── contract-review/          # 后端
│   ├── src/contract_review/
│   │   ├── api/app.py        # FastAPI 路由（CORS 含 5173/5174/5176）
│   │   ├── domain/           # 领域模型
│   │   ├── engine/           # 规则/解析/工作流
│   │   └── infrastructure/   # persistence / storage
│   ├── alembic/              # 0001_baseline / 0002_spec_alignment
│   ├── tests/                # 37+ 契约测试
│   ├── examples/             # 328B 占位 PDF
│   └── docker-compose.*.yml
├── frontend/                 # 前端
│   ├── src/
│   │   ├── app.js            # 220px 侧边栏、56px 顶栏、欢迎页默认
│   │   ├── styles.css        # --grad 渐变、轮播样式
│   │   ├── pages/login.js    # 轮播（1.mp4 + 4 图）+ 表单
│   │   ├── pages/welcome.js  # 原型静态复刻
│   │   └── api.js            # 5173/5174 CORS 兼容
│   ├── public/images/        # 1.mp4, 2.webp, 3-8.png
│   └── dist/                 # vite build 产物
├── docs/                     # DESIGN_DELIVERY_BLUEPRINT 等
├── .github/workflows/        # CI/CD
└── README.md
```

## API 契约（节选）

- `POST /v1/auth/login` `POST /v1/auth/logout` `GET /v1/auth/me`
- `GET /v1/tasks` `GET /v1/tasks/{id}/review` `POST /v1/reviews/run`（需三方会签 `confirmations`）
- `POST /v1/imports` `GET /v1/rules` `POST /v1/rules` `PATCH /v1/rules/{id}`
- `GET /v1/approvals/pending` `GET /v1/tasks/{id}/flow|risk-matrix|evidence-graph`

详见 `contract-review/docs/api/CONTRACT_REVIEW_API_V1.md`

## 复习指南

完整项目复习见 [复习指南.md](复习指南.md)（架构六层/状态机/18 API/Docker/前端关键点/面试高频问答）

## 许可证

MIT — 见 [LICENSE](LICENSE)
