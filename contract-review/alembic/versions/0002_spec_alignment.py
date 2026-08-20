"""Spec alignment: write_status + 2.4.9 fields.

Revision ID: 0002_spec_alignment
Revises: 0001_baseline
Create Date: 2026-08-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_spec_alignment"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("approval_tasks", sa.Column("write_status", sa.String(32), nullable=False, server_default="not_written"))
    op.add_column("approval_tasks", sa.Column("write_response_text", sa.Text, nullable=True))
    op.add_column("approval_tasks", sa.Column("approval_code", sa.String(128), nullable=True))
    op.add_column("approval_tasks", sa.Column("applicant_name", sa.String(128), nullable=True))
    op.add_column("approval_tasks", sa.Column("applicant_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("approval_tasks", sa.Column("attachment_count", sa.Integer, nullable=False, server_default="0"))
    op.execute("UPDATE approval_tasks SET approval_code = external_task_key WHERE approval_code IS NULL")
    op.execute("UPDATE approval_tasks SET applicant_name = applicant_id WHERE applicant_name IS NULL")
    op.add_column("contract_parses", sa.Column("task_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("approval_tasks.id"), nullable=True))
    op.add_column("contract_parses", sa.Column("parse_status", sa.String(32), nullable=True))
    op.add_column("contract_parses", sa.Column("parse_error", sa.Text, nullable=True))
    op.add_column("contract_parses", sa.Column("basic_info_json", postgresql.JSONB, nullable=True))
    op.add_column("contract_parses", sa.Column("clause_info_json", postgresql.JSONB, nullable=True))
    op.add_column("contract_parses", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.execute("UPDATE contract_parses SET parse_status = status WHERE parse_status IS NULL")
    op.execute("UPDATE contract_parses SET parse_error = error_message WHERE parse_error IS NULL")
    op.add_column("rule_hits", sa.Column("task_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("approval_tasks.id"), nullable=True))
    op.add_column("rule_hits", sa.Column("evidence_text", sa.Text, nullable=True))
    op.add_column("rule_hits", sa.Column("evidence_position", sa.String(255), nullable=True))
    op.add_column("rule_hits", sa.Column("hit_status", sa.String(32), nullable=True))
    op.execute("UPDATE rule_hits SET evidence_text = message WHERE evidence_text IS NULL")
    op.execute("UPDATE rule_hits SET hit_status = result WHERE hit_status IS NULL")
    op.add_column("review_results", sa.Column("overall_risk_level", sa.String(16), nullable=True))
    op.add_column("review_results", sa.Column("summary_text", sa.Text, nullable=True))
    op.add_column("review_results", sa.Column("focus_points_json", postgresql.JSONB, nullable=True))
    op.add_column("review_results", sa.Column("comment_text", sa.Text, nullable=True))
    op.alter_column("comment_logs", "result_id", existing_type=postgresql.UUID(as_uuid=False), nullable=True)
    op.add_column("comment_logs", sa.Column("write_status", sa.String(32), nullable=True))
    op.add_column("comment_logs", sa.Column("write_response_text", sa.Text, nullable=True))
    op.add_column("task_logs", sa.Column("log_level", sa.String(16), nullable=True))
    op.add_column("task_logs", sa.Column("log_type", sa.String(32), nullable=True))
    op.add_column("task_logs", sa.Column("log_content", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("task_logs", "log_content")
    op.drop_column("task_logs", "log_type")
    op.drop_column("task_logs", "log_level")
    op.drop_column("comment_logs", "write_response_text")
    op.drop_column("comment_logs", "write_status")
    op.alter_column("comment_logs", "result_id", existing_type=postgresql.UUID(as_uuid=False), nullable=False)
    op.drop_column("review_results", "comment_text")
    op.drop_column("review_results", "focus_points_json")
    op.drop_column("review_results", "summary_text")
    op.drop_column("review_results", "overall_risk_level")
    op.drop_column("rule_hits", "hit_status")
    op.drop_column("rule_hits", "evidence_position")
    op.drop_column("rule_hits", "evidence_text")
    op.drop_column("rule_hits", "task_id")
    op.drop_column("contract_parses", "created_at")
    op.drop_column("contract_parses", "clause_info_json")
    op.drop_column("contract_parses", "basic_info_json")
    op.drop_column("contract_parses", "parse_error")
    op.drop_column("contract_parses", "parse_status")
    op.drop_column("contract_parses", "task_id")
    op.drop_column("approval_tasks", "attachment_count")
    op.drop_column("approval_tasks", "applicant_time")
    op.drop_column("approval_tasks", "applicant_name")
    op.drop_column("approval_tasks", "approval_code")
    op.drop_column("approval_tasks", "write_response_text")
    op.drop_column("approval_tasks", "write_status")
