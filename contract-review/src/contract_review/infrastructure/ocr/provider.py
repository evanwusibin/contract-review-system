from base64 import b64encode
from dataclasses import dataclass
from json import dumps, loads
from os import getenv
from typing import Callable, Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class OCRProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class OCRProvider(Protocol):
    def inspect(self, content: bytes, page_count: int) -> list["OCRPageQuality"]: ...
    def recognize(self, content: bytes, page_count: int) -> "OCRDocument": ...


@dataclass(frozen=True)
class OCRPageQuality:
    page_no: int
    confidence: float
    text_length: int


@dataclass(frozen=True)
class OCRPage:
    page_no: int
    text: str
    confidence: float


@dataclass(frozen=True)
class OCRDocument:
    pages: tuple[OCRPage, ...]


# ── RapidOCR Settings ──────────────────────────────────────────────

@dataclass(frozen=True)
class RapidOCRSettings:
    dpi: int = 150
    use_cuda: bool = False
    text_score: float = 0.5
    use_det: bool = True
    use_cls: bool = True

    @classmethod
    def from_env(cls) -> "RapidOCRSettings":
        return cls(
            dpi=int(getenv("RAPID_OCR_DPI", "150")),
            use_cuda=getenv("RAPID_OCR_CUDA", "").lower() in ("1", "true", "yes"),
            text_score=float(getenv("RAPID_OCR_TEXT_SCORE", "0.5")),
            use_det=getenv("RAPID_OCR_USE_DET", "1").lower() not in ("0", "false", "no"),
            use_cls=getenv("RAPID_OCR_USE_CLS", "1").lower() not in ("0", "false", "no"),
        )


# ── Unlimited-OCR Settings ─────────────────────────────────────────

@dataclass(frozen=True)
class UnlimitedOCRSettings:
    endpoint: str = "http://127.0.0.1:10000"
    model: str = "Unlimited-OCR"
    timeout_seconds: int = 1200
    dpi: int = 300
    image_mode: str = "base"
    max_length: int = 32768
    ngram_size: int = 35
    ngram_window: int = 1024

    @classmethod
    def from_env(cls) -> "UnlimitedOCRSettings":
        return cls(
            endpoint=getenv("UNLIMITED_OCR_ENDPOINT", cls.endpoint),
            model=getenv("UNLIMITED_OCR_MODEL", cls.model),
            timeout_seconds=int(getenv("UNLIMITED_OCR_TIMEOUT_SECONDS", str(cls.timeout_seconds))),
            dpi=int(getenv("UNLIMITED_OCR_DPI", str(cls.dpi))),
            image_mode=getenv("UNLIMITED_OCR_IMAGE_MODE", cls.image_mode),
            max_length=int(getenv("UNLIMITED_OCR_MAX_LENGTH", str(cls.max_length))),
            ngram_size=int(getenv("UNLIMITED_OCR_NGRAM_SIZE", str(cls.ngram_size))),
            ngram_window=int(getenv("UNLIMITED_OCR_NGRAM_WINDOW", str(cls.ngram_window))),
        )


# ── RapidOCR Provider ─────────────────────────────────────────────

class RapidOCRProvider:
    """零依赖 CPU OCR 适配器，基于 rapidocr_onnxruntime。

    安装：pip install rapidocr_onnxruntime
    模型约 150MB，首次调用自动下载。
    支持 PDF（逐页渲染→逐页 OCR）和图片输入。
    不依赖 GPU，适合开发和测试环境。
    """

    def __init__(
        self,
        settings: RapidOCRSettings | None = None,
    ) -> None:
        self.settings = settings or RapidOCRSettings()
        self._engine = None
        self._available = False
        self._load_engine()

    def _load_engine(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR as _RapidOCR

            engine_kwargs = {}
            if self.settings.use_cuda:
                engine_kwargs["use_cuda"] = True

            self._engine = _RapidOCR(**engine_kwargs)
            self._available = True
        except ImportError as exc:
            self._engine = None
            self._available = False
            self._import_error = exc

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        if not self._available:
            raise OCRProviderError(
                "rapidocr_onnxruntime not installed. Run: pip install rapidocr_onnxruntime",
                retryable=False,
            )

        is_pdf = content[:4] == b"%PDF"
        images = self._pdf_to_images(content) if is_pdf else [content]

        pages = []
        for i, img_bytes in enumerate(images[:page_count], 1):
            try:
                text, confidence = self._ocr_image(img_bytes)
            except Exception as exc:
                raise OCRProviderError(f"RapidOCR page {i} failed: {exc}") from exc
            pages.append(
                OCRPage(
                    page_no=i,
                    text=text,
                    confidence=round(confidence, 4),
                )
            )

        return OCRDocument(pages=tuple(pages))

    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        return [
            OCRPageQuality(p.page_no, p.confidence, len(p.text))
            for p in self.recognize(content, page_count).pages
        ]

    def health_check(self) -> dict:
        return {"ok": self._available, "engine": "rapidocr_onnxruntime"}

    def _pdf_to_images(self, content: bytes) -> list[bytes]:
        try:
            import fitz

            doc = fitz.open(stream=content, filetype="pdf")
            if len(doc) == 0:
                raise OCRProviderError("PDF has no pages", retryable=False)
            images = []
            matrix = fitz.Matrix(self.settings.dpi / 72, self.settings.dpi / 72)
            for page in doc:
                img = page.get_pixmap(matrix=matrix, alpha=False).tobytes("png")
                images.append(img)
            doc.close()
            return images
        except OCRProviderError:
            raise
        except ImportError:
            raise OCRProviderError("pymupdf required for PDF processing. Run: pip install pymupdf", retryable=False)
        except Exception as exc:
            raise OCRProviderError(f"PDF rendering failed: {exc}", retryable=False) from exc

    def _ocr_image(self, img_bytes: bytes) -> tuple[str, float]:
        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        import numpy as np
        arr = np.array(img)

        result = self._engine(arr)

        if not result or result[1] is None:
            return "", 0.0

        texts = []
        confidences = []
        raw_items = result[0]

        for item in raw_items:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                texts.append(str(item[1]))
                confidences.append(float(item[2]))
            elif isinstance(item, str):
                texts.append(item)
                confidences.append(0.5)

        return "\n".join(texts), round(
            sum(confidences) / len(confidences), 4
        ) if confidences else 0.0


# ── Unlimited-OCR Provider ────────────────────────────────────────

class UnlimitedOCRProvider:
    """Unlimited-OCR 的 OpenAI-compatible 多页 PDF 适配器。"""

    NO_REPEAT_PROCESSOR = (
        'sglang.srt.sampling.custom_logit_processor.DeepseekOCRNoRepeatNGramLogitProcessor'
    )

    def __init__(
        self,
        settings: UnlimitedOCRSettings | None = None,
        transport: Callable[[dict, int], dict] | None = None,
    ) -> None:
        self.settings = settings or UnlimitedOCRSettings()
        self.transport = transport or self._post_json

    def build_request(self, image_data_urls: list[str], prompt: str = "Multi page parsing.") -> dict:
        content = [{"type": "text", "text": f"<image>{prompt}"}]
        content.extend({"type": "image_url", "image_url": {"url": url}} for url in image_data_urls)
        return {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "stream": False,
            "max_tokens": self.settings.max_length,
            "images_config": {"image_mode": self.settings.image_mode},
            "custom_logit_processor": self.NO_REPEAT_PROCESSOR,
            "custom_params": {
                "ngram_size": self.settings.ngram_size,
                "window_size": self.settings.ngram_window,
            },
        }

    def health_check(self) -> dict:
        url = f"{self.settings.endpoint.rstrip('/')}/v1/models"
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=10) as response:
                data = loads(response.read().decode())
                return {"ok": True, "models": data.get("data", [])}
        except (TimeoutError, OSError, HTTPError) as exc:
            return {"ok": False, "error": str(exc)}

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        image_data_urls = self._pdf_to_data_urls(content)
        try:
            payload = self.transport(self.build_request(image_data_urls), self.settings.timeout_seconds)
        except HTTPError as exc:
            status = exc.code
            if status in (503, 504):
                raise OCRProviderError(f"Unlimited-OCR service unavailable (HTTP {status})") from exc
            raise OCRProviderError(f"Unlimited-OCR request failed (HTTP {status})") from exc
        except TimeoutError as exc:
            raise OCRProviderError("Unlimited-OCR request timed out") from exc
        except OSError as exc:
            raise OCRProviderError("Unlimited-OCR endpoint unavailable") from exc
        text = self._response_text(payload)
        return OCRDocument(
            tuple(
                OCRPage(page=page, text=text if page == 1 else "", confidence=0.0 if not text else 1.0)
                for page in range(1, page_count + 1)
            )
        )

    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        return [
            OCRPageQuality(page.page_no, page.confidence, len(page.text))
            for page in self.recognize(content, page_count).pages
        ]

    def _pdf_to_data_urls(self, content: bytes) -> list[str]:
        try:
            import fitz

            document = fitz.open(stream=content, filetype="pdf")
            if len(document) == 0:
                raise OCRProviderError("PDF has no pages", retryable=False)
            urls = []
            matrix = fitz.Matrix(self.settings.dpi / 72, self.settings.dpi / 72)
            for page in document:
                image = page.get_pixmap(matrix=matrix, alpha=False).tobytes("png")
                urls.append(f"data:image/png;base64,{b64encode(image).decode('ascii')}")
            document.close()
            return urls
        except OCRProviderError:
            raise
        except (ImportError, RuntimeError, ValueError) as exc:
            raise OCRProviderError("PDF page rendering failed", retryable=False) from exc

    def _post_json(self, payload: dict, timeout: int) -> dict:
        url = f"{self.settings.endpoint.rstrip('/')}/v1/chat/completions"
        request = Request(url, data=dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            return loads(response.read().decode())

    @staticmethod
    def _response_text(payload: dict) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OCRProviderError("Unlimited-OCR returned invalid response", retryable=False) from exc
        return content if isinstance(content, str) else str(content)


# ── Mock Provider ────────────────────────────────────────────────

class MockOCRProvider:
    def __init__(
        self,
        qualities: list[OCRPageQuality] | None = None,
        error: OCRProviderError | None = None,
    ) -> None:
        self.qualities = qualities
        self.error = error
        self.calls = 0

    def recognize(self, content: bytes, page_count: int) -> OCRDocument:
        self.calls += 1
        if self.error is not None:
            raise self.error
        pages = []
        for page in range(1, page_count + 1):
            pages.append(OCRPage(page_no=page, text=f"mock page {page} content (100 chars) " * 2, confidence=0.95))
        return OCRDocument(pages=tuple(pages))

    def inspect(self, content: bytes, page_count: int) -> list[OCRPageQuality]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.qualities or [OCRPageQuality(page, 0.95, 100) for page in range(1, page_count + 1)]


# ── Provider Factory ──────────────────────────────────────────────

class OCRProviderName(str):
    RAPID = "rapid"
    UNLIMITED = "unlimited"
    MOCK = "mock"


def create_ocr_provider(
    provider: str | None = None,
    unlimited_settings: UnlimitedOCRSettings | None = None,
    rapid_settings: RapidOCRSettings | None = None,
    mock_qualities: list[OCRPageQuality] | None = None,
    mock_error: OCRProviderError | None = None,
) -> "OCRProvider":
    """根据环境变量 OCR_PROVIDER 或显式参数创建对应 Provider。

    环境变量优先级：
      1. 显式参数 provider
      2. 环境变量 OCR_PROVIDER
      3. 默认 "mock"（开发和测试环境）

    可选值："rapid" | "unlimited" | "mock"
    """
    choice = (provider or getenv("OCR_PROVIDER", "mock")).lower()

    if choice == "rapid":
        return RapidOCRProvider(rapid_settings or RapidOCRSettings.from_env())
    if choice == "unlimited":
        return UnlimitedOCRProvider(unlimited_settings or UnlimitedOCRSettings.from_env())
    return MockOCRProvider(mock_qualities, mock_error)


__all__ = [
    "OCRProvider",
    "OCRProviderError",
    "OCRProviderName",
    "OCRPageQuality",
    "OCRPage",
    "OCRDocument",
    "RapidOCRSettings",
    "RapidOCRProvider",
    "UnlimitedOCRSettings",
    "UnlimitedOCRProvider",
    "MockOCRProvider",
    "create_ocr_provider",
]