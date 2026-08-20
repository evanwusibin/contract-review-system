from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from contract_review.infrastructure.database import Base


def _json_type() -> JSON:
    return JSON().with_variant(JSONB(), "postgresql")


class ApprovalTaskModel(Base):
    __tablename__ = "approval_tasks"
    __table_args__ = (Index("ix_approval_tasks_status_updated", "status", "updated_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    external_task_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    applicant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attachments: Mapped[list["ApprovalAttachmentModel"]] = relationship(back_populates="task")


class ApprovalAttachmentModel(Base):
    __tablename__ = "approval_attachments"
    __table_args__ = (
        UniqueConstraint("task_id", "version_no", name="uq_attachment_task_version"),
        UniqueConstraint("task_id", "file_sha256", name="uq_attachment_task_hash"),
        Index("ix_attachment_task_current", "task_id", "is_current"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped[ApprovalTaskModel] = relationship(back_populates="attachments")


class ContractParseModel(Base):
    __tablename__ = "contract_parses"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    attachment_id: Mapped[UUID] = mapped_column(
        ForeignKey("approval_attachments.id"), unique=True, nullable=False
    )
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)
    extracted_payload: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewRuleModel(Base):
    __tablename__ = "review_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_types: Mapped[list] = mapped_column(_json_type(), nullable=False, default=list)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    expression: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_rule_code_version"),
        Index("ix_rule_code_status", "rule_code", "status"),
    )


class RuleHitModel(Base):
    __tablename__ = "rule_hits"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    parse_id: Mapped[UUID] = mapped_column(ForeignKey("contract_parses.id"), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("review_rules.id"), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence: Mapped[dict | None] = mapped_column(_json_type(), nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewResultModel(Base):
    __tablename__ = "review_results"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False)
    attachment_id: Mapped[UUID] = mapped_column(ForeignKey("approval_attachments.id"), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_summary: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_roles: Mapped[list] = mapped_column(_json_type(), nullable=False, default=list)
    confirmed_roles: Mapped[list] = mapped_column(_json_type(), nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewVersionModel(Base):
    __tablename__ = "review_versions"
    __table_args__ = (Index("ix_version_task", "task_id", "version_no"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False)
    attachment_id: Mapped[UUID] = mapped_column(ForeignKey("approval_attachments.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    result_status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_summary: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommentLogModel(Base):
    __tablename__ = "comment_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("approval_tasks.id"), nullable=False)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("review_results.id"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    before_status: Mapped[str] = mapped_column(String(32), nullable=False)
    after_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_comment_task_created", "task_id", "created_at"),
        Index("ix_comment_result", "result_id"),
    )


class TaskLogModel(Base):
    __tablename__ = "task_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("approval_tasks.id"), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_state: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    after_state: Mapped[dict] = mapped_column(_json_type(), nullable=False, default=dict)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_task_logs_created", "created_at"),)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
