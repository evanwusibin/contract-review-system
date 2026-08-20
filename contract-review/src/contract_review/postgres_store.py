"""PostgreSQL-backed implementation of the ReviewStore interface.

Used when STORAGE_BACKEND=postgres and DATABASE_URL points to PostgreSQL.
Mirrors InMemoryReviewStore's method surface so the services and workflow
are identical regardless of backend. Uses synchronous psycopg sessions;
opened per operation for simplicity and correctness.
"""

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from sqlalchemy import and_, desc, select

from contract_review.database import get_sync_session_factory
from contract_review.db import (
    ApprovalAttachment as ApprovalAttachmentORM,
    ApprovalTask as ApprovalTaskORM,
    CommentLog as CommentLogORM,
    ContractParse as ContractParseORM,
    ReviewResult as ReviewResultORM,
    ReviewVersion as ReviewVersionORM,
    RuleHit as RuleHitORM,
    TaskLog as TaskLogORM,
)
from contract_review.domain import (
    ApprovalAttachment,
    ApprovalTask,
    InMemoryReviewStore,
    TaskLog,
)
from contract_review.parser import ContractParse
from contract_review.results import CommentLog, ReviewResult
from contract_review.rules import RuleHit
from contract_review.mappers import (
    attachment_to_domain,
    attachment_to_orm,
    comment_to_domain,
    comment_to_orm,
    log_to_domain,
    log_to_orm,
    parse_to_domain,
    parse_to_orm,
    result_to_domain,
    result_to_orm,
    rule_hit_to_domain,
    rule_hit_to_orm,
    task_to_domain,
    task_to_orm,
    version_to_domain,
    version_to_orm,
)
from contract_review.versions import ReviewVersion


class PostgresReviewStore(InMemoryReviewStore):
    """Subclass only for structural typing; all state lives in PostgreSQL.

    The in-memory dicts from InMemoryReviewStore are never used here — every
    method queries the database. Keeping the subclass relationship documents
    that both satisfy the same contract.
    """

    def __init__(self) -> None:
        super().__init__()
        self._session_factory = get_sync_session_factory()

    @contextmanager
    def _session(self) -> Iterator:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ── tasks ────────────────────────────────────────────────
    def find_task(self, external_task_key: str) -> ApprovalTask | None:
        with self._session() as s:
            orm = s.execute(
                select(ApprovalTaskORM).where(ApprovalTaskORM.external_task_key == external_task_key)
            ).scalar_one_or_none()
            return task_to_domain(orm) if orm else None

    def get_task(self, task_id: UUID) -> ApprovalTask | None:
        with self._session() as s:
            orm = s.get(ApprovalTaskORM, str(task_id))
            return task_to_domain(orm) if orm else None

    def list_tasks(self) -> list[ApprovalTask]:
        with self._session() as s:
            rows = s.execute(
                select(ApprovalTaskORM).order_by(desc(ApprovalTaskORM.updated_at))
            ).scalars().all()
            return [task_to_domain(r) for r in rows]

    def save_task(self, task: ApprovalTask) -> None:
        with self._session() as s:
            s.merge(task_to_orm(task))

    # ── attachments ──────────────────────────────────────────
    def find_attachment(self, task_id: UUID, file_hash: str) -> ApprovalAttachment | None:
        with self._session() as s:
            orm = s.execute(
                select(ApprovalAttachmentORM).where(
                    and_(ApprovalAttachmentORM.task_id == str(task_id), ApprovalAttachmentORM.file_sha256 == file_hash)
                )
            ).scalar_one_or_none()
            return attachment_to_domain(orm) if orm else None

    def get_attachment(self, attachment_id: UUID) -> ApprovalAttachment | None:
        with self._session() as s:
            orm = s.get(ApprovalAttachmentORM, str(attachment_id))
            return attachment_to_domain(orm) if orm else None

    def save_attachment(self, attachment: ApprovalAttachment) -> None:
        with self._session() as s:
            s.merge(attachment_to_orm(attachment))

    def list_attachments(self, task_id: UUID) -> list[ApprovalAttachment]:
        with self._session() as s:
            rows = s.execute(
                select(ApprovalAttachmentORM).where(ApprovalAttachmentORM.task_id == str(task_id))
            ).scalars().all()
            return [attachment_to_domain(r) for r in rows]

    def next_version(self, task_id: UUID) -> int:
        with self._session() as s:
            current = s.execute(
                select(ApprovalAttachmentORM.version_no).where(
                    ApprovalAttachmentORM.task_id == str(task_id)
                )
            ).scalars().all()
            return (max(current) + 1) if current else 1

    # ── logs ─────────────────────────────────────────────────
    def append_log(self, log: TaskLog) -> None:
        with self._session() as s:
            s.add(log_to_orm(log))

    def list_logs(self, limit: int = 50, offset: int = 0) -> list[TaskLog]:
        with self._session() as s:
            rows = s.execute(
                select(TaskLogORM).order_by(TaskLogORM.created_at).limit(limit).offset(offset)
            ).scalars().all()
            return [log_to_domain(r) for r in rows]

    def list_logs_for_task(self, task_id: UUID) -> list[TaskLog]:
        with self._session() as s:
            rows = s.execute(
                select(TaskLogORM).where(TaskLogORM.task_id == str(task_id)).order_by(TaskLogORM.created_at)
            ).scalars().all()
            return [log_to_domain(r) for r in rows]

    # ── results ──────────────────────────────────────────────
    def save_result(self, result: ReviewResult) -> None:
        with self._session() as s:
            s.merge(result_to_orm(result))

    def get_result(self, result_id: UUID) -> ReviewResult | None:
        with self._session() as s:
            orm = s.get(ReviewResultORM, str(result_id))
            return result_to_domain(orm) if orm else None

    def list_results(self, task_id: UUID) -> list[ReviewResult]:
        with self._session() as s:
            rows = s.execute(
                select(ReviewResultORM).where(ReviewResultORM.task_id == str(task_id)).order_by(ReviewResultORM.created_at)
            ).scalars().all()
            return [result_to_domain(r) for r in rows]

    def find_confirmed_result(self, task_id: UUID) -> ReviewResult | None:
        with self._session() as s:
            rows = s.execute(
                select(ReviewResultORM)
                .where(and_(ReviewResultORM.task_id == str(task_id), ReviewResultORM.status == "confirmed"))
                .order_by(ReviewResultORM.created_at)
            ).scalars().all()
            return result_to_domain(rows[-1]) if rows else None

    # ── comments ─────────────────────────────────────────────
    def save_comment(self, comment: CommentLog) -> None:
        with self._session() as s:
            s.add(comment_to_orm(comment))

    def list_comments(self) -> list[CommentLog]:
        with self._session() as s:
            rows = s.execute(select(CommentLogORM).order_by(CommentLogORM.created_at)).scalars().all()
            return [comment_to_domain(r) for r in rows]

    def list_comments_for_task(self, task_id: UUID) -> list[CommentLog]:
        with self._session() as s:
            rows = s.execute(
                select(CommentLogORM).where(CommentLogORM.task_id == str(task_id)).order_by(CommentLogORM.created_at)
            ).scalars().all()
            return [comment_to_domain(r) for r in rows]

    # ── versions ─────────────────────────────────────────────
    def save_version(self, version: ReviewVersion) -> None:
        with self._session() as s:
            s.merge(version_to_orm(version))

    def get_version(self, version_id: UUID) -> ReviewVersion | None:
        with self._session() as s:
            orm = s.get(ReviewVersionORM, str(version_id))
            return version_to_domain(orm) if orm else None

    def list_versions(self, task_id: UUID) -> list[ReviewVersion]:
        with self._session() as s:
            rows = s.execute(
                select(ReviewVersionORM)
                .where(ReviewVersionORM.task_id == str(task_id))
                .order_by(ReviewVersionORM.version_no)
            ).scalars().all()
            return [version_to_domain(r) for r in rows]

    # ── parses ───────────────────────────────────────────────
    def save_parse(self, parse: ContractParse) -> None:
        with self._session() as s:
            s.merge(parse_to_orm(parse))

    def get_parse(self, parse_id: UUID) -> ContractParse | None:
        with self._session() as s:
            orm = s.get(ContractParseORM, str(parse_id))
            return parse_to_domain(orm) if orm else None

    def get_parse_for_task(self, task_id: UUID) -> ContractParse | None:
        with self._session() as s:
            attachment_ids = s.execute(
                select(ApprovalAttachmentORM.id).where(ApprovalAttachmentORM.task_id == str(task_id))
            ).scalars().all()
            if not attachment_ids:
                return None
            orm = s.execute(
                select(ContractParseORM)
                .where(ContractParseORM.attachment_id.in_(str(a) for a in attachment_ids))
                .order_by(desc(ContractParseORM.created_at))
            ).scalars().first()
            return parse_to_domain(orm) if orm else None

    # ── rule hits ────────────────────────────────────────────
    def save_rule_hit(self, hit: RuleHit) -> None:
        with self._session() as s:
            s.add(rule_hit_to_orm(hit))

    def list_rule_hits(self, parse_id: UUID) -> list[RuleHit]:
        with self._session() as s:
            rows = s.execute(
                select(RuleHitORM).where(RuleHitORM.parse_id == str(parse_id)).order_by(RuleHitORM.created_at)
            ).scalars().all()
            return [rule_hit_to_domain(r) for r in rows]
