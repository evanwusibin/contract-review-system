from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from contract_review.domain import ApprovalAttachment, ApprovalTask, TaskLog
from contract_review.infrastructure import models
from contract_review.results import CommentLog, ReviewResult
from contract_review.rules import RuleDefinition, RuleHit
from contract_review.versions import ReviewVersion


class SqlTaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, task_id: object) -> ApprovalTask | None:
        row = self.session.get(models.ApprovalTaskModel, task_id)
        return _task_from_row(row) if row else None

    def get_by_external_key(self, external_key: str) -> ApprovalTask | None:
        row = self.session.scalar(
            select(models.ApprovalTaskModel).where(
                models.ApprovalTaskModel.external_task_key == external_key
            )
        )
        return _task_from_row(row) if row else None

    def list_all(self) -> list[ApprovalTask]:
        rows = self.session.scalars(
            select(models.ApprovalTaskModel)
            .where(models.ApprovalTaskModel.deleted_at.is_(None))
            .order_by(models.ApprovalTaskModel.updated_at.desc())
        ).all()
        return [_task_from_row(row) for row in rows]

    def save(self, task: ApprovalTask) -> None:
        row = self.session.get(models.ApprovalTaskModel, task.id)
        if row is None:
            row = models.ApprovalTaskModel(
                id=task.id,
                external_task_key=task.external_task_key,
                title=task.title,
                applicant_id=task.applicant_id,
                status=task.status.value,
                blocked_reason=task.blocked_reason,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            self.session.add(row)
        else:
            row.status = task.status.value
            row.title = task.title
            row.blocked_reason = task.blocked_reason
            row.updated_at = task.updated_at


class SqlAttachmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, attachment_id: object) -> ApprovalAttachment | None:
        row = self.session.get(models.ApprovalAttachmentModel, attachment_id)
        return _attachment_from_row(row) if row else None

    def find_by_task_and_hash(self, task_id: object, file_hash: str) -> ApprovalAttachment | None:
        row = self.session.scalar(
            select(models.ApprovalAttachmentModel).where(
                models.ApprovalAttachmentModel.task_id == task_id,
                models.ApprovalAttachmentModel.file_sha256 == file_hash,
            )
        )
        return _attachment_from_row(row) if row else None

    def list_by_task(self, task_id: object) -> list[ApprovalAttachment]:
        rows = self.session.scalars(
            select(models.ApprovalAttachmentModel).where(
                models.ApprovalAttachmentModel.task_id == task_id
            )
        ).all()
        return [_attachment_from_row(row) for row in rows]

    def save(self, attachment: ApprovalAttachment) -> None:
        row = self.session.get(models.ApprovalAttachmentModel, attachment.id)
        if row is None:
            row = models.ApprovalAttachmentModel(
                id=attachment.id,
                task_id=attachment.task_id,
                version_no=attachment.version_no,
                file_name=attachment.file_name,
                mime_type=attachment.mime_type,
                storage_key=attachment.storage_key,
                file_sha256=attachment.file_sha256,
                page_count=attachment.page_count,
                quality_status=attachment.quality_status.value,
                uploaded_by=attachment.uploaded_by,
                uploaded_at=attachment.uploaded_at,
                is_current=attachment.is_current,
            )
            self.session.add(row)
        else:
            row.quality_status = attachment.quality_status.value
            row.is_current = attachment.is_current

    def next_version(self, task_id: object) -> int:
        rows = self.session.scalars(
            select(models.ApprovalAttachmentModel.version_no).where(
                models.ApprovalAttachmentModel.task_id == task_id
            )
        ).all()
        return max(rows, default=-1) + 1


class SqlTaskLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, log: TaskLog) -> None:
        self.session.add(
            models.TaskLogModel(
                id=uuid4(),
                task_id=log.task_id,
                actor_id=log.actor_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                before_state=log.before_state,
                after_state=log.after_state,
                request_id=log.request_id,
                created_at=log.created_at,
            )
        )

    def list_by_task(self, task_id: object) -> list[TaskLog]:
        rows = self.session.scalars(
            select(models.TaskLogModel)
            .where(models.TaskLogModel.task_id == task_id)
            .order_by(models.TaskLogModel.created_at.desc())
        ).all()
        return [_task_log_from_row(row) for row in rows]

    def list_all(self, limit: int = 50, offset: int = 0) -> list[TaskLog]:
        rows = self.session.scalars(
            select(models.TaskLogModel)
            .order_by(models.TaskLogModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [_task_log_from_row(row) for row in rows]

    def count_all(self) -> int:
        return self.session.scalar(select(models.TaskLogModel).where().with_only_columns(__import__("sqlalchemy").func.count())) or 0


class SqlRuleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, rule_id: object) -> RuleDefinition | None:
        row = self.session.get(models.ReviewRuleModel, rule_id)
        return _rule_from_row(row) if row else None

    def list_all(self) -> list[RuleDefinition]:
        rows = self.session.scalars(select(models.ReviewRuleModel)).all()
        return [_rule_from_row(row) for row in rows]

    def list_published(self) -> list[RuleDefinition]:
        rows = self.session.scalars(
            select(models.ReviewRuleModel).where(models.ReviewRuleModel.status == "published")
        ).all()
        return [_rule_from_row(row) for row in rows]

    def save(self, rule: RuleDefinition) -> None:
        row = self.session.get(models.ReviewRuleModel, rule.id)
        if row is None:
            row = models.ReviewRuleModel(
                id=rule.id,
                rule_code=rule.rule_code,
                version=rule.version,
                name=rule.name,
                contract_types=list(rule.contract_types),
                severity=rule.severity,
                expression=rule.expression,
                source_ref=rule.source_ref,
                status=rule.status.value,
            )
            self.session.add(row)
        else:
            row.name = rule.name
            row.severity = rule.severity
            row.expression = rule.expression
            row.status = rule.status.value
            row.source_ref = rule.source_ref


class SqlReviewResultRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, result_id: object) -> ReviewResult | None:
        row = self.session.get(models.ReviewResultModel, result_id)
        return _result_from_row(row) if row else None

    def get_latest_by_task(self, task_id: object) -> ReviewResult | None:
        row = self.session.scalar(
            select(models.ReviewResultModel)
            .where(models.ReviewResultModel.task_id == task_id)
            .order_by(models.ReviewResultModel.updated_at.desc())
        )
        return _result_from_row(row) if row else None

    def list_by_task(self, task_id: object) -> list[ReviewResult]:
        rows = self.session.scalars(
            select(models.ReviewResultModel)
            .where(models.ReviewResultModel.task_id == task_id)
            .order_by(models.ReviewResultModel.updated_at.desc())
        ).all()
        return [_result_from_row(row) for row in rows]

    def save(self, result: ReviewResult) -> None:
        row = self.session.get(models.ReviewResultModel, result.id)
        if row is None:
            row = models.ReviewResultModel(
                id=result.id,
                task_id=result.task_id,
                attachment_id=result.attachment_id,
                recommendation=result.recommendation.value,
                status=result.status.value,
                risk_summary=dict(result.risk_summary),
                review_comment=result.review_comment,
                required_roles=list(result.required_roles),
                confirmed_roles=list(result.confirmed_roles),
                created_by=result.created_by,
                confirmed_at=result.confirmed_at,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
            self.session.add(row)
        else:
            row.status = result.status.value
            row.recommendation = result.recommendation.value
            row.risk_summary = dict(result.risk_summary)
            row.review_comment = result.review_comment
            row.confirmed_roles = list(result.confirmed_roles)
            row.confirmed_at = result.confirmed_at
            row.updated_at = result.updated_at


class SqlCommentLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, log: CommentLog) -> None:
        self.session.add(
            models.CommentLogModel(
                id=uuid4(),
                task_id=log.task_id,
                result_id=log.result_id,
                actor_id=log.actor_id,
                role=log.role,
                action=log.action,
                comment=log.comment,
                before_status=log.before_status.value,
                after_status=log.after_status.value,
                created_at=log.created_at,
            )
        )

    def list_by_task(self, task_id: object) -> list[CommentLog]:
        rows = self.session.scalars(
            select(models.CommentLogModel)
            .where(models.CommentLogModel.task_id == task_id)
            .order_by(models.CommentLogModel.created_at.desc())
        ).all()
        return [
            CommentLog(
                id=row.id, task_id=row.task_id, result_id=row.result_id, actor_id=row.actor_id,
                role=row.role, action=row.action, comment=row.comment,
                before_status=row.before_status, after_status=row.after_status, created_at=row.created_at,
            )
            for row in rows
        ]


class SqlVersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, version: ReviewVersion) -> None:
        self.session.add(
            models.ReviewVersionModel(
                id=version.id,
                task_id=version.task_id,
                attachment_id=version.attachment_id,
                version_no=version.version_no,
                recommendation=version.recommendation.value,
                result_status=version.result_status.value,
                risk_summary=dict(version.risk_summary),
                comment=version.comment,
                created_by=version.created_by,
                created_at=version.created_at,
            )
        )

    def list_by_task(self, task_id: object) -> list[ReviewVersion]:
        rows = self.session.scalars(
            select(models.ReviewVersionModel)
            .where(models.ReviewVersionModel.task_id == task_id)
            .order_by(models.ReviewVersionModel.version_no)
        ).all()
        return [_version_from_row(row) for row in rows]

    def get_by_id(self, version_id: object) -> ReviewVersion | None:
        row = self.session.get(models.ReviewVersionModel, version_id)
        return _version_from_row(row) if row else None


# ── mappers ──────────────────────────────────────────────────────

def _task_from_row(row: models.ApprovalTaskModel) -> ApprovalTask:
    return ApprovalTask(
        id=row.id, external_task_key=row.external_task_key, title=row.title,
        applicant_id=row.applicant_id, status=row.status,
        blocked_reason=row.blocked_reason, created_at=row.created_at, updated_at=row.updated_at,
    )


def _attachment_from_row(row: models.ApprovalAttachmentModel) -> ApprovalAttachment:
    return ApprovalAttachment(
        id=row.id, task_id=row.task_id, version_no=row.version_no, file_name=row.file_name,
        mime_type=row.mime_type, storage_key=row.storage_key, file_sha256=row.file_sha256,
        page_count=row.page_count, quality_status=row.quality_status,
        uploaded_by=row.uploaded_by, uploaded_at=row.uploaded_at, is_current=row.is_current,
    )


def _task_log_from_row(row: models.TaskLogModel) -> TaskLog:
    return TaskLog(
        task_id=row.task_id, actor_id=row.actor_id, action=row.action,
        resource_type=row.resource_type, resource_id=row.resource_id,
        before_state=row.before_state, after_state=row.after_state,
        request_id=row.request_id, created_at=row.created_at,
    )


def _rule_from_row(row: models.ReviewRuleModel) -> RuleDefinition:
    from contract_review.rules import RuleStatus

    return RuleDefinition(
        id=row.id, rule_code=row.rule_code, version=row.version, name=row.name,
        contract_types=tuple(row.contract_types or []), severity=row.severity,
        expression=row.expression, source_ref=row.source_ref or "",
        status=RuleStatus(row.status),
    )


def _result_from_row(row: models.ReviewResultModel) -> ReviewResult:
    from contract_review.results import Recommendation, ResultStatus

    return ReviewResult(
        id=row.id, task_id=row.task_id, attachment_id=row.attachment_id,
        recommendation=Recommendation(row.recommendation), status=ResultStatus(row.status),
        risk_summary=row.risk_summary, review_comment=row.review_comment,
        required_roles=tuple(row.required_roles or []), confirmed_roles=set(row.confirmed_roles or []),
        created_by=row.created_by, confirmed_at=row.confirmed_at,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _version_from_row(row: models.ReviewVersionModel) -> ReviewVersion:
    from contract_review.results import Recommendation, ResultStatus

    return ReviewVersion(
        id=row.id, task_id=row.task_id, attachment_id=row.attachment_id,
        version_no=row.version_no, recommendation=Recommendation(row.recommendation),
        result_status=ResultStatus(row.result_status), risk_summary=row.risk_summary,
        comment=row.comment, created_by=row.created_by, created_at=row.created_at,
    )
