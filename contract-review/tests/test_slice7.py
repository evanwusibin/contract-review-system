from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contract_review.domain import ContractImporter, ImportRequest, InMemoryObjectStorage, InMemoryReviewStore, TaskStatus
from contract_review.infrastructure.ocr.provider import OCRDocument, OCRPage, OCRPageQuality
from contract_review.engine.parser.service import ContractParser
from contract_review.engine.parser.quality import QualityDiagnostic
from contract_review.engine.workflow.results import ReviewResultService, ResultStatus
from contract_review.engine.rules.engine import RestrictedRuleEngine, party_completeness_rule
from contract_review.engine.workflow.versions import ReviewVersionService
from contract_review.engine.workflow.workflow import ContractReviewWorkflow, SimulatedApprovalGateway, WorkflowError


class GoldenOCR:
    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        return [OCRPageQuality(page, 0.95, 80) for page in range(1, page_count + 1)]

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        text = "甲方：甲公司\n合同编号：HT-001\n金额：100\n币种：CNY"
        return OCRDocument(tuple(OCRPage(page, text, 0.95) for page in range(1, page_count + 1)))


def build_workflow() -> tuple[ContractReviewWorkflow, InMemoryReviewStore, SimulatedApprovalGateway]:
    store = InMemoryReviewStore()
    importer = ContractImporter(store, InMemoryObjectStorage())
    provider = GoldenOCR()
    gateway = SimulatedApprovalGateway()
    workflow = ContractReviewWorkflow(
        importer,
        QualityDiagnostic(store, provider),
        ContractParser(store, provider),
        RestrictedRuleEngine(),
        ReviewResultService(store),
        ReviewVersionService(store),
        gateway,
    )
    return workflow, store, gateway


def request() -> ImportRequest:
    return ImportRequest("approval-007", "售后合同", "user-redacted", "contract.pdf", "application/pdf", b"%PDF-1.7\n/Type /Page\n")


def confirmations() -> dict[str, tuple[str, str]]:
    return {role: (f"u-{role}", f"{role}确认") for role in ("business", "legal", "warranty")}


def test_golden_case_runs_import_parse_rule_confirm_save_and_simulated_writeback():
    workflow, store, gateway = build_workflow()

    outcome = workflow.run(request(), [party_completeness_rule()], confirmations(), "admin", "req-golden")

    assert outcome.review.status is ResultStatus.CONFIRMED
    assert outcome.version.version_no == 1
    assert outcome.writeback.code == "SIMULATED_ONLY"
    assert outcome.writeback.recommendation == "reject"
    assert outcome.parse.extracted_payload["party_b"].value is None
    assert store.tasks[outcome.review.task_id].status is TaskStatus.CONFIRMED
    assert len(gateway.calls) == 1


def test_repeating_same_input_is_idempotent_for_version_and_writeback():
    workflow, store, gateway = build_workflow()
    rules = [party_completeness_rule()]

    first = workflow.run(request(), rules, confirmations(), "admin", "req-first")
    second = workflow.run(request(), rules, confirmations(), "admin", "req-repeat")

    assert second.duplicate is True
    assert second.version.id == first.version.id
    assert len(store.versions) == 1
    assert len(gateway.calls) == 1
    assert len(store.tasks) == 1
    assert len(store.attachments) == 1


def test_missing_confirmation_does_not_reach_version_or_writeback():
    workflow, store, gateway = build_workflow()
    incomplete = {"business": ("u-business", "确认")}

    with pytest.raises(WorkflowError, match="缺少会签角色"):
        workflow.run(request(), [party_completeness_rule()], incomplete, "admin")

    assert store.versions == {}
    assert gateway.calls == []
