from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from contract_review.domain import ApprovalAttachment, ApprovalTask, InMemoryReviewStore, TaskLog, TaskStatus
from contract_review.engine.rules.engine import RuleHit, RuleHitResult


class Recommendation(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


class ResultStatus(StrEnum):
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    RETURNED = "returned"


@dataclass
class ReviewResult:
    id: UUID
    task_id: UUID
    attachment_id: UUID
    recommendation: Recommendation
    status: ResultStatus
    risk_summary: dict[str, int]
    review_comment: str | None
    required_roles: tuple[str, ...]
    confirmed_roles: set[str]
    created_by: str
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CommentLog:
    id: UUID
    task_id: UUID
    result_id: UUID
    actor_id: str
    role: str
    action: str
    comment: str
    before_status: ResultStatus
    after_status: ResultStatus
    created_at: datetime


class ConfirmationError(ValueError):
    pass


class ReviewResultService:
    REQUIRED_ROLES = ("business", "legal", "warranty")

    def __init__(self, store: InMemoryReviewStore) -> None:
        self.store = store

    @property
    def comments(self) -> list[CommentLog]:
        """Read-only view of all comments (backed by the store)."""
        return self.store.list_comments()

    def create_recommendation(
        self,
        task: ApprovalTask,
        attachment: ApprovalAttachment,
        hits: list[RuleHit],
        created_by: str,
        request_id: str = "req_local",
    ) -> ReviewResult:
        high_hits = [hit for hit in hits if hit.result is RuleHitResult.HIT and hit.severity == "high"]
        insufficient = [hit for hit in hits if hit.result is RuleHitResult.INSUFFICIENT_EVIDENCE]
        if high_hits:
            recommendation = Recommendation.REJECT
            roles = self.REQUIRED_ROLES
        elif insufficient:
            recommendation = Recommendation.MANUAL_REVIEW
            roles = self.REQUIRED_ROLES
        else:
            recommendation = Recommendation.PASS
            roles = ("business",)

        now = datetime.now(timezone.utc)
        result = ReviewResult(
            id=uuid4(), task_id=task.id, attachment_id=attachment.id,
            recommendation=recommendation, status=ResultStatus.PENDING_CONFIRMATION,
            risk_summary=self._risk_summary(hits), review_comment=None,
            required_roles=roles, confirmed_roles=set(), created_by=created_by,
            confirmed_at=None, created_at=now, updated_at=now,
        )
        task.status = TaskStatus.AWAITING_CONFIRMATION
        task.updated_at = now
        self.store.save_result(result)
        self.store.save_task(task)
        self.store.append_log(self._task_log(task, "recommendation_created", request_id, now, {"recommendation": recommendation.value, "status": result.status.value}))
        return result

    def confirm_role(self, result: ReviewResult, task: ApprovalTask, role: str, actor_id: str, comment: str, request_id: str = "req_local") -> ReviewResult:
        if result.status is not ResultStatus.PENDING_CONFIRMATION:
            raise ConfirmationError("结果不在待确认状态")
        if role not in result.required_roles:
            raise ConfirmationError("角色不在当前会签责任域")
        if not actor_id or not comment.strip():
            raise ConfirmationError("确认人和意见不能为空")
        before = result.status
        result.confirmed_roles.add(role)
        result.updated_at = datetime.now(timezone.utc)
        task.status = TaskStatus.CONFIRMING
        self._append_comment(result, task, actor_id, role, "confirm", comment, before, result.status, request_id)
        self.store.save_result(result)
        self.store.save_task(task)
        return result

    def finalize(self, result: ReviewResult, task: ApprovalTask, actor_id: str, request_id: str = "req_local") -> ReviewResult:
        missing = set(result.required_roles) - result.confirmed_roles
        if missing:
            self.store.append_log(self._task_log(task, "confirmation_rejected", request_id, datetime.now(timezone.utc), {"missing_roles": ",".join(sorted(missing))}))
            raise ConfirmationError(f"缺少会签角色：{','.join(sorted(missing))}")
        if result.status is not ResultStatus.PENDING_CONFIRMATION:
            raise ConfirmationError("结果不在待确认状态")
        now = datetime.now(timezone.utc)
        result.status = ResultStatus.CONFIRMED
        result.confirmed_at = now
        result.updated_at = now
        task.status = TaskStatus.CONFIRMED
        self.store.append_log(self._task_log(task, "result_confirmed", request_id, now, {"actor_id": actor_id, "status": result.status.value}))
        self.store.save_result(result)
        self.store.save_task(task)
        return result

    def return_for_review(self, result: ReviewResult, task: ApprovalTask, actor_id: str, role: str, action: str, comment: str, request_id: str = "req_local") -> ReviewResult:
        if action not in {"reject", "request_evidence"}:
            raise ConfirmationError("不支持的回退动作")
        if role not in result.required_roles:
            raise ConfirmationError("角色不在当前会签责任域")
        before = result.status
        result.status = ResultStatus.REJECTED if action == "reject" else ResultStatus.RETURNED
        result.updated_at = datetime.now(timezone.utc)
        task.status = TaskStatus.REVIEWING
        self._append_comment(result, task, actor_id, role, action, comment, before, result.status, request_id)
        self.store.save_result(result)
        self.store.save_task(task)
        return result

    @staticmethod
    def _risk_summary(hits: list[RuleHit]) -> dict[str, int]:
        return {severity: sum(hit.result is RuleHitResult.HIT and hit.severity == severity for hit in hits) for severity in ("high", "medium", "low")}

    def _append_comment(self, result, task, actor_id, role, action, comment, before, after, request_id):
        now = datetime.now(timezone.utc)
        self.store.save_comment(CommentLog(uuid4(), task.id, result.id, actor_id, role, action, comment, before, after, now))
        self.store.append_log(self._task_log(task, f"comment_{action}", request_id, now, {"role": role, "result_status": after.value}))

    @staticmethod
    def _task_log(task: ApprovalTask, action: str, request_id: str, now: datetime, after: dict[str, str]) -> TaskLog:
        return TaskLog(task.id, "system", action, "review_result", str(task.id), {}, after, request_id, now)
