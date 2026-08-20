"""Baseline: create all core tables.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # approval_tasks
    op.create_table(
        "approval_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("external_task_key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("contract_type", sa.String(32), nullable=True),
        sa.Column("applicant_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="imported"),
        sa.Column("recommendation_status", sa.String(32), nullable=True),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("blocked_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("external_task_key", name="uq_task_external_key"),
    )
    op.create_index("idx_tasks_status_updated", "approval_tasks", ["status", "updated_at"])
    op.create_index("idx_tasks_applicant", "approval_tasks", ["applicant_id"])

    # approval_attachments
    op.create_table(
        "approval_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_tasks.id"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("quality_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("uploaded_by", sa.String(128), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_attachment_task_version", "approval_attachments", ["task_id", "version_no"])
    op.create_unique_constraint("uq_attachment_task_hash", "approval_attachments", ["task_id", "file_sha256"])
    op.create_index("idx_attachment_task_current", "approval_attachments", ["task_id", "is_current"])

    # contract_parses
    op.create_table(
        "contract_parses",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_attachments.id"), nullable=False, unique=True),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("extracted_payload", postgresql.JSONB, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_parse_status_finished", "contract_parses", ["status", "finished_at"])

    # review_rules
    op.create_table(
        "review_rules",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("rule_code", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contract_types", postgresql.JSONB, nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("expression", postgresql.JSONB, nullable=True),
        sa.Column("source_ref", sa.String(512), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(128), nullable=True),
    )
    op.create_unique_constraint("uq_rule_code_version", "review_rules", ["rule_code", "version"])

    # rule_hits
    op.create_table(
        "rule_hits",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("parse_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("contract_parses.id"), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("review_rules.id"), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("evidence", postgresql.JSONB, nullable=True),
        sa.Column("suggested_action", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # review_results
    op.create_table(
        "review_results",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_tasks.id"), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_attachments.id"), nullable=False),
        sa.Column("recommendation", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("risk_summary", postgresql.JSONB, nullable=True),
        sa.Column("review_comment", sa.Text, nullable=True),
        sa.Column("required_roles", postgresql.JSONB, nullable=True),
        sa.Column("confirmed_roles", postgresql.JSONB, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_result_task", "review_results", ["task_id"])

    # comment_logs
    op.create_table(
        "comment_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_tasks.id"), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("review_results.id"), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("before_status", sa.String(32), nullable=True),
        sa.Column("after_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_comment_task_created", "comment_logs", ["task_id", "created_at"])
    op.create_index("idx_comment_result", "comment_logs", ["result_id", "created_at"])

    # task_logs
    op.create_table(
        "task_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_tasks.id"), nullable=True),
        sa.Column("actor_id", sa.String(128), nullable=False, server_default="system"),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("before_state", postgresql.JSONB, nullable=True),
        sa.Column("after_state", postgresql.JSONB, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=False, server_default="req_local"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_log_task_created", "task_logs", ["task_id", "created_at"])

    # review_versions
    op.create_table(
        "review_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_tasks.id"), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("approval_attachments.id"), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("review_results.id"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("recommendation", sa.String(32), nullable=False),
        sa.Column("result_status", sa.String(32), nullable=False),
        sa.Column("risk_summary", postgresql.JSONB, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_version_task_no", "review_versions", ["task_id", "version_no"])
    op.create_index("idx_version_task", "review_versions", ["task_id"])

    # users (for Phase 3 auth, created now so the baseline is complete)
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="business_reviewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_user_username", "users", ["username"])


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("review_versions")
    op.drop_table("task_logs")
    op.drop_table("comment_logs")
    op.drop_table("review_results")
    op.drop_table("rule_hits")
    op.drop_table("review_rules")
    op.drop_table("contract_parses")
    op.drop_table("approval_attachments")
    op.drop_table("approval_tasks")
