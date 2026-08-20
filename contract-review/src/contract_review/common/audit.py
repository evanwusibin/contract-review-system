"""Audit trail queries (Phase 4).

Thin service over the review store's task-log access. Keeps the API layer free of
storage details and gives the audit surface a single, documented home. comment_logs
remain part of the review result lifecycle (results.py), while this module owns the
append-only task_logs audit trail.
"""

from __future__ import annotations

from uuid import UUID

from contract_review.domain import InMemoryReviewStore, TaskLog


class AuditService:
    def __init__(self, store: InMemoryReviewStore) -> None:
        self.store = store

    def list_events(self, limit: int = 50, offset: int = 0) -> list[TaskLog]:
        return self.store.list_logs(limit, offset)

    def list_for_task(self, task_id: UUID) -> list[TaskLog]:
        return self.store.list_logs_for_task(task_id)
