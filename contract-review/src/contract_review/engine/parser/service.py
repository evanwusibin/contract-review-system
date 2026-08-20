from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from re import search
from uuid import UUID, uuid4

from contract_review.domain import ApprovalAttachment, ApprovalTask, InMemoryReviewStore, TaskLog, TaskStatus
from contract_review.infrastructure.ocr.provider import OCRDocument, OCRPage, OCRProviderError


class ParseStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FieldStatus(StrEnum):
    FOUND = "found"
    MISSING = "missing"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True)
class FieldEvidence:
    page_no: int
    snippet: str
    confidence: float


@dataclass(frozen=True)
class ExtractedField:
    value: str | None
    status: FieldStatus
    confidence: float
    evidence: FieldEvidence | None


@dataclass(frozen=True)
class ContractParse:
    id: UUID
    attachment_id: UUID
    parser_version: str
    status: ParseStatus
    quality_score: float | None
    extracted_payload: dict[str, ExtractedField]
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class ContractParser:
    """将 OCR 页结果收敛为可追溯字段，不把全文当作结构化事实。"""

    FIELD_LABELS = {
        "party_a": ("甲方", "party_a"),
        "party_b": ("乙方", "party_b"),
        "contract_no": ("合同编号", "contract_no"),
        "amount": ("金额", "amount"),
        "currency": ("币种", "currency"),
        "signed_date": ("签订日期", "signed_date"),
        "warranty_term": ("质保期", "warranty_term"),
    }

    def __init__(self, store: InMemoryReviewStore, provider, parser_version: str = "slice3-v1") -> None:
        self.store = store
        self.provider = provider
        self.parser_version = parser_version

    def parse(
        self,
        task: ApprovalTask,
        attachment: ApprovalAttachment,
        content: bytes,
        request_id: str = "req_local",
    ) -> ContractParse:
        started = datetime.now(timezone.utc)
        parse_id = uuid4()
        self.store.append_log(self._log(task, "parse_started", request_id, started, {"status": ParseStatus.RUNNING.value}))
        try:
            document = self.provider.recognize(content, attachment.page_count)
            payload = self._extract_fields(document)
            finished = datetime.now(timezone.utc)
            result = ContractParse(parse_id, attachment.id, self.parser_version, ParseStatus.SUCCEEDED, self._quality(payload), payload, None, None, started, finished)
            task.status = TaskStatus.REVIEWING if hasattr(TaskStatus, "REVIEWING") else task.status
            self.store.append_log(self._log(task, "parse_succeeded", request_id, finished, {"status": ParseStatus.SUCCEEDED.value, "field_count": str(len(payload))}))
            self.store.save_parse(result)
            return result
        except OCRProviderError as exc:
            finished = datetime.now(timezone.utc)
            self.store.append_log(self._log(task, "parse_failed", request_id, finished, {"status": ParseStatus.FAILED.value, "error_code": "OCR_FAILED"}))
            failed = ContractParse(parse_id, attachment.id, self.parser_version, ParseStatus.FAILED, None, {}, "OCR_FAILED", str(exc), started, finished)
            self.store.save_parse(failed)
            return failed
        except (ValueError, TypeError) as exc:
            finished = datetime.now(timezone.utc)
            self.store.append_log(self._log(task, "parse_failed", request_id, finished, {"status": ParseStatus.FAILED.value, "error_code": "INVALID_OCR_PAYLOAD"}))
            failed = ContractParse(parse_id, attachment.id, self.parser_version, ParseStatus.FAILED, None, {}, "INVALID_OCR_PAYLOAD", str(exc), started, finished)
            self.store.save_parse(failed)
            return failed

    def _extract_fields(self, document: OCRDocument) -> dict[str, ExtractedField]:
        fields: dict[str, ExtractedField] = {}
        for key, labels in self.FIELD_LABELS.items():
            fields[key] = self._extract_field(document.pages, labels)
        return fields

    @staticmethod
    def _extract_field(pages: tuple[OCRPage, ...], labels: tuple[str, str]) -> ExtractedField:
        label = labels[0]
        for page in pages:
            match = search(rf"{label}\s*[:：]\s*([^\n，,；;]+)", page.text)
            if match:
                value = match.group(1).strip()
                confidence = page.confidence
                status = FieldStatus.FOUND if confidence >= 0.7 else FieldStatus.LOW_CONFIDENCE
                return ExtractedField(value, status, confidence, FieldEvidence(page.page_no, match.group(0)[:200], confidence))
        return ExtractedField(None, FieldStatus.MISSING, 0.0, None)

    @staticmethod
    def _quality(payload: dict[str, ExtractedField]) -> float:
        return round(sum(item.confidence for item in payload.values()) / len(payload) * 100, 2)

    @staticmethod
    def _log(task: ApprovalTask, action: str, request_id: str, now: datetime, after: dict[str, str]) -> TaskLog:
        return TaskLog(task.id, "system", action, "contract_parse", str(task.id), {}, after, request_id, now)
