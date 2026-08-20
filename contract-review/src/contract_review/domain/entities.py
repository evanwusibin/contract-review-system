from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid4


class TaskStatus(StrEnum):
    # 2.4.4 规范状态
    PENDING = "pending"
    PARSING = "parsing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"
    DONE = "done"
    # 兼容历史状态
    IMPORTED = "imported"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    REJECTED_RECOMMENDATION = "rejected_recommendation"

    def to_spec(self) -> str:
        mapping = {
            self.PENDING: "pending",
            self.PARSING: "parsing",
            self.REVIEWING: "reviewing",
            self.BLOCKED: "blocked",
            self.DONE: "done",
            self.IMPORTED: "pending",
            self.AWAITING_CONFIRMATION: "reviewing",
            self.CONFIRMING: "reviewing",
            self.CONFIRMED: "done",
            self.REJECTED_RECOMMENDATION: "blocked",
        }
        return mapping.get(self, self.value)


class WriteStatus(StrEnum):
    NOT_WRITTEN = "not_written"
    WRITING = "writing"
    SUCCESS = "success"
    FAILED = "failed"


class QualityStatus(StrEnum):
    UNKNOWN = "unknown"
    USABLE = "usable"
    LOW_QUALITY = "low_quality"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class ImportRequest:
    external_task_key: str
    title: str
    applicant_id: str
    file_name: str
    mime_type: str
    content: bytes


@dataclass
class ApprovalTask:
    id: UUID
    external_task_key: str
    title: str
    applicant_id: str
    status: TaskStatus
    blocked_reason: str | None
    created_at: datetime
    updated_at: datetime
    write_status: WriteStatus = WriteStatus.NOT_WRITTEN
    approval_code: str | None = None

    def __post_init__(self) -> None:
        if self.approval_code is None:
            self.approval_code = self.external_task_key

    def can_retry(self) -> bool:
        return self.status == TaskStatus.BLOCKED

    def retry(self) -> None:
        if not self.can_retry():
            raise ValueError(f"仅 blocked 状态可重试，当前 {self.status}")
        self.status = TaskStatus.PARSING
        self.blocked_reason = None
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class ApprovalAttachment:
    id: UUID
    task_id: UUID
    version_no: int
    file_name: str
    mime_type: str
    storage_key: str
    file_sha256: str
    page_count: int
    quality_status: QualityStatus
    uploaded_by: str
    uploaded_at: datetime
    is_current: bool = True


@dataclass(frozen=True)
class TaskLog:
    task_id: UUID | None
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    before_state: dict[str, str | None]
    after_state: dict[str, str | None]
    request_id: str
    created_at: datetime


@dataclass(frozen=True)
class ImportResult:
    task: ApprovalTask
    attachment: ApprovalAttachment | None
    duplicate: bool
    error_code: str | None = None
    error_message: str | None = None


class InMemoryObjectStorage:
    """测试替身只保存对象，不把原始二进制混入业务记录。"""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, key: str, content: bytes) -> None:
        self._objects[key] = content

    def get(self, key: str) -> bytes:
        return self._objects[key]


class InMemoryReviewStore:
    """In-process store used for demo and tests. Also the interface contract
    that PostgresReviewStore implements for production persistence."""

    def __init__(self) -> None:
        self.tasks: dict[UUID, ApprovalTask] = {}
        self.attachments: dict[UUID, ApprovalAttachment] = {}
        self.logs: list[TaskLog] = []
        self.results: dict[UUID, ReviewResult] = {}
        self.comments: list[CommentLog] = []
        self.versions: dict[UUID, ReviewVersion] = {}
        self.parses: dict[UUID, ContractParse] = {}
        self.rule_hits: list[RuleHit] = []

    # ── tasks ────────────────────────────────────────────────
    def find_task(self, external_task_key: str) -> ApprovalTask | None:
        return next(
            (task for task in self.tasks.values() if task.external_task_key == external_task_key),
            None,
        )

    def get_task(self, task_id: UUID) -> ApprovalTask | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[ApprovalTask]:
        return list(self.tasks.values())

    def save_task(self, task: ApprovalTask) -> None:
        self.tasks[task.id] = task

    # ── attachments ──────────────────────────────────────────
    def find_attachment(self, task_id: UUID, file_hash: str) -> ApprovalAttachment | None:
        return next(
            (
                attachment
                for attachment in self.attachments.values()
                if attachment.task_id == task_id and attachment.file_sha256 == file_hash
            ),
            None,
        )

    def get_attachment(self, attachment_id: UUID) -> ApprovalAttachment | None:
        return self.attachments.get(attachment_id)

    def save_attachment(self, attachment: ApprovalAttachment) -> None:
        self.attachments[attachment.id] = attachment

    def list_attachments(self, task_id: UUID) -> list[ApprovalAttachment]:
        return [a for a in self.attachments.values() if a.task_id == task_id]

    def next_version(self, task_id: UUID) -> int:
        versions = [item.version_no for item in self.attachments.values() if item.task_id == task_id]
        return max(versions, default=-1) + 1

    # ── logs ─────────────────────────────────────────────────
    def append_log(self, log: TaskLog) -> None:
        self.logs.append(log)

    def list_logs(self, limit: int = 50, offset: int = 0) -> list[TaskLog]:
        return self.logs[offset:offset + limit]

    def list_logs_for_task(self, task_id: UUID) -> list[TaskLog]:
        return [log for log in self.logs if log.task_id == task_id]

    # ── results ──────────────────────────────────────────────
    def save_result(self, result: ReviewResult) -> None:
        self.results[result.id] = result

    def get_result(self, result_id: UUID) -> ReviewResult | None:
        return self.results.get(result_id)

    def list_results(self, task_id: UUID) -> list[ReviewResult]:
        return [r for r in self.results.values() if r.task_id == task_id]

    def find_confirmed_result(self, task_id: UUID) -> ReviewResult | None:
        confirmed = [r for r in self.results.values() if r.task_id == task_id and r.status.value == "confirmed"]
        return confirmed[-1] if confirmed else None

    # ── comments ─────────────────────────────────────────────
    def save_comment(self, comment: CommentLog) -> None:
        self.comments.append(comment)

    def list_comments(self) -> list[CommentLog]:
        return list(self.comments)

    def list_comments_for_task(self, task_id: UUID) -> list[CommentLog]:
        return [c for c in self.comments if c.task_id == task_id]

    # ── versions ─────────────────────────────────────────────
    def save_version(self, version: ReviewVersion) -> None:
        self.versions[version.id] = version

    def get_version(self, version_id: UUID) -> ReviewVersion | None:
        return self.versions.get(version_id)

    def list_versions(self, task_id: UUID) -> list[ReviewVersion]:
        return sorted(
            (v for v in self.versions.values() if v.task_id == task_id),
            key=lambda item: item.version_no,
        )

    # ── parses ───────────────────────────────────────────────
    def save_parse(self, parse: ContractParse) -> None:
        self.parses[parse.id] = parse

    def get_parse(self, parse_id: UUID) -> ContractParse | None:
        return self.parses.get(parse_id)

    def get_parse_for_task(self, task_id: UUID) -> ContractParse | None:
        attachment_ids = {a.id for a in self.attachments.values() if a.task_id == task_id}
        for parse in self.parses.values():
            if parse.attachment_id in attachment_ids:
                return parse
        return None

    # ── rule hits ────────────────────────────────────────────
    def save_rule_hit(self, hit: RuleHit) -> None:
        self.rule_hits.append(hit)

    def list_rule_hits(self, parse_id: UUID) -> list[RuleHit]:
        return [h for h in self.rule_hits if h.parse_id == parse_id]


class ImportErrorCode(StrEnum):
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    EMPTY_FILE = "EMPTY_FILE"
    INVALID_PDF = "INVALID_PDF"


class ContractImporter:
    def __init__(self, store: InMemoryReviewStore, objects: InMemoryObjectStorage) -> None:
        self.store = store
        self.objects = objects

    def import_contract(self, request: ImportRequest, request_id: str = "req_local") -> ImportResult:
        now = datetime.now(timezone.utc)
        existing_task = self.store.find_task(request.external_task_key)
        file_hash = sha256(request.content).hexdigest()

        if existing_task is not None:
            existing_attachment = self.store.find_attachment(existing_task.id, file_hash)
            if existing_attachment is not None:
                return ImportResult(existing_task, existing_attachment, duplicate=True)

        validation_error = self._validate_file(request)
        if validation_error is not None:
            task = existing_task or self._new_task(request, TaskStatus.BLOCKED, validation_error[1], now)
            if existing_task is None:
                self.store.save_task(task)
            self.store.append_log(
                self._log(task, "import_blocked", request_id, now, None, TaskStatus.BLOCKED.value)
            )
            return ImportResult(task, None, duplicate=False, error_code=validation_error[0], error_message=validation_error[1])

        task = existing_task or self._new_task(request, TaskStatus.IMPORTED, None, now)
        if existing_task is None:
            self.store.save_task(task)

        version_no = self.store.next_version(task.id)
        attachment = ApprovalAttachment(
            id=uuid4(),
            task_id=task.id,
            version_no=version_no,
            file_name=request.file_name,
            mime_type=request.mime_type,
            storage_key=f"contracts/{task.id}/{version_no}/{file_hash}.pdf",
            file_sha256=file_hash,
            page_count=self._page_count(request.content),
            quality_status=QualityStatus.USABLE,
            uploaded_by=request.applicant_id,
            uploaded_at=now,
        )
        for old in self.store.list_attachments(task.id):
            old.is_current = False
            self.store.save_attachment(old)
        self.objects.put(attachment.storage_key, request.content)
        self.store.save_attachment(attachment)
        self.store.append_log(
            self._log(task, "imported", request_id, now, None, TaskStatus.IMPORTED.value, str(attachment.id))
        )
        return ImportResult(task, attachment, duplicate=False)

    @staticmethod
    def _new_task(request: ImportRequest, status: TaskStatus, reason: str | None, now: datetime) -> ApprovalTask:
        return ApprovalTask(uuid4(), request.external_task_key, request.title, request.applicant_id, status, reason, now, now)

    @staticmethod
    def _validate_file(request: ImportRequest) -> tuple[str, str] | None:
        if request.mime_type != "application/pdf":
            return ImportErrorCode.UNSUPPORTED_FILE_TYPE.value, "仅支持 PDF 文件"
        if not request.content:
            return ImportErrorCode.EMPTY_FILE.value, "文件内容为空"
        if not request.content.startswith(b"%PDF-"):
            return ImportErrorCode.INVALID_PDF.value, "文件不是有效 PDF"
        return None

    @staticmethod
    def _page_count(content: bytes) -> int:
        return max(content.count(b"/Type /Page"), 1)

    @staticmethod
    def _log(
        task: ApprovalTask,
        action: str,
        request_id: str,
        now: datetime,
        before: str | None,
        after: str,
        resource_id: str | None = None,
    ) -> TaskLog:
        return TaskLog(
            task_id=task.id,
            actor_id="system",
            action=action,
            resource_type="approval_task",
            resource_id=resource_id or str(task.id),
            before_state={"status": before},
            after_state={"status": after},
            request_id=request_id,
            created_at=now,
        )
