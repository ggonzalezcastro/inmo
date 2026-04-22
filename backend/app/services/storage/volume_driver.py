import hashlib
import os
from pathlib import Path
from typing import AsyncIterator

import aiofiles
import aiofiles.os

from app.services.storage.base import StorageDriverBase, StoredFile

_CHUNK_SIZE = 64 * 1024  # 64 KB


class VolumeDriver(StorageDriverBase):
    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)

    def _resolve(self, key: str) -> Path:
        if ".." in key.split("/") or key.startswith("/"):
            raise ValueError(f"Unsafe storage key: {key!r}")
        return self.base_path / key

    async def upload(
        self,
        stream: bytes | AsyncIterator[bytes],
        key: str,
        content_type: str,
    ) -> StoredFile:
        dest = self._resolve(key)
        tmp = dest.with_suffix(dest.suffix + ".tmp")

        await aiofiles.os.makedirs(dest.parent, mode=0o700, exist_ok=True)

        digest = hashlib.sha256()
        size = 0

        async with aiofiles.open(tmp, "wb") as fh:
            if isinstance(stream, bytes):
                await fh.write(stream)
                digest.update(stream)
                size = len(stream)
            else:
                async for chunk in stream:
                    await fh.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)

        os.replace(tmp, dest)

        return StoredFile(
            key=key,
            size_bytes=size,
            sha256=digest.hexdigest(),
            content_type=content_type,
        )

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key!r}")

        async def _gen():
            async with aiofiles.open(path, "rb") as fh:
                while True:
                    chunk = await fh.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        return _gen()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)

    async def head(self, key: str) -> StoredFile:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key!r}")

        stat = path.stat()
        digest = hashlib.sha256()
        async with aiofiles.open(path, "rb") as fh:
            while True:
                chunk = await fh.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)

        return StoredFile(
            key=key,
            size_bytes=stat.st_size,
            sha256=digest.hexdigest(),
            content_type="application/octet-stream",
        )
