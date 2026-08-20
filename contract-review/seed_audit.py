import urllib.request, json

boundary = "----TestFormBoundary"
fields = {
    "external_task_key": "AUDIT-FINAL-001",
    "title": "审计验证合同",
    "applicant_id": "audit_user",
    "confirmations": json.dumps({r: ["u-" + r, "ok"] for r in ("business", "legal", "warranty")}),
    "actor_id": "audit_user",
}
body = b""
for k, v in fields.items():
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
with open("tests/data/test_contract_after_sales.pdf", "rb") as f:
    content = f.read()
body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"t.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
body += content + b"\r\n--" + boundary.encode() + b"--\r\n"

req = urllib.request.Request("http://127.0.0.1:8001/v1/reviews/run", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
resp = urllib.request.urlopen(req, timeout=180)
d = json.loads(resp.read())
print("review ok:", d.get("ok"), "status:", d.get("data", {}).get("review_status"))
print("writeback:", d.get("data", {}).get("writeback", {}).get("code"))

# 验证审计
req2 = urllib.request.Request("http://127.0.0.1:8001/v1/audit/events?limit=20")
resp2 = urllib.request.urlopen(req2, timeout=10)
d2 = json.loads(resp2.read())
print("audit total:", d2["data"]["total"])
for log in d2["data"]["items"][:5]:
    print("  -", log["action"], log["after_state"])
