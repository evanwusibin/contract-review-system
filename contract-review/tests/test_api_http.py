import json

from fastapi.testclient import TestClient

from contract_review.domain import InMemoryObjectStorage
from contract_review.ocr import OCRDocument, OCRPage, OCRPageQuality
from contract_review.api import create_app


class HttpOCR:
    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        return [OCRPageQuality(page, 0.95, 60) for page in range(1, page_count + 1)]

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        return OCRDocument(tuple(OCRPage(page, "甲方：甲公司", 0.95) for page in range(1, page_count + 1)))


def client() -> TestClient:
    return TestClient(create_app(InMemoryObjectStorage(), HttpOCR()))


def test_health_and_review_http_chain():
    api = client()
    assert api.get("/v1/health").json()["data"]["status"] == "ok"

    response = api.post(
        "/v1/reviews/run",
        data={
            "external_task_key": "http-001",
            "title": "售后合同",
            "applicant_id": "user-redacted",
            "actor_id": "admin",
            "request_id": "req-http",
            "confirmations": json.dumps({role: [f"u-{role}", "确认"] for role in ("business", "legal", "warranty")}),
        },
        files={"file": ("contract.pdf", b"%PDF-1.7\n/Type /Page\n", "application/pdf")},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["writeback"]["code"] == "SIMULATED_ONLY"
    assert payload["data"]["version"]["version_no"] == 1


def test_review_http_rejects_missing_confirmation_before_save():
    api = client()
    response = api.post(
        "/v1/reviews/run",
        data={
            "external_task_key": "http-002",
            "title": "售后合同",
            "applicant_id": "user-redacted",
            "actor_id": "admin",
            "confirmations": json.dumps({"business": ["u-business", "确认"]}),
        },
        files={"file": ("contract.pdf", b"%PDF-1.7\n/Type /Page\n", "application/pdf")},
    )

    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "REVIEW_WORKFLOW_FAILED"
