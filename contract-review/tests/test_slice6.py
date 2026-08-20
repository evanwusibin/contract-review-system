from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contract_review.domain import ApprovalTask, InMemoryReviewStore, TaskStatus
from contract_review.engine.workflow.results import Recommendation, ResultStatus, ReviewResult
from contract_review.engine.workflow.versions import ReviewVersionService, VersionSaveError


def task() -> ApprovalTask:
    now = datetime.now(timezone.utc)
    return ApprovalTask(uuid4(), "task-006", "合同", "user-redacted", TaskStatus.CONFIRMED, None, now, now)


def result(task_id, status=ResultStatus.CONFIRMED, comment="初始意见") -> ReviewResult:
    now = datetime.now(timezone.utc)
    return ReviewResult(uuid4(), task_id, uuid4(), Recommendation.REJECT, status, {"high": 1, "medium": 0, "low": 0}, comment, ("business", "legal", "warranty"), {"business", "legal", "warranty"}, "system", now, now, now)


def test_save_appends_review_versions_without_overwriting_history():
    current_task = task()
    review = result(current_task.id)
    service = ReviewVersionService(InMemoryReviewStore())

    first = service.save(current_task, review, "admin", "req-v1")
    review.review_comment = "修订后的意见"
    second = service.save(current_task, review, "admin", "req-v2")

    assert (first.version_no, second.version_no) == (1, 2)
    assert first.comment == "初始意见"
    assert second.comment == "修订后的意见"
    assert service.list_versions(current_task.id) == (first, second)
    assert len(service.store.logs) == 2


def test_restore_only_changes_read_context_and_does_not_change_current_result():
    current_task = task()
    review = result(current_task.id)
    service = ReviewVersionService(InMemoryReviewStore())
    saved = service.save(current_task, review, "admin")

    context = service.restore_view(current_task, saved.id)

    assert context.version_id == saved.id
    assert context.version_no == 1
    assert context.read_only is True
    assert review.status is ResultStatus.CONFIRMED
    assert current_task.status is TaskStatus.CONFIRMED


def test_failed_save_does_not_create_partial_version():
    current_task = task()
    service = ReviewVersionService(InMemoryReviewStore())

    with pytest.raises(VersionSaveError, match="已确认"):
        service.save(current_task, result(current_task.id, ResultStatus.PENDING_CONFIRMATION), "admin")

    assert service.list_versions(current_task.id) == ()
    assert service.store.logs == []


def test_cannot_restore_another_tasks_version():
    current_task = task()
    other_task = task()
    service = ReviewVersionService(InMemoryReviewStore())
    saved = service.save(other_task, result(other_task.id), "admin")

    with pytest.raises(VersionSaveError, match="不属于当前任务"):
        service.restore_view(current_task, saved.id)
