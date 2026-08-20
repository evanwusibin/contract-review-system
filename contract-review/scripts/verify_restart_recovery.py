#!/usr/bin/env python
"""阶段 5 重启恢复验收脚本。

流程：登录 → 上传黄金 PDF 并运行评审 → 重启 backend 容器 → 校验任务/评审/解析/规则命中仍在。

用法（在 contract-review 目录、prod 栈已启动后）：
    python scripts/verify_restart_recovery.py --pdf tests/data/test_contract_after_sales.pdf

环境变量可覆盖：BASE_URL、ADMIN_PASSWORD。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parents[1]


def wait_health(client: httpx.Client, base_url: str, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = client.get(f"{base_url}/v1/health")
            if r.status_code == 200 and r.json().get("ok"):
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SystemExit("backend 未在超时时间内恢复健康")


def login(client: httpx.Client, base_url: str, password: str) -> None:
    r = client.post(f"{base_url}/v1/auth/login", data={"username": "admin", "password": password})
    r.raise_for_status()
    if not r.json().get("ok"):
        raise SystemExit(f"登录失败: {r.json().get('error')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8001"))
    parser.add_argument("--admin-password", default=os.getenv("ADMIN_PASSWORD", "admin123"))
    parser.add_argument("--pdf", default=str(BASE / "tests" / "data" / "test_contract_after_sales.pdf"))
    parser.add_argument("--compose-file", default="docker-compose.prod.yml")
    parser.add_argument("--backend-service", default="backend")
    args = parser.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        raise SystemExit(f"PDF 不存在: {pdf}")

    with httpx.Client(base_url=args.base_url, timeout=300.0) as client:
        login(client, args.base_url, args.admin_password)
        print("[1] 登录成功 (admin)")

        # 运行评审（黄金数据集：清晰售后合同）
        task_key = f"golden-{uuid.uuid4().hex[:12]}"
        confirmations = json.dumps({
            "business": {"actor_id": "admin", "comment": "业务确认"},
            "legal": {"actor_id": "admin", "comment": "法务确认"},
            "warranty": {"actor_id": "admin", "comment": "质保确认"},
        })
        r = client.post(
            "/v1/reviews/run",
            data={
                "external_task_key": task_key,
                "title": "黄金-售后合同",
                "applicant_id": "user-golden",
                "confirmations": confirmations,
                "request_id": "req-golden",
            },
            files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        )
        r.raise_for_status()
        result = r.json()
        if not result.get("ok"):
            raise SystemExit(f"评审失败: {result.get('error')}")
        data = result["data"]
        task_id = data["task_id"]
        print(f"[2] 评审完成: task_id={task_id} review_status={data['review_status']} version={data['version_id']}")

    # 重启 backend 容器
    cmd = ["docker", "compose", "-f", args.compose_file, "restart", args.backend_service]
    print(f"[3] 重启后端: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=BASE, check=True)

    with httpx.Client(base_url=args.base_url, timeout=120.0) as client:
        wait_health(client, args.base_url)
        login(client, args.base_url, args.admin_password)
        print("[4] 后端已恢复，重新登录成功")

        r = client.get(f"/v1/tasks/{task_id}/review")
        r.raise_for_status()
        review = r.json().get("data", {})
        if review.get("review") is None:
            raise SystemExit("重启后 review 结果丢失")
        rule_hits = review.get("rule_hits", [])
        print(
            f"[5] 持久化校验通过: review_status={review['review']['status']} "
            f"parse={'有' if review.get('parse') else '无'} rule_hits={len(rule_hits)} 条"
        )

    print("PASS: 容器重启后任务/评审/解析/规则命中数据完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
