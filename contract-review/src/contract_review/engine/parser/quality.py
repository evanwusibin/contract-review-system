from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from contract_review.domain import ApprovalAttachment, ApprovalTask, InMemoryReviewStore, QualityStatus, TaskLog, TaskStatus
from contract_review.infrastructure.ocr.provider import OCRPageQuality, OCRProvider, OCRProviderError


@dataclass(frozen=True)
class QualityDiagnosticResult:
    attachment_id: UUID
    status: QualityStatus
    quality_score: float
    low_confidence_pages: tuple[int, ...]
    attempts: int
    blocked_reason: str | None
    next_action: str


class QualityDiagnostic:
    def __init__(self, store: InMemoryReviewStore, provider: OCRProvider, max_attempts: int = 3) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.store = store
        self.provider = provider
        self.max_attempts = max_attempts

    def diagnose(self, task: ApprovalTask, attachment: ApprovalAttachment, content: bytes, request_id: str = "req_local") -> QualityDiagnosticResult:
        now = datetime.now(timezone.utc)
        if not content.startswith(b"%PDF-"):
            return self._blocked(task, attachment, QualityStatus.UNREADABLE, 0.0, (), 1, "FILE_CORRUPTED", "重新上传可打开的 PDF", request_id, now)

        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            try:
                pages = self.provider.inspect(content, attachment.page_count)
                return self._classify(task, attachment, pages, attempts, request_id, now)
            except OCRProviderError as exc:
                self.store.append_log(self._log(task, "quality_retry", request_id, now, {"attempt": str(attempts)}))
                if not exc.retryable or attempts >= self.max_attempts:
                    return self._blocked(task, attachment, QualityStatus.UNREADABLE, 0.0, (), attempts, "OCR_FAILED", "人工补录或更换解析服务", request_id, now)
        raise AssertionError("retry loop must return")

    def _classify(self, task, attachment, pages: list[OCRPageQuality], attempts, request_id, now):
        confidences = [max(0.0, min(1.0, page.confidence)) for page in pages]
        score = round(sum(confidences) / len(confidences) * 100, 2) if confidences else 0.0
        low_pages = tuple(page.page_no for page in pages if page.confidence < 0.7 or page.text_length == 0)
        if low_pages:
            return self._blocked(task, attachment, QualityStatus.LOW_QUALITY, score, low_pages, attempts, "LOW_OCR_CONFIDENCE", "按页人工补录后再解析", request_id, now)
        attachment.quality_status = QualityStatus.USABLE
        self.store.append_log(self._log(task, "quality_usable", request_id, now, {"quality_score": str(score)}))
        self.store.save_attachment(attachment)
        return QualityDiagnosticResult(attachment.id, QualityStatus.USABLE, score, (), attempts, None, "进入解析")

    def _blocked(self, task, attachment, status, score, low_pages, attempts, reason, next_action, request_id, now):
        task.status = TaskStatus.BLOCKED
        task.blocked_reason = reason
        task.updated_at = now
        attachment.quality_status = status
        self.store.append_log(self._log(task, "quality_blocked", request_id, now, {"reason": reason, "attempts": str(attempts)}))
        self.store.save_attachment(attachment)
        self.store.save_task(task)
        return QualityDiagnosticResult(attachment.id, status, score, low_pages, attempts, reason, next_action)

    @staticmethod
    def _log(task, action, request_id, now, after):
        return TaskLog(task.id, "system", action, "approval_task", str(task.id), {}, after, request_id, now)
