# 合同评审系统

AI 驱动的合同风险识别与审批工作台。基于原文证据、规则命中与人工会签，帮助法务和业务更快发现合同风险。

## 功能

- **合同导入**：支持 PDF 上传，自动解析提取字段
- **风险识别**：基于规则引擎自动标记高/中/低风险
- **双栏工作台**：左侧原文证据，右侧审核工作区
- **人工会签**：业务、法务、质保三方确认
- **版本管理**：历史版本留痕，支持恢复
- **审计追踪**：完整操作日志

## 快速开始

### 本地开发

```bash
# 后端
cd contract-review
pip install -e ".[test]"
docker compose -f docker-compose.demo.yml up -d
python -m uvicorn contract_review.api:app --port 8001

# 前端
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
cd contract-review
cp .env.production.example .env.production
# 编辑 .env.production 填写密码
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 技术栈

- **后端**：FastAPI + SQLAlchemy + PostgreSQL + RapidOCR
- **前端**：Vite 6 + 原生 JavaScript
- **存储**：PostgreSQL（元数据）+ MinIO（附件）
- **部署**：Docker Compose

## 项目结构

```
├── contract-review/        # 后端
│   ├── src/contract_review/  # 源码
│   ├── alembic/              # 数据库迁移
│   ├── tests/                # 测试
│   └── docker-compose.prod.yml
├── frontend/               # 前端
│   └── src/
├── .github/workflows/      # CI/CD
└── README.md
```

## 许可证

MIT
