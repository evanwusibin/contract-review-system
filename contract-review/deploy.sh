#!/bin/bash
# 一键部署脚本 - 在 ECS 上运行一次即可
# 用法: bash deploy.sh

set -e

IMAGE="18979909121/contract-review:latest"
COMPOSE_FILE="docker-compose.prod.yml"

echo "=== 拉取最新镜像 ==="
docker pull $IMAGE

echo "=== 停止旧容器 ==="
docker compose -f $COMPOSE_FILE down 2>/dev/null || true

echo "=== 启动新容器 ==="
docker compose -f $COMPOSE_FILE --env-file .env.production up -d

echo "=== 等待服务就绪 ==="
sleep 10

echo "=== 健康检查 ==="
curl -s http://localhost:8001/v1/health && echo "" || echo "后端未就绪"

echo "=== 部署完成 ==="
echo "前端: http://$(curl -s ifconfig.me)"
echo "后端: http://$(curl -s ifconfig.me):8001/v1/health"
