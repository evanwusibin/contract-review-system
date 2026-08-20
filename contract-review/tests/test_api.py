import json

from fastapi.testclient import TestClient

from contract_review.api import create_app
from contract_review.ocr import OCRDocument, OCRPage, OCRPageQuality
from contract_review.storage import create_memory_storage


class HTTPGoldenOCR:
    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        return [OCRPageQuality(page, 0.95, 80) for page in range(1, page_count + 1)]

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        text = "甲方：甲公司\n合同编号：HT-HTTP-001\n金额：100\n币种：CNY"
        return OCRDocument(tuple(OCRPage(page, text, 0.95) for page in range(1, page_count + 1)))


def client() -> TestClient:
    return TestClient(create_app(create_memory_storage(), HTTPGoldenOCR()))


def pdf() -> bytes:
    return b"%PDF-1.7\n/Type /Page\n"


def confirmations() -> str:
    return json.dumps({role: [f"u-{role}", f"{role}确认"] for role in ("business", "legal", "warranty")})


def test_http_health_and_import_are_real_service_contracts():
    http = client()

    health = http.get("/v1/health")
    imported = http.post(
        "/v1/imports",
        data={"external_task_key": "http-001", "title": "合同", "applicant_id": "u-1", "request_id": "req-import"},
        files={"file": ("contract.pdf", pdf(), "application/pdf")},
    )

    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"
    assert imported.status_code == 200
    assert imported.json()["ok"] is True
    assert imported.json()["data"]["task"]["status"] == "imported"

    tasks = http.get("/v1/tasks")
    assert tasks.status_code == 200
    assert tasks.json()["data"]["total"] == 1
    assert tasks.json()["data"]["items"][0]["external_task_key"] == "http-001"


def test_http_review_runs_full_workflow_and_exposes_version():
    http = client()

    response = http.post(
        "/v1/reviews/run",
        data={
            "external_task_key": "http-002",
            "title": "售后合同",
            "applicant_id": "u-1",
            "confirmations": confirmations(),
            "actor_id": "admin",
            "request_id": "req-review",
        },
        files={"file": ("contract.pdf", pdf(), "application/pdf")},
    )
    body = response.json()
    task_id = body["data"]["task_id"]

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["review"]["status"] == "confirmed"
    assert body["data"]["writeback"]["code"] == "SIMULATED_ONLY"

    task = http.get(f"/v1/tasks/{task_id}")
    versions = http.get(f"/v1/tasks/{task_id}/versions")
    version_id = versions.json()["data"]["items"][0]["id"]
    restored = http.get(f"/v1/tasks/{task_id}/versions/{version_id}")

    assert task.status_code == 200
    assert task.json()["data"]["task"]["status"] == "confirmed"
    assert versions.json()["data"]["total"] == 1
    assert restored.status_code == 200
    assert restored.json()["data"]["view_context"]["read_only"] is True


def test_http_review_is_idempotent_for_same_task_and_file():
    http = client()
    payload = {
        "external_task_key": "http-003",
        "title": "合同",
        "applicant_id": "u-1",
        "confirmations": confirmations(),
        "actor_id": "admin",
    }
    first = http.post("/v1/reviews/run", data={**payload, "request_id": "req-1"}, files={"file": ("contract.pdf", pdf(), "application/pdf")})
    second = http.post("/v1/reviews/run", data={**payload, "request_id": "req-2"}, files={"file": ("contract.pdf", pdf(), "application/pdf")})

    assert first.json()["data"]["duplicate"] is False
    assert second.json()["data"]["duplicate"] is True
    assert first.json()["data"]["version"]["id"] == second.json()["data"]["version"]["id"]
