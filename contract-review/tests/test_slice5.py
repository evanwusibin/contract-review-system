from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contract_review.domain import ApprovalAttachment, ApprovalTask, InMemoryReviewStore, QualityStatus, TaskStatus
from contract_review.results import ConfirmationError, Recommendation, ResultStatus, ReviewResultService
from contract_review.rules import RuleHit, RuleHitResult


def context():
    now = datetime.now(timezone.utc)
    task = ApprovalTask(uuid4(), "task-005", "合同", "user-redacted", TaskStatus.REVIEWING, None, now, now)
    attachment = ApprovalAttachment(uuid4(), task.id, 0, "contract.pdf", "application/pdf", "key", "a" * 64, 1, QualityStatus.USABLE, "user-redacted", now)
    return task, attachment


def hit(result=RuleHitResult.HIT, severity="high"):
    return RuleHit(uuid4(), uuid4(), uuid4(), result, severity, "主体缺失", None, "补充主体", datetime.now(timezone.utc))


def test_high_risk_recommendation_requires_all_business_roles_before_confirmation():
    task, attachment = context()
    service = ReviewResultService(InMemoryReviewStore())
    review = service.create_recommendation(task, attachment, [hit()], "system")

    assert review.recommendation is Recommendation.REJECT
    assert review.status is ResultStatus.PENDING_CONFIRMATION
    assert review.required_roles == ("business", "legal", "warranty")
    assert task.status is TaskStatus.AWAITING_CONFIRMATION

    service.confirm_role(review, task, "business", "u-business", "业务确认", "req-b")
    with pytest.raises(ConfirmationError, match="缺少会签角色"):
        service.finalize(review, task, "u-business")
    assert review.status is ResultStatus.PENDING_CONFIRMATION


def test_all_required_roles_can_finalize_confirmed_result():
    task, attachment = context()
    service = ReviewResultService(InMemoryReviewStore())
    review = service.create_recommendation(task, attachment, [hit()], "system")

    for role in review.required_roles:
        service.confirm_role(review, task, role, f"u-{role}", f"{role}确认")
    service.finalize(review, task, "admin")

    assert review.status is ResultStatus.CONFIRMED
    assert task.status is TaskStatus.CONFIRMED
    assert review.confirmed_roles == {"business", "legal", "warranty"}


def test_role_outside_responsibility_domain_cannot_confirm():
    task, attachment = context()
    service = ReviewResultService(InMemoryReviewStore())
    review = service.create_recommendation(task, attachment, [hit()], "system")

    with pytest.raises(ConfirmationError, match="责任域"):
        service.confirm_role(review, task, "finance", "u-finance", "确认")


def test_request_evidence_returns_to_reviewing_and_preserves_comment_log():
    task, attachment = context()
    store = InMemoryReviewStore()
    service = ReviewResultService(store)
    review = service.create_recommendation(task, attachment, [hit()], "system")

    service.return_for_review(review, task, "u-legal", "legal", "request_evidence", "请补充盖章页")

    assert review.status is ResultStatus.RETURNED
    assert task.status is TaskStatus.REVIEWING
    assert service.comments[-1].action == "request_evidence"
    assert service.comments[-1].comment == "请补充盖章页"
