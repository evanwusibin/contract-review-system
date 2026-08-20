"""SQLAlchemy 2 ORM models for the 8 core tables + review_versions.

Maps the data model defined in 02_数据模型与黄金数据集.md.
All JSONB columns store脱敏 data only — no contract full text, passwords, or keys.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalTask(Base):
    __tablename__ = "approval_tasks"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    external_task_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applicant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="imported")
    write_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_written")
    write_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_version_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attachments: Mapped[list["ApprovalAttachment"]] = relationship(back_populates="task")

    __table_args__ = (
        Index("idx_tasks_status_updated", "status", "updated_at"),
        Index("idx_tasks_applicant", "applicant_id"),
    )


class ApprovalAttachment(Base):
    __tablename__ = "approval_attachments"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["ApprovalTask"] = relationship(back_populates="attachments")
    parses: Mapped[list["ContractParse"]] = relationship(back_populates="attachment")

    __table_args__ = (
        UniqueConstraint("task_id", "version_no", name="uq_attachment_task_version"),
        UniqueConstraint("task_id", "file_sha256", name="uq_attachment_task_hash"),
        Index("idx_attachment_task_current", "task_id", "is_current"),
    )


class ContractParse(Base):
    __tablename__ = "contract_parses"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=True)
    attachment_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_attachments.id"), nullable=False, unique=True
    )
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    parse_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    basic_info_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    clause_info_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attachment: Mapped["ApprovalAttachment"] = relationship(back_populates="parses")
    rule_hits: Mapped[list["RuleHit"]] = relationship(back_populates="parse")

    __table_args__ = (
        Index("idx_parse_status_finished", "status", "finished_at"),
    )


class ReviewRule(Base):
    __tablename__ = "review_rules"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_types: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    expression: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    hits: Mapped[list["RuleHit"]] = relationship(back_populates="rule")

    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_rule_code_version"),
    )


class RuleHit(Base):
    __tablename__ = "rule_hits"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    parse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("contract_parses.id"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("review_rules.id"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    hit_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    parse: Mapped["ContractParse"] = relationship(back_populates="rule_hits")
    rule: Mapped["ReviewRule"] = relationship(back_populates="hits")


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=False
    )
    attachment_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_attachments.id"), nullable=False
    )
    overall_risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    risk_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus_points_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    comment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_roles: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confirmed_roles: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    comments: Mapped[list["CommentLog"]] = relationship(back_populates="result")
    versions: Mapped[list["ReviewVersion"]] = relationship(back_populates="result")

    __table_args__ = (
        Index("idx_result_task", "task_id"),
    )


class CommentLog(Base):
    __tablename__ = "comment_logs"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=False
    )
    result_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("review_results.id"), nullable=True
    )
    write_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    write_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    before_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    result: Mapped["ReviewResult"] = relationship(back_populates="comments")

    __table_args__ = (
        Index("idx_comment_task_created", "task_id", "created_at"),
        Index("idx_comment_result", "result_id", "created_at"),
    )


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=True
    )
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    log_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    log_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    log_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="req_local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_log_task_created", "task_id", "created_at"),
    )


class ReviewVersion(Base):
    """Confirmed review snapshot — append-only, never overwritten."""
    __tablename__ = "review_versions"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_tasks.id"), nullable=False
    )
    attachment_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("approval_attachments.id"), nullable=False
    )
    result_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("review_results.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    result_status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    result: Mapped["ReviewResult"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("task_id", "version_no", name="uq_version_task_no"),
        Index("idx_version_task", "task_id"),
    )


class User(Base):
    """User accounts for database-backed authentication (Phase 3)."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="business_reviewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
