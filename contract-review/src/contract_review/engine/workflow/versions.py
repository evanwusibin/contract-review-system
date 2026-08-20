from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contract_review.domain import ApprovalTask, InMemoryReviewStore, TaskLog
from contract_review.engine.workflow.results import Recommendation, ResultStatus, ReviewResult


class VersionSaveError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewVersion:
    id: UUID
    task_id: UUID
    attachment_id: UUID
    result_id: UUID
    version_no: int
    recommendation: Recommendation
    result_status: ResultStatus
    risk_summary: dict[str, int]
    comment: str | None
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class VersionViewContext:
    task_id: UUID
    version_id: UUID
    version_no: int
    read_only: bool = True


class ReviewVersionService:
    """评审快照只追加；历史版本不可被恢复操作或新保存覆盖。"""

    def __init__(self, store: InMemoryReviewStore) -> None:
        self.store = store

    def save(self, task: ApprovalTask, result: ReviewResult, actor_id: str, request_id: str = "req_local") -> ReviewVersion:
        if result.task_id != task.id:
            raise VersionSaveError("评审结果不属于当前任务")
        if result.status is not ResultStatus.CONFIRMED:
            raise VersionSaveError("只有已确认结果可以保存版本")
        if not actor_id:
            raise VersionSaveError("保存人不能为空")

        version_no = self._next_version(task.id)
        now = datetime.now(timezone.utc)
        version = ReviewVersion(
            id=uuid4(), task_id=task.id, attachment_id=result.attachment_id,
            result_id=result.id, version_no=version_no, recommendation=result.recommendation,
            result_status=result.status, risk_summary=dict(result.risk_summary),
            comment=result.review_comment, created_by=actor_id, created_at=now,
        )
        self.store.save_version(version)
        self.store.append_log(TaskLog(task.id, actor_id, "review_version_saved", "review_version", str(version.id), {}, {"version_no": str(version_no)}, request_id, now))
        return version

    def list_versions(self, task_id: UUID) -> tuple[ReviewVersion, ...]:
        return tuple(self.store.list_versions(task_id))

    def get_version(self, version_id: UUID) -> ReviewVersion | None:
        return self.store.get_version(version_id)

    def restore_view(self, task: ApprovalTask, version_id: UUID) -> VersionViewContext:
        version = self.store.get_version(version_id)
        if version is None or version.task_id != task.id:
            raise VersionSaveError("历史版本不存在或不属于当前任务")
        return VersionViewContext(task.id, version.id, version.version_no)

    def _next_version(self, task_id: UUID) -> int:
        versions = self.list_versions(task_id)
        return (versions[-1].version_no + 1) if versions else 1
