"""MinIO 对象读写联调验证（HP-005）。

验证：bucket 创建 → 对象上传 → 对象下载 → sha256 一致性校验
"""
import hashlib
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, "C:/Users/wuwri/AppData/Roaming/Python/Python312-32/site-packages")
sys.path.insert(0, str(Path(__file__).parent / "src"))

from contract_review.storage import create_storage

TEST_PDF = Path(__file__).parent / "tests" / "data" / "test_contract_purchase.pdf"
BUCKET = "contract-review-e2e"
KEY = "e2e/contracts/hp005-verification.pdf"


def main() -> int:
    content = TEST_PDF.read_bytes()
    expected_sha = hashlib.sha256(content).hexdigest()
    print(f"[INFO] 源文件: {TEST_PDF.name} ({len(content)} bytes)")
    print(f"[INFO] 预期 sha256: {expected_sha[:16]}...")

    storage = create_storage()
    print("[INFO] storage backend: MinIO")

    # 1. bucket 创建
    storage.ensure_bucket()
    print(f"[OK] bucket 创建/确认: {BUCKET}")

    # 2. 对象上传
    storage.put(KEY, content)
    print(f"[OK] 对象上传: {KEY}")

    # 3. 对象下载
    downloaded = storage.get(KEY)
    print(f"[OK] 对象下载: {len(downloaded)} bytes")

    # 4. sha256 一致性
    actual_sha = hashlib.sha256(downloaded).hexdigest()
    if actual_sha != expected_sha:
        print(f"[FAIL] sha256 不一致: expected={expected_sha[:16]}... actual={actual_sha[:16]}...")
        return 1
    print(f"[OK] sha256 读回校验一致: {actual_sha[:16]}...")

    # 5. 内容逐字节对比
    if downloaded != content:
        print("[FAIL] 对象内容与源文件不一致")
        return 1
    print("[OK] 对象内容逐字节一致")

    print("\n=== HP-005 MinIO 对象读写联调 PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
