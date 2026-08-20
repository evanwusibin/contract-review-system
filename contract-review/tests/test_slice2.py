from contract_review.domain import ImportRequest, InMemoryObjectStorage, InMemoryReviewStore, QualityStatus, TaskStatus
from contract_review.ocr import MockOCRProvider, OCRPageQuality, OCRProviderError, UnlimitedOCRProvider, UnlimitedOCRSettings
from contract_review.quality import QualityDiagnostic
from contract_review.storage import MinioSettings
from contract_review.domain import ContractImporter


def imported_contract(content=b"%PDF-1.7\n/Type /Page\n"):
    store = InMemoryReviewStore()
    importer = ContractImporter(store, InMemoryObjectStorage())
    result = importer.import_contract(ImportRequest("slice2", "合同", "user-redacted", "contract.pdf", "application/pdf", content))
    return store, result


def test_low_quality_pages_are_blocked_with_page_and_next_action():
    store, result = imported_contract()
    provider = MockOCRProvider([OCRPageQuality(1, 0.92, 120), OCRPageQuality(2, 0.42, 0)])
    diagnostic = QualityDiagnostic(store, provider)

    outcome = diagnostic.diagnose(result.task, result.attachment, b"%PDF-1.7\n/Type /Page\n/Type /Page\n", "req-low")

    assert outcome.status is QualityStatus.LOW_QUALITY
    assert outcome.low_confidence_pages == (2,)
    assert outcome.next_action == "按页人工补录后再解析"
    assert result.task.status is TaskStatus.BLOCKED
    assert result.task.blocked_reason == "LOW_OCR_CONFIDENCE"
    assert any(log.action == "quality_blocked" for log in store.logs)


def test_transient_ocr_failure_retries_at_most_three_times_then_blocks():
    store, result = imported_contract()
    provider = MockOCRProvider(error=OCRProviderError("provider unavailable", retryable=True))
    diagnostic = QualityDiagnostic(store, provider)

    outcome = diagnostic.diagnose(result.task, result.attachment, b"%PDF-1.7\n/Type /Page\n", "req-retry")

    assert outcome.attempts == 3
    assert provider.calls == 3
    assert outcome.status is QualityStatus.UNREADABLE
    assert outcome.blocked_reason == "OCR_FAILED"
    assert sum(log.action == "quality_retry" for log in store.logs) == 3
    assert result.task.status is TaskStatus.BLOCKED


def test_corrupted_pdf_is_blocked_without_calling_ocr():
    store, result = imported_contract()
    provider = MockOCRProvider()
    diagnostic = QualityDiagnostic(store, provider)

    outcome = diagnostic.diagnose(result.task, result.attachment, b"not-a-pdf", "req-corrupt")

    assert outcome.blocked_reason == "FILE_CORRUPTED"
    assert outcome.next_action == "重新上传可打开的 PDF"
    assert provider.calls == 0
    assert result.attachment.quality_status is QualityStatus.UNREADABLE


def test_unlimited_ocr_request_uses_openai_compatible_contract():
    provider = UnlimitedOCRProvider(UnlimitedOCRSettings(endpoint="http://ocr:10000"))

    payload = provider.build_request(["data:image/png;base64,abc"])

    assert payload["model"] == "Unlimited-OCR"
    assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png")


def test_minio_settings_use_local_docker_defaults_and_environment_override(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_BUCKET_NAME", "contract-review-test")
    monkeypatch.setenv("MINIO_SECURE", "false")

    settings = MinioSettings.from_env()

    assert settings.endpoint == "minio:9000"
    assert settings.bucket == "contract-review-test"
    assert settings.url == "http://minio:9000"
