# 完整闭环演示（2.4.12）

## 前置
```bash
docker compose -f docker-compose.demo.yml up -d
# 或生产：docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 方式A：前端演示（推荐）
1. 打开 http://localhost:5173
2. 待审任务页点击任意任务的 **Agent 闭环** 按钮
3. 观察轨迹：详情→附件→解析→规则→保存→回写
4. 进入评审工作台查看 write_status=success 与证据定位
5. 对 blocked 任务点击 **重试** 验证重入 parsing

## 方式B：API 演示
```bash
curl http://localhost:8001/v1/approvals/pending?limit=5
curl http://localhost:8001/v1/approvals/CTR-2026-0001
curl -X POST http://localhost:8001/v1/agent/run -F instance_id=CTR-2026-0001
curl http://localhost:8001/v1/tasks/<task_id>/review
curl -X POST http://localhost:8001/v1/tasks/<task_id>/retry
```

## 验收
- 去重点：重复拉取同一 approval_code 不新增任务
- 附件缺失/解析失败/内容为空 均进 blocked 且可重试
- 规则命中含 evidence_text/position/suggestion
- 输出含 overall_risk_level/summary/focus/comment_text + write_status
