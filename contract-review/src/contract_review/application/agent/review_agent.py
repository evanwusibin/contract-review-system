"""Agent 编排层 — 工具调用链 + 状态机 + 异常阻塞（2.4.8/2.4.4）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from contract_review.domain import InMemoryReviewStore, TaskStatus, WriteStatus
from contract_review.infrastructure.storage.mock import mock_attachment_content
from contract_review.application.tools.contract_tools import download_contract_attachment, get_contract_approval, parse_contract_document, run_contract_rules, save_review_result, write_approval_comment


@dataclass
class AgentStep:
    step: str
    tool: str
    input: dict[str, Any]
    output: dict[str, Any]
    status: str
    thought: str


@dataclass
class AgentRun:
    instance_id: str
    trajectory: list[AgentStep] = field(default_factory=list)
    final_status: str = "pending"
    overall_risk_level: str | None = None
    summary_text: str | None = None
    blocked_reason: str | None = None


class ContractReviewAgent:
    def __init__(self, store: InMemoryReviewStore, parser, engine, rule_definitions) -> None:
        self.store = store
        self.parser = parser
        self.engine = engine
        self.rule_definitions = rule_definitions

    def run_full_loop(self, instance_id: str) -> AgentRun:
        run = AgentRun(instance_id=instance_id)
        try:
            detail = get_contract_approval(self.store, instance_id)
            run.trajectory.append(AgentStep("1-详情", "get_contract_approval", {"instance_id": instance_id}, detail, "success", "获取审批详情与附件清单"))
            if not detail.get("attachments"):
                task = self.store.find_task(instance_id)
                if task:
                    task.status = TaskStatus.BLOCKED
                    task.blocked_reason = "附件缺失"
                    task.updated_at = datetime.now(timezone.utc)
                    self.store.save_task(task)
                run.final_status = "blocked"
                run.blocked_reason = "附件缺失，无法进入解析"
                return run
            att = detail["attachments"][0]
            att_id = att["attachment_id"]
            dl = download_contract_attachment(self.store, instance_id, att_id, att.get("file_name"))
            content = dl.get("file_content") or mock_attachment_content(instance_id, att_id)
            if "file_sha256" not in dl:
                import hashlib
                dl["file_sha256"] = hashlib.sha256(content).hexdigest()
            run.trajectory.append(AgentStep("2-附件", "download_contract_attachment", {"attachment_id": att_id}, {"file_sha256": dl["file_sha256"]}, "success", "下载附件并校验完整性"))
            pr = parse_contract_document(self.store, self.parser, att_id, content)
            run.trajectory.append(AgentStep("3-解析", "parse_contract_document", {"document_id": att_id}, pr, pr.get("parse_status", "success"), "解析合同字段与证据定位"))
            if pr.get("parse_status") == "blocked":
                run.final_status = "blocked"
                run.blocked_reason = pr.get("parse_error")
                return run
            rr = run_contract_rules(self.store, self.engine, self.rule_definitions, instance_id)
            run.trajectory.append(AgentStep("4-规则", "run_contract_rules", {"case_id": instance_id}, {"overall": rr["overall_risk_level"], "hits": rr["total"]}, "success", "规则审查与风险汇总"))
            summary = f"合同 {instance_id} 风险等级 {rr['overall_risk_level']}，命中 {rr['total']} 条规则。"
            focus = rr["focus_points"]
            comment = f"【自动审查意见】风险等级：{rr['overall_risk_level']}；关注点：{'；'.join(focus) if focus else '无'}；请重点核对证据片段与条款位置。"
            sr = save_review_result(self.store, instance_id if self._is_task_id(instance_id) else self._resolve_task_id(instance_id), rr["overall_risk_level"], summary, focus, comment)
            run.trajectory.append(AgentStep("5-保存", "save_review_result", {"overall": rr["overall_risk_level"]}, sr, "success", "保存审查结果与摘要"))
            wr = write_approval_comment(self.store, instance_id, sr["review_id"])
            run.trajectory.append(AgentStep("6-回写", "write_approval_comment", {"review_id": sr["review_id"]}, wr, wr["write_status"], "将意见写回审批评论区"))
            run.final_status = "done" if wr["write_status"] == WriteStatus.SUCCESS.value else "blocked"
            run.overall_risk_level = rr["overall_risk_level"]
            run.summary_text = summary
            return run
        except Exception as exc:
            run.trajectory.append(AgentStep("error", "agent", {"instance_id": instance_id}, {"error": str(exc)}, "blocked", f"异常进入 blocked: {exc}"))
            run.final_status = "blocked"
            run.blocked_reason = str(exc)
            try:
                t = self.store.find_task(instance_id) or self.store.get_task(self._resolve_task_id(instance_id))  # type: ignore[arg-type]
                if t:
                    t.status = TaskStatus.BLOCKED
                    t.blocked_reason = str(exc)[:500]
                    self.store.save_task(t)
            except Exception:
                pass
            return run

    def _is_task_id(self, s: str) -> bool:
        try:
            from uuid import UUID
            UUID(s)
            return True
        except Exception:
            return False

    def _resolve_task_id(self, instance_id: str) -> str:
        t = self.store.find_task(instance_id)
        if t:
            return str(t.id)
        from uuid import uuid4
        from contract_review.domain import ApprovalTask
        now = datetime.now(timezone.utc)
        detail = get_contract_approval(self.store, instance_id) if instance_id.startswith("CTR-") else None
        title = detail["title"] if detail else instance_id
        applicant = detail["applicant_id"] if detail else "mock"
        task = ApprovalTask(uuid4(), instance_id, title, applicant, TaskStatus.PENDING, None, now, now, WriteStatus.NOT_WRITTEN, instance_id)
        self.store.save_task(task)
        return str(task.id)

    def retry_blocked(self, instance_id: str) -> dict[str, Any]:
        t = self.store.find_task(instance_id)
        if not t:
            raise ValueError("任务不存在")
        if t.status != TaskStatus.BLOCKED:
            raise ValueError("仅 blocked 可重试")
        t.retry()
        self.store.save_task(t)
        return {"task_status": t.status.value, "write_status": t.write_status.value}
