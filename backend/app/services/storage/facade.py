from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StoredFile
from app.services.storage.signing import sign_download_token, verify_download_token
from app.services.storage.volume_driver import VolumeDriver


@lru_cache(maxsize=1)
def _get_driver() -> VolumeDriver:
    if settings.STORAGE_DRIVER in ("railway_volume", "local"):
        base = (
            settings.STORAGE_VOLUME_PATH
            if settings.STORAGE_DRIVER == "railway_volume"
            else settings.STORAGE_LOCAL_PATH
        )
        return VolumeDriver(base)
    raise ValueError(f"Unknown STORAGE_DRIVER: {settings.STORAGE_DRIVER}")


class FileStorageService:
    @staticmethod
    async def upload(stream, key: str, content_type: str) -> StoredFile:
        return await _get_driver().upload(stream, key, content_type)

    @staticmethod
    async def open_stream(key: str):
        return await _get_driver().open_stream(key)

    @staticmethod
    async def delete(key: str) -> None:
        await _get_driver().delete(key)

    @staticmethod
    async def head(key: str) -> StoredFile:
        return await _get_driver().head(key)

    @staticmethod
    def sign_download_url(key: str, broker_id: int, base_url: str) -> str:
        token = sign_download_token(key, broker_id, settings.STORAGE_PRESIGN_TTL_SEC)
        return f"{base_url}/api/files/serve/{token}"

    @staticmethod
    def verify_download_token(token: str) -> dict:
        return verify_download_token(token)

    @staticmethod
    def make_key(broker_id: int, deal_id: int, doc_uuid: str, ext: str) -> str:
        """Construct a safe, non-enumerable storage key."""
        return f"{broker_id}/{deal_id}/{doc_uuid}.{ext.lstrip('.')}"
