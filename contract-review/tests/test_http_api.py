from fastapi.testclient import TestClient

from contract_review.domain import ContractImporter, InMemoryObjectStorage, InMemoryReviewStore
from contract_review.infrastructure.ocr.provider import OCRDocument, OCRPage, OCRPageQuality
from contract_review.engine.parser.service import ContractParser
from contract_review.engine.parser.quality import QualityDiagnostic
from contract_review.engine.workflow.results import ReviewResultService
from contract_review.engine.rules.engine import RestrictedRuleEngine
from contract_review.engine.workflow.versions import ReviewVersionService
from contract_review.engine.workflow.workflow import ContractReviewWorkflow, SimulatedApprovalGateway
from contract_review.api import create_app


class HttpOCR:
    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        return [OCRPageQuality(1, 0.95, 60)]

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        return OCRDocument((OCRPage(1, "甲方：甲公司", 0.95),))


def client() -> TestClient:
    store = InMemoryReviewStore()
    provider = HttpOCR()
    workflow = ContractReviewWorkflow(
        ContractImporter(store, InMemoryObjectStorage()),
        QualityDiagnostic(store, provider),
        ContractParser(store, provider),
        RestrictedRuleEngine(),
        ReviewResultService(store),
        ReviewVersionService(store),
        SimulatedApprovalGateway(),
    )
    return TestClient(create_app(workflow))


def test_http_import_contract_returns_task_and_attachment():
    response = client().post(
        "/v1/imports",
        data={"external_task_key": "http-001", "title": "合同", "applicant_id": "user"},
        files={"file": ("contract.pdf", b"%PDF-1.7\n/Type /Page\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["task"]["status"] == "imported"
    assert payload["data"]["attachment"]["version_no"] == 0


def test_http_task_list_returns_tasks_from_store():
    test_client = client()
    test_client.post(
        "/v1/imports",
        data={"external_task_key": "http-list-001", "title": "列表合同", "applicant_id": "user"},
        files={"file": ("contract.pdf", b"%PDF-1.7\n/Type /Page\n", "application/pdf")},
    )

    response = test_client.get("/v1/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["external_task_key"] == "http-list-001"


def test_http_run_review_and_list_versions():
    test_client = client()
    confirmations = {role: {"actor_id": f"u-{role}", "comment": "确认"} for role in ("business", "legal", "warranty")}
    response = test_client.post(
        "/v1/reviews/run",
        data={
            "external_task_key": "http-002",
            "title": "合同",
            "applicant_id": "user",
            "actor_id": "admin",
            "confirmations": __import__("json").dumps(confirmations),
        },
        files={"file": ("contract.pdf", b"%PDF-1.7\n/Type /Page\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["review_status"] == "confirmed"
    assert payload["data"]["writeback"]["code"] == "SIMULATED_ONLY"
    task_id = payload["data"]["task_id"]
    assert test_client.get(f"/v1/reviews/{task_id}/versions").status_code == 200
