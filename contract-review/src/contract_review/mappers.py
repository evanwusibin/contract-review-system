"""Mappers between domain dataclasses and SQLAlchemy ORM models.

Domain objects use UUID and rich dataclasses; ORM models use str UUID,
JSONB for payloads, and DateTime(timezone=True). These functions convert both ways.
All JSONB fields are serialized/deserialized here so the store layer stays generic.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from contract_review.domain import (
    ApprovalAttachment,
    ApprovalTask,
    QualityStatus,
    TaskLog,
    TaskStatus,
)
from contract_review.parser import (
    ContractParse,
    ExtractedField,
    FieldEvidence,
    FieldStatus,
    ParseStatus,
)
from contract_review.results import CommentLog, Recommendation, ResultStatus, ReviewResult
from contract_review.rules import RuleDefinition, RuleHit, RuleHitResult, RuleStatus
from contract_review.versions import ReviewVersion

from contract_review.db import (
    ApprovalAttachment as ApprovalAttachmentORM,
    ApprovalTask as ApprovalTaskORM,
    CommentLog as CommentLogORM,
    ContractParse as ContractParseORM,
    ReviewResult as ReviewResultORM,
    ReviewRule as ReviewRuleORM,
    RuleHit as RuleHitORM,
    TaskLog as TaskLogORM,
    ReviewVersion as ReviewVersionORM,
)


# ── Field evidence helpers ────────────────────────────────────

def _evidence_to_dict(ev: FieldEvidence | None) -> dict | None:
    if ev is None:
        return None
    return {"page_no": ev.page_no, "snippet": ev.snippet, "confidence": ev.confidence}


def _dict_to_evidence(data: dict | None) -> FieldEvidence | None:
    if not data:
        return None
    return FieldEvidence(
        page_no=int(data["page_no"]),
        snippet=str(data.get("snippet", "")),
        confidence=float(data.get("confidence", 0.0)),
    )


def _payload_to_dict(payload: dict[str, ExtractedField]) -> dict:
    out: dict[str, Any] = {}
    for key, field in payload.items():
        out[key] = {
            "value": field.value,
            "status": field.status.value,
            "confidence": field.confidence,
            "evidence": _evidence_to_dict(field.evidence),
        }
    return out


def _dict_to_payload(data: dict | None) -> dict[str, ExtractedField]:
    if not data:
        return {}
    out: dict[str, ExtractedField] = {}
    for key, field in data.items():
        out[key] = ExtractedField(
            value=field.get("value"),
            status=FieldStatus(field["status"]),
            confidence=float(field.get("confidence", 0.0)),
            evidence=_dict_to_evidence(field.get("evidence")),
        )
    return out


# ── ApprovalTask ──────────────────────────────────────────────

def task_to_orm(task: ApprovalTask) -> ApprovalTaskORM:
    return ApprovalTaskORM(
        id=str(task.id),
        external_task_key=task.external_task_key,
        title=task.title,
        applicant_id=task.applicant_id,
        status=task.status.value,
        blocked_reason=task.blocked_reason,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def task_to_domain(orm: ApprovalTaskORM) -> ApprovalTask:
    return ApprovalTask(
        id=UUID(orm.id),
        external_task_key=orm.external_task_key,
        title=orm.title,
        applicant_id=orm.applicant_id,
        status=TaskStatus(orm.status),
        blocked_reason=orm.blocked_reason,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


# ── ApprovalAttachment ────────────────────────────────────────

def attachment_to_orm(att: ApprovalAttachment) -> ApprovalAttachmentORM:
    return ApprovalAttachmentORM(
        id=str(att.id),
        task_id=str(att.task_id),
        version_no=att.version_no,
        file_name=att.file_name,
        mime_type=att.mime_type,
        storage_key=att.storage_key,
        file_sha256=att.file_sha256,
        page_count=att.page_count,
        quality_status=att.quality_status.value,
        uploaded_by=att.uploaded_by,
        uploaded_at=att.uploaded_at,
        is_current=att.is_current,
    )


def attachment_to_domain(orm: ApprovalAttachmentORM) -> ApprovalAttachment:
    return ApprovalAttachment(
        id=UUID(orm.id),
        task_id=UUID(orm.task_id),
        version_no=orm.version_no,
        file_name=orm.file_name,
        mime_type=orm.mime_type,
        storage_key=orm.storage_key,
        file_sha256=orm.file_sha256,
        page_count=orm.page_count,
        quality_status=QualityStatus(orm.quality_status),
        uploaded_by=orm.uploaded_by,
        uploaded_at=orm.uploaded_at,
        is_current=orm.is_current,
    )


# ── TaskLog ──────────────────────────────────────────────────

def log_to_orm(log: TaskLog) -> TaskLogORM:
    return TaskLogORM(
        id=str(uuid4()),
        task_id=str(log.task_id) if log.task_id is not None else None,
        actor_id=log.actor_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        before_state=log.before_state,
        after_state=log.after_state,
        request_id=log.request_id,
        created_at=log.created_at,
    )


def log_to_domain(orm: TaskLogORM) -> TaskLog:
    return TaskLog(
        task_id=UUID(orm.task_id) if orm.task_id else None,
        actor_id=orm.actor_id,
        action=orm.action,
        resource_type=orm.resource_type,
        resource_id=orm.resource_id,
        before_state=orm.before_state or {},
        after_state=orm.after_state or {},
        request_id=orm.request_id,
        created_at=orm.created_at,
    )


# ── ContractParse ────────────────────────────────────────────

def parse_to_orm(parse: ContractParse) -> ContractParseORM:
    return ContractParseORM(
        id=str(parse.id),
        attachment_id=str(parse.attachment_id),
        parser_version=parse.parser_version,
        status=parse.status.value,
        quality_score=parse.quality_score,
        extracted_payload=_payload_to_dict(parse.extracted_payload),
        error_code=parse.error_code,
        error_message=parse.error_message,
        started_at=parse.started_at,
        finished_at=parse.finished_at,
    )


def parse_to_domain(orm: ContractParseORM) -> ContractParse:
    return ContractParse(
        id=UUID(orm.id),
        attachment_id=UUID(orm.attachment_id),
        parser_version=orm.parser_version,
        status=ParseStatus(orm.status),
        quality_score=orm.quality_score,
        extracted_payload=_dict_to_payload(orm.extracted_payload),
        error_code=orm.error_code,
        error_message=orm.error_message,
        started_at=orm.started_at,
        finished_at=orm.finished_at,
    )


# ── RuleHit ──────────────────────────────────────────────────

def rule_hit_to_orm(hit: RuleHit) -> RuleHitORM:
    return RuleHitORM(
        id=str(hit.id),
        parse_id=str(hit.parse_id),
        rule_id=str(hit.rule_id),
        result=hit.result.value,
        severity=hit.severity,
        message=hit.message,
        evidence=_evidence_to_dict(hit.evidence),
        suggested_action=hit.suggested_action,
        created_at=hit.created_at,
    )


def rule_hit_to_domain(orm: RuleHitORM) -> RuleHit:
    return RuleHit(
        id=UUID(orm.id),
        parse_id=UUID(orm.parse_id),
        rule_id=UUID(orm.rule_id),
        result=RuleHitResult(orm.result),
        severity=orm.severity,
        message=orm.message,
        evidence=_dict_to_evidence(orm.evidence),
        suggested_action=orm.suggested_action,
        created_at=orm.created_at,
    )


# ── ReviewResult ─────────────────────────────────────────────

def result_to_orm(result: ReviewResult) -> ReviewResultORM:
    return ReviewResultORM(
        id=str(result.id),
        task_id=str(result.task_id),
        attachment_id=str(result.attachment_id),
        recommendation=result.recommendation.value,
        status=result.status.value,
        risk_summary=result.risk_summary,
        review_comment=result.review_comment,
        required_roles=list(result.required_roles),
        confirmed_roles=list(result.confirmed_roles),
        created_by=result.created_by,
        confirmed_at=result.confirmed_at,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


def result_to_domain(orm: ReviewResultORM) -> ReviewResult:
    return ReviewResult(
        id=UUID(orm.id),
        task_id=UUID(orm.task_id),
        attachment_id=UUID(orm.attachment_id),
        recommendation=Recommendation(orm.recommendation),
        status=ResultStatus(orm.status),
        risk_summary=orm.risk_summary or {},
        review_comment=orm.review_comment,
        required_roles=tuple(orm.required_roles or ()),
        confirmed_roles=set(orm.confirmed_roles or ()),
        created_by=orm.created_by,
        confirmed_at=orm.confirmed_at,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


# ── CommentLog ───────────────────────────────────────────────

def comment_to_orm(comment: CommentLog) -> CommentLogORM:
    return CommentLogORM(
        id=str(comment.id),
        task_id=str(comment.task_id),
        result_id=str(comment.result_id),
        actor_id=comment.actor_id,
        role=comment.role,
        action=comment.action,
        comment=comment.comment,
        before_status=comment.before_status.value if comment.before_status else None,
        after_status=comment.after_status.value if comment.after_status else None,
        created_at=comment.created_at,
    )


def comment_to_domain(orm: CommentLogORM) -> CommentLog:
    return CommentLog(
        id=UUID(orm.id),
        task_id=UUID(orm.task_id),
        result_id=UUID(orm.result_id),
        actor_id=orm.actor_id,
        role=orm.role,
        action=orm.action,
        comment=orm.comment,
        before_status=ResultStatus(orm.before_status) if orm.before_status else None,
        after_status=ResultStatus(orm.after_status) if orm.after_status else None,
        created_at=orm.created_at,
    )


# ── ReviewVersion ────────────────────────────────────────────

def version_to_orm(version: ReviewVersion) -> ReviewVersionORM:
    return ReviewVersionORM(
        id=str(version.id),
        task_id=str(version.task_id),
        attachment_id=str(version.attachment_id),
        result_id=str(version.result_id),
        version_no=version.version_no,
        recommendation=version.recommendation.value,
        result_status=version.result_status.value,
        risk_summary=version.risk_summary,
        comment=version.comment,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def version_to_domain(orm: ReviewVersionORM) -> ReviewVersion:
    return ReviewVersion(
        id=UUID(orm.id),
        task_id=UUID(orm.task_id),
        attachment_id=UUID(orm.attachment_id),
        result_id=UUID(orm.result_id),
        version_no=orm.version_no,
        recommendation=Recommendation(orm.recommendation),
        result_status=ResultStatus(orm.result_status),
        risk_summary=orm.risk_summary or {},
        comment=orm.comment,
        created_by=orm.created_by,
        created_at=orm.created_at,
    )


# ── RuleDefinition ───────────────────────────────────────────

def rule_to_orm(rule: RuleDefinition) -> ReviewRuleORM:
    return ReviewRuleORM(
        id=str(rule.id),
        rule_code=rule.rule_code,
        version=rule.version,
        name=rule.name,
        contract_types=list(rule.contract_types),
        severity=rule.severity,
        expression=rule.expression,
        source_ref=rule.source_ref or None,
        status=rule.status.value,
    )


def rule_to_domain(orm: ReviewRuleORM) -> RuleDefinition:
    return RuleDefinition(
        id=UUID(orm.id),
        rule_code=orm.rule_code,
        version=orm.version,
        name=orm.name,
        contract_types=tuple(orm.contract_types or ()),
        severity=orm.severity,
        expression=orm.expression or {},
        source_ref=orm.source_ref or "",
        status=RuleStatus(orm.status),
    )
