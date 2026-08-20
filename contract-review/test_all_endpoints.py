import sys, json
sys.path.insert(0, 'C:/Users/wuwri/AppData/Roaming/Python/Python312-32/site-packages')
sys.path.insert(0, 'src')

from contract_review.api import create_app
from contract_review.ocr import create_ocr_provider
from fastapi.testclient import TestClient

provider = create_ocr_provider('rapid')
app = create_app(ocr_provider=provider)
client = TestClient(app)

print("=== Health ===")
r = client.get("/v1/health")
d = r.json()
assert d["ok"] and d["data"]["status"] == "ok"
print("  [OK]")

print("=== Tasks ===")
r = client.get("/v1/tasks")
d = r.json()
assert d["ok"]
print("  [OK] total=%d" % d["data"]["total"])

print("=== Import ===")
with open("tests/data/test_contract_purchase.pdf", "rb") as f:
    r = client.post("/v1/imports",
        data={"external_task_key": "TEST-001", "title": "购车合同", "applicant_id": "test"},
        files={"file": ("test.pdf", f.read(), "application/pdf")}
    )
d = r.json()
assert d["ok"]
task_id = d["data"]["task"]["id"]
print("  [OK] task=%s" % task_id[:8])

print("=== Get Task ===")
r = client.get("/v1/tasks/" + task_id)
d = r.json()
assert d["ok"] and len(d["data"]["attachments"]) >= 1
print("  [OK] attachments=%d" % len(d["data"]["attachments"]))

print("=== Run Review ===")
with open("tests/data/test_contract_purchase.pdf", "rb") as f:
    confirmations = json.dumps(
        {role: ["u-" + role, "ok"] for role in ("business", "legal", "warranty")}
    )
    r = client.post("/v1/reviews/run",
        data={
            "external_task_key": "TEST-002",
            "title": "购车合同",
            "applicant_id": "test",
            "confirmations": confirmations,
            "actor_id": "test"
        },
        files={"file": ("test.pdf", f.read(), "application/pdf")}
    )
d = r.json()
assert d["ok"]
print("  [OK] status=%s" % d["data"]["review_status"])
print("  [OK] writeback=%s" % d["data"]["writeback"]["code"])
print("  [OK] risk_summary=%s" % d["data"]["review"]["risk_summary"])
print("  [OK] parsed_fields=%d" % len(d["data"]["parse"]["extracted_payload"]))

print("=== List Versions ===")
r = client.get("/v1/tasks/" + task_id + "/versions")
d = r.json()
assert d["ok"]
print("  [OK] total=%d" % d["data"]["total"])

print("=== List Rules ===")
r = client.get("/v1/rules")
d = r.json()
assert d["ok"] and d["data"]["total"] == 3
print("  [OK] rules=%d" % d["data"]["total"])
for rule in d["data"]["items"]:
    print("    %s: %s (%s)" % (rule["rule_code"], rule["name"], rule["severity"]))

print("=== Add Rule ===")
r = client.post("/v1/rules", data={
    "rule_code": "RULE-CUSTOM-001",
    "name": "自定义规则",
    "severity": "medium"
})
d = r.json()
assert d["ok"]
print("  [OK] created: %s" % d["data"]["rule_code"])

print("=== Audit Events ===")
r = client.get("/v1/audit/events?limit=5")
d = r.json()
assert d["ok"]
print("  [OK] total_events=%d" % d["data"]["total"])

print("=== Task Audit ===")
r = client.get("/v1/tasks/" + task_id + "/audit")
d = r.json()
assert d["ok"]
print("  [OK] audit_events=%d" % d["data"]["total"])

print("\n=== ALL 10 ENDPOINTS VERIFIED ===")