"""Unlimited-OCR 联调验证脚本。

使用方式：
1. 确保 Unlimited-OCR 服务已启动：docker compose up -d unlimited-ocr
2. 确认服务就绪：python verify_ocr.py --health
3. 执行联调测试：python verify_ocr.py --run

环境变量（可选）：
    UNLIMITED_OCR_ENDPOINT=http://127.0.0.1:10000
    UNLIMITED_OCR_MODEL=Unlimited-OCR
    UNLIMITED_OCR_TIMEOUT_SECONDS=1200
"""

import argparse
import sys
from pathlib import Path

from contract_review.ocr import (
    OCRProviderError,
    UnlimitedOCRProvider,
    UnlimitedOCRSettings,
)


DATA_DIR = Path(__file__).parent / "tests" / "data"
PDFS = [
    DATA_DIR / "test_contract_purchase.pdf",
    DATA_DIR / "test_contract_after_sales.pdf",
]


def check_health(endpoint: str) -> bool:
    settings = UnlimitedOCRSettings(endpoint=endpoint)
    provider = UnlimitedOCRProvider(settings=settings)
    result = provider.health_check()
    if result["ok"]:
        models = [m["id"] for m in result.get("models", [])]
        print(f"[OK] Unlimited-OCR 服务就绪，可用模型: {models}")
        return True
    else:
        print(f"[FAIL] Unlimited-OCR 服务不可达: {result['error']}")
        return False


def run_ocr(settings: UnlimitedOCRSettings) -> bool:
    provider = UnlimitedOCRProvider(settings=settings)
    all_ok = True

    for pdf in PDFS:
        if not pdf.exists():
            print(f"[SKIP] 缺少测试文件: {pdf}")
            continue

        size_kb = pdf.stat().st_size / 1024
        print(f"\n--- 测试: {pdf.name} ({size_kb:.0f} KB) ---")

        try:
            content = pdf.read_bytes()
            print(f"[INFO] 发送 OCR 请求，timeout={settings.timeout_seconds}s...")
            doc = provider.recognize(content, page_count=3)

            print(f"[OK] 识别成功，共 {len(doc.pages)} 页")
            for page in doc.pages:
                text_preview = page.text[:200].replace("\n", " ")
                print(f"  Page {page.page_no}: {len(page.text)} chars, confidence={page.confidence:.2f}")
                if page.text:
                    print(f"    预览: {text_preview}...")

        except OCRProviderError as exc:
            all_ok = False
            print(f"[FAIL] OCR 失败: {exc}")
            print(f"       retryable={exc.retryable}")
        except Exception as exc:
            all_ok = False
            print(f"[FAIL] 意外错误: {exc}")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Unlimited-OCR 联调验证")
    parser.add_argument("--health", action="store_true", help="仅检查服务健康状态")
    parser.add_argument("--run", action="store_true", help="执行 OCR 联调测试")
    parser.add_argument("--endpoint", default=None, help="OCR 服务地址")
    args = parser.parse_args()

    endpoint = args.endpoint or "http://127.0.0.1:10000"

    if args.health:
        ok = check_health(endpoint)
        sys.exit(0 if ok else 1)

    if args.run:
        if not check_health(endpoint):
            print("\n[ERROR] 服务未就绪，请先启动: docker compose up -d unlimited-ocr")
            sys.exit(1)

        settings = UnlimitedOCRSettings.from_env()
        if args.endpoint:
            settings = UnlimitedOCRSettings(endpoint=args.endpoint)

        ok = run_ocr(settings)
        sys.exit(0 if ok else 1)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()