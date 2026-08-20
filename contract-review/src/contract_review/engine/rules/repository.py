"""Review rule persistence against the review_rules table (Phase 4).

Rules are read from the database when the PostgreSQL backend is enabled, replacing
the hardcoded factories for production. The three default rules are seeded with
stable IDs (idempotent), so rule_hits.rule_id references a real, traceable rule.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID, uuid4

from sqlalchemy import select

from contract_review.infrastructure.persistence.database import get_sync_session_factory
from contract_review.infrastructure.persistence.models import ReviewRule as ReviewRuleORM
from contract_review.infrastructure.persistence.mappers import rule_to_domain, rule_to_orm
from contract_review.engine.rules.engine import (
    RuleDefinition,
    RuleStatus,
    party_completeness_rule,
    party_completeness_rule_v2,
    warranty_clause_rule,
)


class RuleRepository:
    """Sync access to the review_rules table (mirrors PostgresReviewStore pattern)."""

    def __init__(self) -> None:
        self._factory = get_sync_session_factory()

    @contextmanager
    def _session(self) -> Iterator:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_published(self) -> list[RuleDefinition]:
        with self._session() as s:
            rows = s.execute(
                select(ReviewRuleORM)
                .where(ReviewRuleORM.status == RuleStatus.PUBLISHED.value)
                .order_by(ReviewRuleORM.rule_code)
            ).scalars().all()
            return [rule_to_domain(r) for r in rows]

    def list_all(self) -> list[RuleDefinition]:
        with self._session() as s:
            rows = s.execute(select(ReviewRuleORM).order_by(ReviewRuleORM.rule_code)).scalars().all()
            return [rule_to_domain(r) for r in rows]

    def get_by_code(self, rule_code: str, version: str = "1.0") -> RuleDefinition | None:
        with self._session() as s:
            row = s.execute(
                select(ReviewRuleORM).where(
                    ReviewRuleORM.rule_code == rule_code, ReviewRuleORM.version == version
                )
            ).scalar_one_or_none()
            return rule_to_domain(row) if row else None

    def create_rule(self, rule_code: str, name: str, severity: str) -> RuleDefinition:
        now = datetime.now(timezone.utc)
        rule = RuleDefinition(
            id=uuid4(),
            rule_code=rule_code,
            version="1.0",
            name=name,
            contract_types=(),
            severity=severity,
            expression={"op": "field_status", "field": rule_code, "equals": "missing"},
            source_ref="",
            status=RuleStatus.DRAFT,
        )
        with self._session() as s:
            s.merge(rule_to_orm(rule))
        return rule

    def set_status(self, rule_id: UUID, status: str, approved_by: str | None = None) -> RuleDefinition | None:
        with self._session() as s:
            row = s.get(ReviewRuleORM, str(rule_id))
            if row is None:
                return None
            row.status = status
            if status == RuleStatus.PUBLISHED.value:
                row.effective_from = datetime.now(timezone.utc)
                row.approved_by = approved_by
            elif status == RuleStatus.RETIRED.value:
                row.effective_to = datetime.now(timezone.utc)
            return rule_to_domain(row)

    def ensure_seed_rules(self) -> None:
        """Idempotent bootstrap of the three default published rules."""
        seeds = (party_completeness_rule(), party_completeness_rule_v2(), warranty_clause_rule())
        with self._session() as s:
            for rule in seeds:
                exists = s.execute(
                    select(ReviewRuleORM.id).where(
                        ReviewRuleORM.rule_code == rule.rule_code,
                        ReviewRuleORM.version == rule.version,
                    )
                ).scalar_one_or_none()
                if exists is None:
                    s.add(rule_to_orm(rule))
