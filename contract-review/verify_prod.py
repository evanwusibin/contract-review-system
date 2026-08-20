"""生产环境全链路验收脚本"""
import json, urllib.request, http.cookiejar
from pathlib import Path

API = "http://127.0.0.1:8001"
PDF = Path("tests/data/test_contract_after_sales.pdf")

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

def multipart(fields: dict, file_path: str | None) -> bytes:
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = b""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    if file_path:
        content = Path(file_path).read_bytes()
        fname = Path(file_path).name
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
        body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, boundary

def post(path, fields=None, file_path=None):
    data, boundary = multipart(fields or {}, file_path)
    req = urllib.request.Request(f"{API}{path}", data=data, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    return json.loads(opener.open(req, timeout=300).read().decode())

def get(path):
    req = urllib.request.Request(f"{API}{path}")
    return json.loads(opener.open(req, timeout=15).read().decode())

# Step 1: Login
print("=== Step 1: Login ===")
r = post("/v1/auth/login", {"username": "admin", "password": "fa21bc041474b3ae94d7e043"})
assert r["ok"], f"Login failed: {r}"
print(f"  [OK] {r['data']['user']['username']} ({r['data']['user']['role']})")

# Step 2: Health
print("=== Step 2: Health ===")
r = get("/v1/health")
assert r["ok"]
print("  [OK]")

# Step 3: Import
print("=== Step 3: Import Contract ===")
r = post("/v1/imports", {"external_task_key": "PROD-FINAL-005", "title": "生产验收", "applicant_id": "admin"}, str(PDF))
assert r["ok"], f"Import failed: {r}"
task_id = r["data"]["task"]["id"]
print(f"  [OK] task={task_id[:8]}...")

# Step 4: Run Review
print("=== Step 4: Run Review Pipeline ===")
confirmations = json.dumps({"business": ["admin", "ok"], "legal": ["admin", "ok"], "warranty": ["admin", "ok"]})
r = post("/v1/reviews/run", {
    "external_task_key": "PROD-FINAL-006", "title": "生产验收",
    "applicant_id": "admin", "confirmations": confirmations, "actor_id": "admin"
}, str(PDF))
if not r["ok"]:
    print(f"  [FAIL] {r.get('error', {}).get('message')}")
    print(f"  [INFO] Try with different user roles...")
    # Try with business user
    r = post("/v1/auth/login", {"username": "business", "password": "business123"})
    print(f"  [AUTH] business login: {r.get('ok')}")
    exit(1)
assert r["ok"], f"Review failed: {r.get('error')}"
print(f"  [OK] status={r['data']['review_status']}")
print(f"  [OK] recommendation={r['data']['review']['recommendation']}")
print(f"  [OK] writeback={r['data']['writeback']['code']}")

# Step 5: Versions
print("=== Step 5: Versions ===")
r = get(f"/v1/tasks/{task_id}/versions")
print(f"  [OK] versions={r['data']['total']}")

# Step 6: Audit
print("=== Step 6: Audit Events ===")
r = get("/v1/audit/events?limit=5")
print(f"  [OK] events={r['data']['total']}")

# Step 7: Rules
print("=== Step 7: Rules ===")
r = get("/v1/rules")
assert r["ok"]
print(f"  [OK] rules={r['data']['total']}")

# Step 8: Review Detail
print("=== Step 8: Review Detail ===")
r = get(f"/v1/tasks/{task_id}/review")
assert r["ok"]
print(f"  [OK] fields={len(r['data'].get('parse',{}).get('extracted_payload',{}))}")
print(f"  [OK] required_roles={r['data'].get('review',{}).get('required_roles')}")

print("\n=== ALL PRODUCTION E2E TESTS PASSED ===")