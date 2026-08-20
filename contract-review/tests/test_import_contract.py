from contract_review.domain import (
    ContractImporter,
    ImportRequest,
    InMemoryObjectStorage,
    InMemoryReviewStore,
    TaskStatus,
)


def make_importer() -> ContractImporter:
    return ContractImporter(InMemoryReviewStore(), InMemoryObjectStorage())


def valid_pdf() -> bytes:
    return b"%PDF-1.7\n/Type /Page\n"


def test_valid_pdf_creates_imported_task_and_first_attachment() -> None:
    importer = make_importer()
    result = importer.import_contract(
        ImportRequest("approval-001", "售后合同", "user-redacted", "contract.pdf", "application/pdf", valid_pdf()),
        request_id="req-001",
    )

    assert result.error_code is None
    assert result.task.status is TaskStatus.IMPORTED
    assert result.attachment is not None
    assert result.attachment.version_no == 0
    assert result.attachment.page_count == 1
    assert len(importer.store.logs) == 1
    assert importer.store.logs[0].action == "imported"


def test_same_task_and_hash_is_idempotent() -> None:
    importer = make_importer()
    request = ImportRequest("approval-001", "售后合同", "user-redacted", "contract.pdf", "application/pdf", valid_pdf())

    first = importer.import_contract(request)
    second = importer.import_contract(request)

    assert second.duplicate is True
    assert second.task.id == first.task.id
    assert second.attachment is not None
    assert second.attachment.id == first.attachment.id
    assert len(importer.store.tasks) == 1
    assert len(importer.store.attachments) == 1


def test_same_task_with_new_hash_creates_next_version_without_overwriting() -> None:
    importer = make_importer()
    first = importer.import_contract(
        ImportRequest("approval-001", "售后合同", "user-redacted", "v1.pdf", "application/pdf", valid_pdf())
    )
    second = importer.import_contract(
        ImportRequest("approval-001", "售后合同", "user-redacted", "v2.pdf", "application/pdf", valid_pdf() + b"revision")
    )

    assert first.attachment is not None
    assert second.attachment is not None
    assert second.attachment.version_no == 1
    assert first.attachment.is_current is False
    assert second.attachment.is_current is True
    assert len(importer.store.attachments) == 2


def test_unsupported_file_is_blocked_and_does_not_create_attachment() -> None:
    importer = make_importer()
    result = importer.import_contract(
        ImportRequest("approval-002", "不支持格式", "user-redacted", "contract.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"docx")
    )

    assert result.error_code == "UNSUPPORTED_FILE_TYPE"
    assert result.task.status is TaskStatus.BLOCKED
    assert result.attachment is None
    assert importer.store.attachments == {}
    assert importer.store.logs[0].action == "import_blocked"
    assert b"docx" not in str(importer.store.logs[0].after_state).encode()
