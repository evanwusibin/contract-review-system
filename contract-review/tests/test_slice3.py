from contract_review.domain import ContractImporter, ImportRequest, InMemoryObjectStorage, InMemoryReviewStore, TaskStatus
from contract_review.ocr import OCRDocument, OCRPage, OCRProviderError
from contract_review.parser import ContractParser, FieldStatus, ParseStatus


class FixedProvider:
    def __init__(self, document=None, error=None):
        self.document = document
        self.error = error
        self.calls = 0

    def recognize(self, content, page_count):
        self.calls += 1
        if self.error:
            raise self.error
        return self.document


def imported_contract():
    store = InMemoryReviewStore()
    result = ContractImporter(store, InMemoryObjectStorage()).import_contract(
        ImportRequest("slice3", "合同", "user-redacted", "contract.pdf", "application/pdf", b"%PDF-1.7\n/Type /Page\n")
    )
    return store, result


def test_parse_success_returns_fields_with_page_evidence():
    store, result = imported_contract()
    document = OCRDocument((OCRPage(1, "甲方：甲公司\n乙方：乙公司\n合同编号：HT-001\n金额：10000\n币种：CNY\n签订日期：2026-03-14\n质保期：12个月", 0.94),))

    parsed = ContractParser(store, FixedProvider(document)).parse(result.task, result.attachment, b"pdf", "req-parse")

    assert parsed.status is ParseStatus.SUCCEEDED
    assert parsed.extracted_payload["party_b"].value == "乙公司"
    assert parsed.extracted_payload["party_b"].evidence.page_no == 1
    assert parsed.extracted_payload["party_b"].evidence.snippet == "乙方：乙公司"
    assert result.task.status is TaskStatus.REVIEWING
    assert parsed.quality_score == 94.0


def test_missing_field_is_explicit_and_never_empty_success():
    store, result = imported_contract()
    document = OCRDocument((OCRPage(1, "甲方：甲公司", 0.95),))

    parsed = ContractParser(store, FixedProvider(document)).parse(result.task, result.attachment, b"pdf")

    party_b = parsed.extracted_payload["party_b"]
    assert parsed.status is ParseStatus.SUCCEEDED
    assert party_b.value is None
    assert party_b.status is FieldStatus.MISSING
    assert party_b.evidence is None


def test_low_confidence_field_remains_marked_low_confidence():
    store, result = imported_contract()
    document = OCRDocument((OCRPage(2, "乙方：疑似乙公司", 0.42),))

    parsed = ContractParser(store, FixedProvider(document)).parse(result.task, result.attachment, b"pdf")

    field = parsed.extracted_payload["party_b"]
    assert field.status is FieldStatus.LOW_CONFIDENCE
    assert field.confidence == 0.42
    assert field.evidence.page_no == 2


def test_provider_failure_returns_failed_parse_instead_of_empty_fields():
    store, result = imported_contract()
    provider = FixedProvider(error=OCRProviderError("ocr unavailable"))

    parsed = ContractParser(store, provider).parse(result.task, result.attachment, b"pdf", "req-failed")

    assert parsed.status is ParseStatus.FAILED
    assert parsed.error_code == "OCR_FAILED"
    assert parsed.extracted_payload == {}
    assert any(log.action == "parse_failed" for log in store.logs)
