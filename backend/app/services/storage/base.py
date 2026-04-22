from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class StoredFile:
    key: str            # relative storage key e.g. "42/7/uuid.pdf"
    size_bytes: int
    sha256: str         # hex digest
    content_type: str


class StorageDriverBase:
    async def upload(
        self,
        stream: bytes | AsyncIterator[bytes],
        key: str,
        content_type: str,
    ) -> StoredFile: ...

    async def open_stream(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...

    async def head(self, key: str) -> StoredFile: ...
