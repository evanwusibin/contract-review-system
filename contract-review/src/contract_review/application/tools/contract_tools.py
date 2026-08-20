"""7大工具接口 — 满足 2.4.10/2.4.3（2.4.1接入/输出能力）。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contract_review.domain import ApprovalTask, InMemoryReviewStore, TaskStatus, WriteStatus
from contract_review.infrastructure.storage.mock import get_mock_approval, list_mock_approvals, mock_attachment_content
from contract_review.engine.parser.service import ContractParser, ParseStatus
from contract_review.engine.workflow.results import ReviewResult
from contract_review.engine.rules.engine import RestrictedRuleEngine, RuleDefinition


def list_pending_contract_approvals(store: InMemoryReviewStore, limit: int = 10) -> dict[str, Any]:
    tasks = sorted(store.list_tasks(), key=lambda t: t.created_at, reverse=True)
    if tasks:
        items = []
        for t in tasks[:limit]:
            atts = store.list_attachments(t.id)
            items.append(
                {
                    "instance_id": t.external_task_key,
                    "approval_code": getattr(t, "approval_code", t.external_task_key),
                    "approval_title": t.title,
                    "title": t.title,
                    "applicant_name": getattr(t, "applicant_name", t.applicant_id),
                    "applicant_id": t.applicant_id,
                    "applicant_time": t.created_at.isoformat(),
                    "apply_time": t.created_at.isoformat(),
                    "attachment_count": len(atts),
                    "status": t.status.value,
                    "write_status": getattr(t, "write_status", WriteStatus.NOT_WRITTEN).value,
                }
            )
        return {"items": items, "total": len(tasks), "source": "store"}
    mocks = list_mock_approvals(limit=limit)
    return {"items": mocks, "total": len(mocks), "source": "mock"}


def get_contract_approval(store: InMemoryReviewStore, instance_id: str) -> dict[str, Any]:
    task = store.find_task(instance_id)
    if task is not None:
        atts = store.list_attachments(task.id)
        return {
            "instance_id": instance_id,
            "approval_code": getattr(task, "approval_code", task.external_task_key),
            "approval_title": task.title,
            "title": task.title,
            "applicant_name": getattr(task, "applicant_name", task.applicant_id),
            "applicant_id": task.applicant_id,
            "applicant_time": task.created_at.isoformat(),
            "form_data": {"contract_title": task.title, "contract_code": instance_id},
            "attachments": [
                {
                    "attachment_id": str(a.id),
                    "file_name": a.file_name,
                    "file_type": a.mime_type.split("/")[-1] if "/" in a.mime_type else a.mime_type,
                    "file_path": a.storage_key,
                    "file_size": 0,
                    "download_status": "ready",
                }
                for a in atts
            ],
            "status": task.status.value,
            "write_status": getattr(task, "write_status", WriteStatus.NOT_WRITTEN).value,
            "task_status": task.status.value,
            "blocked_reason": task.blocked_reason,
        }
    mock = get_mock_approval(instance_id)
    if mock is None:
        raise ValueError(f"审批单不存在: {instance_id}")
    return mock


def download_contract_attachment(store: InMemoryReviewStore, instance_id: str, attachment_id: str, file_name: str | None = None) -> dict[str, Any]:
    try:
        aid = UUID(attachment_id)
        att = store.get_attachment(aid)
        if att is not None:
            return {
                "instance_id": instance_id,
                "attachment_id": attachment_id,
                "file_name": att.file_name,
                "file_path": att.storage_key,
                "file_sha256": att.file_sha256,
                "file_type": att.mime_type,
                "download_status": "success",
            }
    except Exception:
        pass
    content = mock_attachment_content(instance_id, attachment_id)
    sha = hashlib.sha256(content).hexdigest()
    return {
        "instance_id": instance_id,
        "attachment_id": attachment_id,
        "file_name": file_name or f"{instance_id}_{attachment_id}.pdf",
        "file_path": f"mock/{instance_id}/{attachment_id}.pdf",
        "file_content": content,
        "file_sha256": sha,
        "file_type": "application/pdf",
        "download_status": "success",
        "source": "mock",
    }


def parse_contract_document(store: InMemoryReviewStore, parser: ContractParser, document_id: str, content: bytes | None = None) -> dict[str, Any]:
    try:
        aid = UUID(document_id)
    except Exception as exc:
        raise ValueError(f"非法 document_id: {document_id}") from exc
    att = store.get_attachment(aid)
    if att is None:
        raise ValueError(f"附件不存在: {document_id}")
    task = store.get_task(att.task_id)
    if task is None:
        raise ValueError("关联任务不存在")
    task.status = TaskStatus.PARSING
    task.updated_at = datetime.now(timezone.utc)
    store.save_task(task)
    if content is None:
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = "附件内容为空，无法解析"
        task.updated_at = datetime.now(timezone.utc)
        store.save_task(task)
        store.append_log(_log(task.id, "parse_blocked", "parse_contract_document", "附件内容为空"))
        return {"parse_status": "blocked", "parse_error": task.blocked_reason, "task_status": task.status.value}
    if not content:
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = "文档内容为空"
        task.updated_at = datetime.now(timezone.utc)
        store.save_task(task)
        return {"parse_status": "blocked", "parse_error": task.blocked_reason, "task_status": task.status.value}
    if not content.startswith(b"%PDF-"):
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = "文件不是有效PDF，无法识别"
        task.updated_at = datetime.now(timezone.utc)
        store.save_task(task)
        return {"parse_status": "blocked", "parse_error": task.blocked_reason, "task_status": task.status.value}
    parsed = parser.parse(task, att, content, request_id="tool_parse")
    if parsed.status is not ParseStatus.SUCCEEDED:
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = parsed.error_message or "解析失败"
        task.updated_at = datetime.now(timezone.utc)
        store.save_task(task)
        return {"parse_status": "blocked", "parse_error": task.blocked_reason, "task_status": task.status.value}
    task.status = TaskStatus.REVIEWING
    task.updated_at = datetime.now(timezone.utc)
    store.save_task(task)
    return {"parse_id": str(parsed.id), "parse_status": "success", "task_status": task.status.value, "basic_info": getattr(parsed, "extracted_payload", {}), "clause_info": {}, "extracted_payload": getattr(parsed, "extracted_payload", {})}


def run_contract_rules(store: InMemoryReviewStore, engine: RestrictedRuleEngine, rule_definitions: list[RuleDefinition], case_id: str) -> dict[str, Any]:
    parse = None
    try:
        tid = UUID(case_id)
        parse = store.get_parse_for_task(tid)
        if parse is None:
            parse = store.get_parse(tid)
    except Exception:
        parse = None
    if parse is None:
        raise ValueError(f"未找到可审查的解析结果: {case_id}")
    task_id = getattr(parse, "task_id", None) or store.get_attachment(parse.attachment_id).task_id if store.get_attachment(parse.attachment_id) else None
    task = store.get_task(task_id) if task_id else None
    if task is not None:
        task.status = TaskStatus.REVIEWING
        task.updated_at = datetime.now(timezone.utc)
        store.save_task(task)
    hits = engine.run(parse, rule_definitions, request_id="tool_rules")
    for h in hits:
        store.save_rule_hit(h)
    overall = _overall_risk(hits)
    focus = _focus_points(hits)
    return {"hits": [{"rule_name": h.message, "risk_level": h.severity, "evidence_text": getattr(h, "evidence_text", h.message), "evidence_position": getattr(h, "evidence_position", None), "suggested_action": h.suggested_action, "result": h.result.value} for h in hits], "overall_risk_level": overall, "focus_points": focus, "total": len(hits), "task_status": task.status.value if task else "reviewing"}


def save_review_result(store: InMemoryReviewStore, case_id: str, overall_risk_level: str, summary_text: str, focus_points_json: list[str] | None, comment_text: str) -> dict[str, Any]:
    tid = UUID(case_id)
    task = store.get_task(tid)
    if task is None:
        raise ValueError(f"任务不存在: {case_id}")
    atts = store.list_attachments(tid)
    attachment_id = atts[-1].id if atts else tid
    from contract_review.engine.workflow.results import Recommendation, ResultStatus, ReviewResult
    level = overall_risk_level if overall_risk_level in ("low", "medium", "high") else "medium"
    rec_map = {"low": Recommendation.PASS, "medium": Recommendation.MANUAL_REVIEW, "high": Recommendation.REJECT}
    result = ReviewResult(id=uuid4(), task_id=tid, attachment_id=attachment_id, recommendation=rec_map[level], status=ResultStatus.DRAFT, risk_summary={"overall": level}, review_comment=comment_text, required_roles=("business", "legal"), confirmed_roles=set(), created_by="system", confirmed_at=None, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    object.__setattr__(result, "overall_risk_level", level)
    object.__setattr__(result, "summary_text", summary_text)
    object.__setattr__(result, "focus_points_json", focus_points_json or [])
    object.__setattr__(result, "comment_text", comment_text)
    store.save_result(result)
    store.append_log(_log(tid, "result_saved", "save_review_result", f"overall={level}"))
    return {"review_id": str(result.id), "overall_risk_level": level, "summary_text": summary_text, "focus_points": focus_points_json or []}


def write_approval_comment(store: InMemoryReviewStore, instance_id: str, review_id: str) -> dict[str, Any]:
    tid = None
    try:
        tid = UUID(instance_id)
        task = store.get_task(tid)
    except Exception:
        task = store.find_task(instance_id)
        tid = task.id if task else None
    if task is None or tid is None:
        raise ValueError(f"任务不存在: {instance_id}")
    try:
        rid = UUID(review_id)
    except Exception as exc:
        raise ValueError(f"非法 review_id: {review_id}") from exc
    result = store.get_result(rid)
    if result is None:
        raise ValueError(f"审查结果不存在: {review_id}")
    comment_text = getattr(result, "comment_text", None) or getattr(result, "review_comment", None) or ""
    if not comment_text:
        comment_text = f"【合同评审】风险等级 {getattr(result, 'overall_risk_level', 'medium')}，建议 {result.recommendation.value}"
    task.write_status = WriteStatus.WRITING  # type: ignore[attr-defined]
    task.updated_at = datetime.now(timezone.utc)
    store.save_task(task)
    from contract_review.engine.workflow.results import CommentLog, ResultStatus
    write_status = WriteStatus.SUCCESS
    response_text = f"SIMULATED_ONLY: 已写回审批 {getattr(task, 'approval_code', task.external_task_key)} 评论区"
    task.write_status = write_status  # type: ignore[attr-defined]
    task.updated_at = datetime.now(timezone.utc)
    store.save_task(task)
    clog = CommentLog(id=uuid4(), task_id=tid, result_id=rid, actor_id="system", role="legal", action="write_comment", comment=comment_text, before_status=ResultStatus.DRAFT, after_status=ResultStatus.DRAFT, created_at=datetime.now(timezone.utc))
    object.__setattr__(clog, "write_status", write_status.value)
    object.__setattr__(clog, "write_response_text", response_text)
    store.save_comment(clog)
    store.append_log(_log(tid, "comment_written", "write_approval_comment", response_text))
    return {"write_status": write_status.value, "write_response_text": response_text, "comment_text": comment_text}


def _overall_risk(hits: list[Any]) -> str:
    severities = [getattr(h, "severity", "low") for h in hits if getattr(h, "result", None) and getattr(h.result, "value", "") == "hit"]
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"

def _focus_points(hits: list[Any]) -> list[str]:
    pts = []
    for h in hits:
        if getattr(h, "result", None) and getattr(h.result, "value", "") == "hit":
            pts.append(getattr(h, "suggested_action", None) or h.message)
    return pts[:5]

def _log(task_id: UUID, action: str, request_id: str, content: str):
    from contract_review.domain import TaskLog
    return TaskLog(task_id=task_id, actor_id="system", action=action, resource_type="tool", resource_id=str(task_id), before_state={}, after_state={"log_content": content}, request_id=request_id, created_at=datetime.now(timezone.utc))
