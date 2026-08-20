"""OCR 端到端联调测试。

使用 tests/data/ 下的真实合同 PDF 进行 OCR 识别验证。
支持三种 Provider：Mock / RapidOCR / Unlimited-OCR。

测试策略：
1. Mock 模式：验证测试框架和数据可访问（当前）
2. RapidOCR 模式：pip install rapidocr_onnxruntime 后可直接测试（零 GPU）
3. Unlimited-OCR 模式：Docker GPU 就绪后测试（生产目标）
"""

from pathlib import Path
import importlib.util

from contract_review.infrastructure.ocr.provider import (
    create_ocr_provider,
    MockOCRProvider,
    OCRProviderError,
    RapidOCRProvider,
    RapidOCRSettings,
    UnlimitedOCRProvider,
    UnlimitedOCRSettings,
)


RAPIDOCR_INSTALLED = importlib.util.find_spec("rapidocr_onnxruntime") is not None


DATA_DIR = Path(__file__).parent / "data"
PURCHASE_PDF = DATA_DIR / "test_contract_purchase.pdf"
AFTER_SALES_PDF = DATA_DIR / "test_contract_after_sales.pdf"


def test_pdf_files_exist():
    assert PURCHASE_PDF.exists(), f"缺少测试文件: {PURCHASE_PDF}"
    assert AFTER_SALES_PDF.exists(), f"缺少测试文件: {AFTER_SALES_PDF}"
    assert PURCHASE_PDF.stat().st_size > 0
    assert AFTER_SALES_PDF.stat().st_size > 0


def test_mock_pdf_rendering_purchase():
    content = PURCHASE_PDF.read_bytes()
    provider = MockOCRProvider()
    qualities = provider.inspect(content, page_count=3)
    assert len(qualities) == 3
    for q in qualities:
        assert q.confidence >= 0.9


def test_mock_pdf_rendering_after_sales():
    content = AFTER_SALES_PDF.read_bytes()
    provider = MockOCRProvider()
    qualities = provider.inspect(content, page_count=5)
    assert len(qualities) == 5
    for q in qualities:
        assert q.confidence >= 0.9


def test_mock_error_handling():
    error = OCRProviderError("模拟 OCR 服务不可用")
    provider = MockOCRProvider(error=error)
    try:
        provider.inspect(b"", 1)
    except OCRProviderError as exc:
        assert "不可用" in str(exc)
    else:
        assert False, "应抛出 OCRProviderError"


def test_mock_recognize():
    content = PURCHASE_PDF.read_bytes()
    provider = MockOCRProvider()
    doc = provider.recognize(content, page_count=2)
    assert len(doc.pages) == 2
    assert len(doc.pages[0].text) > 0
    assert doc.pages[0].confidence == 0.95


# ── RapidOCR Provider Tests ──────────────────────────────────────

def test_rapidocr_settings_from_env():
    settings = RapidOCRSettings.from_env()
    assert settings.dpi == 150
    assert settings.use_cuda is False
    assert settings.text_score == 0.5
    assert settings.use_det is True
    assert settings.use_cls is True


def test_rapidocr_graceful_import_failure():
    if RAPIDOCR_INSTALLED:
        provider = RapidOCRProvider()
        assert provider._available is True
        return
    provider = RapidOCRProvider()
    assert provider._available is False


def test_rapidocr_raises_when_not_installed():
    if RAPIDOCR_INSTALLED:
        return
    provider = RapidOCRProvider()
    try:
        provider.recognize(b"%PDF-1.4", page_count=1)
    except OCRProviderError as exc:
        assert "pip install" in str(exc)
    else:
        assert False, "应抛出 OCRProviderError"


def test_rapidocr_health_check():
    if RAPIDOCR_INSTALLED:
        provider = RapidOCRProvider()
        result = provider.health_check()
        assert result["ok"] is True
        assert result["engine"] == "rapidocr_onnxruntime"
        return
    provider = RapidOCRProvider()
    result = provider.health_check()
    assert result == {"ok": False, "engine": "rapidocr_onnxruntime"}


# ── Unlimited-OCR Provider Tests ─────────────────────────────────

def test_unlimited_ocr_settings_from_env():
    settings = UnlimitedOCRSettings.from_env()
    assert settings.endpoint == "http://127.0.0.1:10000"
    assert settings.model == "Unlimited-OCR"
    assert settings.dpi == 300
    assert settings.image_mode == "base"
    assert settings.max_length == 32768
    assert settings.ngram_size == 35
    assert settings.ngram_window == 1024


def test_unlimited_ocr_build_request():
    settings = UnlimitedOCRSettings()
    provider = UnlimitedOCRProvider(settings=settings)
    payload = provider.build_request(["data:image/png;base64,abc123"], "Multi page parsing.")
    assert payload["model"] == "Unlimited-OCR"
    assert payload["temperature"] == 0
    assert payload["stream"] is False
    assert payload["images_config"]["image_mode"] == "base"
    assert "ngram_size" in payload["custom_params"]
    assert "window_size" in payload["custom_params"]
    assert len(payload["messages"][0]["content"]) == 2
    assert payload["messages"][0]["content"][1]["type"] == "image_url"


def test_unlimited_ocr_health_check_unavailable():
    settings = UnlimitedOCRSettings(endpoint="http://127.0.0.1:99999")
    provider = UnlimitedOCRProvider(settings=settings)
    result = provider.health_check()
    assert result["ok"] is False
    assert "error" in result


# ── Factory Tests ────────────────────────────────────────────────

def test_factory_mock():
    provider = create_ocr_provider("mock")
    assert isinstance(provider, MockOCRProvider)


def test_factory_rapid():
    provider = create_ocr_provider("rapid")
    assert isinstance(provider, RapidOCRProvider)


def test_factory_unlimited():
    provider = create_ocr_provider("unlimited")
    assert isinstance(provider, UnlimitedOCRProvider)


def test_factory_env_default():
    import os
    os.environ.pop("OCR_PROVIDER", None)
    provider = create_ocr_provider()
    assert isinstance(provider, MockOCRProvider)


def test_factory_env_rapid():
    import os
    os.environ["OCR_PROVIDER"] = "rapid"
    provider = create_ocr_provider()
    assert isinstance(provider, RapidOCRProvider)
    del os.environ["OCR_PROVIDER"]


def test_factory_env_unlimited():
    import os
    os.environ["OCR_PROVIDER"] = "unlimited"
    provider = create_ocr_provider()
    assert isinstance(provider, UnlimitedOCRProvider)
    del os.environ["OCR_PROVIDER"]


# === RapidOCR 安装后启用以下测试（pip install rapidocr_onnxruntime） ===
#
# def test_rapid_ocr_purchase():
#     """RapidOCR 联调：购车合同"""
#     content = PURCHASE_PDF.read_bytes()
#     provider = create_ocr_provider("rapid")
#     doc = provider.recognize(content, page_count=3)
#     assert len(doc.pages) == 3
#     assert len(doc.pages[0].text) > 50
#
#
# def test_rapid_ocr_after_sales():
#     """RapidOCR 联调：售后服务协议"""
#     content = AFTER_SALES_PDF.read_bytes()
#     provider = create_ocr_provider("rapid")
#     doc = provider.recognize(content, page_count=5)
#     assert len(doc.pages) == 5
#     assert len(doc.pages[0].text) > 50
#
#
# def test_rapid_ocr_inspect():
#     """RapidOCR inspect：仅检查页面质量"""
#     content = PURCHASE_PDF.read_bytes()
#     provider = create_ocr_provider("rapid")
#     qualities = provider.inspect(content, page_count=3)
#     assert len(qualities) == 3
#     for q in qualities:
#         assert 0.0 <= q.confidence <= 1.0


# === Unlimited-OCR Docker 就绪后启用 ===
#
# def test_unlimited_ocr_purchase():
#     content = PURCHASE_PDF.read_bytes()
#     provider = create_ocr_provider("unlimited")
#     doc = provider.recognize(content, page_count=3)
#     assert len(doc.pages) == 3
#     assert len(doc.pages[0].text) > 100
#
#
# def test_unlimited_ocr_after_sales():
#     content = AFTER_SALES_PDF.read_bytes()
#     provider = create_ocr_provider("unlimited")
#     doc = provider.recognize(content, page_count=5)
#     assert len(doc.pages) == 5
#     assert len(doc.pages[0].text) > 100