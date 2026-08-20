from typing import Protocol

from contract_review.common.config import MinioSettings
from contract_review.domain import InMemoryObjectStorage


class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


class MinioObjectStorage:
    """MinIO 适配器；SDK 可选，导入工程时不强制启动外部服务。"""

    def __init__(self, settings: MinioSettings) -> None:
        self.settings = settings
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            try:
                from minio import Minio
            except ImportError as exc:
                raise RuntimeError("MinIO storage requires the 'minio' package") from exc
            self._client = Minio(
                self.settings.endpoint,
                access_key=self.settings.access_key,
                secret_key=self.settings.secret_key,
                secure=self.settings.secure,
            )
        return self._client

    def ensure_bucket(self) -> None:
        client = self._client_or_raise()
        if not client.bucket_exists(self.settings.bucket):
            client.make_bucket(self.settings.bucket)

    def put(self, key: str, content: bytes) -> None:
        from io import BytesIO

        self.ensure_bucket()
        self._client_or_raise().put_object(self.settings.bucket, key, BytesIO(content), len(content), content_type="application/pdf")

    def get(self, key: str) -> bytes:
        response = self._client_or_raise().get_object(self.settings.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


def create_storage(settings: MinioSettings | None = None) -> ObjectStorage:
    return MinioObjectStorage(settings or MinioSettings.from_env())


def create_memory_storage() -> InMemoryObjectStorage:
    return InMemoryObjectStorage()
