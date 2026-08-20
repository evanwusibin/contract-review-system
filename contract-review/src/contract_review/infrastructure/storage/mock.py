"""Mock审批系统 — 用于无真实审批时的演示闭环（2.4.3/2.4.12）。

提供 15 条模拟待办，字段满足 2.4.3：审批编号、标题、申请人、申请时间、附件数量。
支持去重查询、附件下载模拟，配合工具层演示完整链路。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

MOCK_APPROVALS: list[dict[str, Any]] = [
    {"approval_code": "CTR-2026-0001", "title": "华东区年度采购框架协议", "applicant": "张明", "applicant_id": "zhangming", "contract_type": "采购合同"},
    {"approval_code": "CTR-2026-0002", "title": "供应链物流服务合同", "applicant": "李娜", "applicant_id": "lina", "contract_type": "服务合同"},
    {"approval_code": "CTR-2026-0003", "title": "软件许可与保密协议", "applicant": "王强", "applicant_id": "wangqiang", "contract_type": "保密协议"},
    {"approval_code": "CTR-2026-0004", "title": "办公场地租赁合同", "applicant": "陈静", "applicant_id": "chenjing", "contract_type": "租赁合同"},
    {"approval_code": "CTR-2026-0005", "title": "知识产权转让协议", "applicant": "赵磊", "applicant_id": "zhaolei", "contract_type": "知识产权"},
    {"approval_code": "CTR-2026-0006", "title": "数据处理委托协议", "applicant": "孙悦", "applicant_id": "sunyue", "contract_type": "数据协议"},
    {"approval_code": "CTR-2026-0007", "title": "年度销售代理合同", "applicant": "周涛", "applicant_id": "zhoutao", "contract_type": "销售合同"},
    {"approval_code": "CTR-2026-0008", "title": "建设工程施工合同", "applicant": "吴敏", "applicant_id": "wumin", "contract_type": "工程合同"},
    {"approval_code": "CTR-2026-0009", "title": "技术服务与验收协议", "applicant": "郑浩", "applicant_id": "zhenghao", "contract_type": "服务合同"},
    {"approval_code": "CTR-2026-0010", "title": "保密与竞业限制协议", "applicant": "冯洁", "applicant_id": "fengjie", "contract_type": "保密协议"},
    {"approval_code": "CTR-2026-0011", "title": "跨境货物运输合同", "applicant": "黄伟", "applicant_id": "huangwei", "contract_type": "运输合同"},
    {"approval_code": "CTR-2026-0012", "title": "云服务订阅与SLA协议", "applicant": "刘洋", "applicant_id": "liuyang", "contract_type": "服务合同"},
    {"approval_code": "CTR-2026-0013", "title": "联合研发合作协议", "applicant": "徐倩", "applicant_id": "xuqian", "contract_type": "合作协议"},
    {"approval_code": "CTR-2026-0014", "title": "设备采购及验收合同", "applicant": "马超", "applicant_id": "machao", "contract_type": "采购合同"},
    {"approval_code": "CTR-2026-0015", "title": "股权转让与付款协议", "applicant": "林芳", "applicant_id": "linfang", "contract_type": "股权协议"},
]


def _base_time(i: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=15 - i, hours=i)


@dataclass
class MockAttachmentMeta:
    attachment_id: str
    file_name: str
    file_type: str
    file_size: int


def list_mock_approvals(limit: int = 10) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, base in enumerate(MOCK_APPROVALS[: max(1, min(limit, len(MOCK_APPROVALS)))]):
        t = _base_time(idx)
        attachment_count = 0 if base["approval_code"] in ("CTR-2026-0008", "CTR-2026-0015") else (1 if idx % 3 == 0 else 2)
        out.append(
            {
                "instance_id": base["approval_code"],
                "approval_code": base["approval_code"],
                "approval_title": base["title"],
                "title": base["title"],
                "applicant_name": base["applicant"],
                "applicant_id": base["applicant_id"],
                "applicant_time": t.isoformat(),
                "apply_time": t.isoformat(),
                "attachment_count": attachment_count,
                "contract_type": base["contract_type"],
                "status": "pending",
            }
        )
    return out


def get_mock_approval(instance_id: str) -> dict[str, Any] | None:
    base = next((x for x in MOCK_APPROVALS if x["approval_code"] == instance_id), None)
    if base is None:
        return None
    atts: list[dict[str, Any]]
    if instance_id == "CTR-2026-0008":
        atts = []
    elif instance_id == "CTR-2026-0015":
        atts = []
    else:
        atts = [
            {
                "attachment_id": f"{instance_id}-ATT-01",
                "file_name": f"{instance_id}_主合同.pdf",
                "file_type": "pdf",
                "file_size": 482_000 + hash(instance_id) % 200_000,
                "download_status": "ready",
            }
        ]
        if hash(instance_id) % 3 == 0:
            atts.append(
                {
                    "attachment_id": f"{instance_id}-ATT-02",
                    "file_name": f"{instance_id}_补充协议.pdf",
                    "file_type": "pdf",
                    "file_size": 120_000 + hash(instance_id) % 80_000,
                    "download_status": "ready",
                }
            )
    applicant_time = _base_time(5).isoformat()
    return {
        "instance_id": instance_id,
        "approval_code": instance_id,
        "approval_title": base["title"],
        "title": base["title"],
        "applicant_name": base["applicant"],
        "applicant_id": base["applicant_id"],
        "applicant_time": applicant_time,
        "contract_type": base["contract_type"],
        "form_data": {
            "contract_title": base["title"],
            "contract_code": instance_id,
            "counterparty": "示例对方公司",
            "amount": "1,280,000",
            "currency": "CNY",
            "effective_date": "2026-03-01",
            "expiry_date": "2027-02-28",
        },
        "attachments": atts,
        "status": "pending" if atts else "blocked",
        "blocked_reason": None if atts else "附件缺失，无法进入解析",
    }


def mock_attachment_content(instance_id: str, attachment_id: str) -> bytes:
    seed = f"{instance_id}:{attachment_id}".encode()
    digest = hashlib.sha256(seed).hexdigest()[:8]
    text = f"合同编号 {instance_id} 附件 {attachment_id} 示例文本 付款条款 30% 预付款 交付条款 保密条款"
    body = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 50 700 Td ("
        + text.encode()[:30]
        + b") Tj ET\nendstream endobj\n"
        b"xref\ntrailer<</Root 1 0 R>>\n%%EOF\n"
        + digest.encode()
    )
    return body
