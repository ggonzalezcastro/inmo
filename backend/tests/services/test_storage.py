"""
Unit tests for the storage layer (VolumeDriver, signing, validation).

Run without Docker:
    .venv/bin/python -m pytest tests/services/test_storage.py -v --noconftest
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.storage.volume_driver import VolumeDriver
from app.services.storage.signing import sign_download_token, verify_download_token
from app.services.storage.validation import (
    FileValidationError,
    validate_upload,
    detect_mime,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run a coroutine synchronously (no pytest-asyncio needed)."""
    return asyncio.run(coro)


class MockUploadFile:
    def __init__(
        self,
        data: bytes,
        content_type: str = "application/octet-stream",
        filename: str = "test.bin",
    ):
        self._data = data
        self.content_type = content_type
        self.filename = filename

    async def read(self, n: int = -1) -> bytes:
        return self._data[:n] if n > 0 else self._data


# ---------------------------------------------------------------------------
# TestVolumeDriver
# ---------------------------------------------------------------------------

class TestVolumeDriver:

    def test_upload_and_head(self, tmp_path: Path) -> None:
        driver = VolumeDriver(str(tmp_path))
        data = b"hello storage"
        expected_sha = hashlib.sha256(data).hexdigest()

        stored = run(driver.upload(data, "a/b/file.txt", "text/plain"))

        assert stored.key == "a/b/file.txt"
        assert stored.size_bytes == len(data)
        assert stored.sha256 == expected_sha

        meta = run(driver.head("a/b/file.txt"))
        assert meta.size_bytes == len(data)
        assert meta.sha256 == expected_sha

    def test_upload_atomic(self, tmp_path: Path) -> None:
        driver = VolumeDriver(str(tmp_path))
        run(driver.upload(b"atomic write", "docs/test.pdf", "application/pdf"))

        # No .tmp files should remain
        tmp_files = list(tmp_path.rglob("*.tmp"))
        assert tmp_files == [], f"Leftover .tmp files: {tmp_files}"

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        driver = VolumeDriver(str(tmp_path))
        with pytest.raises(ValueError, match="Unsafe storage key"):
            run(driver.upload(b"evil", "../etc/passwd", "text/plain"))

    def test_stream(self, tmp_path: Path) -> None:
        driver = VolumeDriver(str(tmp_path))
        data = b"stream me " * 1000
        run(driver.upload(data, "stream/file.bin", "application/octet-stream"))

        async def _collect() -> bytes:
            gen = await driver.open_stream("stream/file.bin")
            chunks = []
            async for chunk in gen:
                chunks.append(chunk)
            return b"".join(chunks)

        result = asyncio.run(_collect())
        assert result == data

    def test_delete(self, tmp_path: Path) -> None:
        driver = VolumeDriver(str(tmp_path))
        run(driver.upload(b"deleteme", "to_delete.bin", "application/octet-stream"))

        run(driver.delete("to_delete.bin"))

        with pytest.raises(FileNotFoundError):
            run(driver.head("to_delete.bin"))


# ---------------------------------------------------------------------------
# TestSigning
# ---------------------------------------------------------------------------

class TestSigning:

    def _secret_patch(self):
        return patch(
            "app.services.storage.signing._get_secret",
            return_value=b"test-secret-key",
        )

    def test_sign_verify_roundtrip(self) -> None:
        with self._secret_patch():
            token = sign_download_token("42/7/doc.pdf", broker_id=42, ttl=300)
            result = verify_download_token(token)

        assert result["key"] == "42/7/doc.pdf"
        assert result["broker_id"] == 42

    def test_expired_token_rejected(self) -> None:
        with self._secret_patch():
            token = sign_download_token("some/key.pdf", broker_id=1, ttl=0)
            # Sleep 1 second so exp is in the past
            time.sleep(1)
            with pytest.raises(ValueError, match="expired"):
                verify_download_token(token)

    def test_tampered_token_rejected(self) -> None:
        with self._secret_patch():
            token = sign_download_token("real/key.pdf", broker_id=1, ttl=300)

        # Flip a character in the payload section
        payload_b64, sig_b64 = token.split(".", 1)
        # Modify payload by appending a character
        tampered = payload_b64[:-1] + ("A" if payload_b64[-1] != "A" else "B")
        tampered_token = tampered + "." + sig_b64

        with self._secret_patch():
            with pytest.raises(ValueError):
                verify_download_token(tampered_token)


# ---------------------------------------------------------------------------
# TestFileValidation
# ---------------------------------------------------------------------------

_PDF_MAGIC = b"%PDF-1.4 minimal"
_JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100
_RANDOM_BYTES = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"


class TestFileValidation:

    def test_pdf_accepted(self) -> None:
        f = MockUploadFile(_PDF_MAGIC, content_type="application/pdf", filename="doc.pdf")
        data, mime, sha = run(validate_upload(f, slot_key="__dev__"))
        assert mime == "application/pdf"
        assert len(data) == len(_PDF_MAGIC)
        assert sha == hashlib.sha256(_PDF_MAGIC).hexdigest()

    def test_jpeg_accepted(self) -> None:
        f = MockUploadFile(_JPEG_MAGIC, content_type="image/jpeg", filename="photo.jpg")
        data, mime, sha = run(validate_upload(f, slot_key="__dev__"))
        assert mime == "image/jpeg"

    def test_unknown_mime_rejected(self) -> None:
        f = MockUploadFile(_RANDOM_BYTES, content_type="application/octet-stream", filename="mystery.bin")
        with pytest.raises(FileValidationError) as exc_info:
            run(validate_upload(f, slot_key="__dev__"))
        assert exc_info.value.status_code == 400

    def test_oversize_rejected(self) -> None:
        from app.core.config import settings as core_settings
        max_bytes = core_settings.STORAGE_MAX_FILE_MB * 1024 * 1024
        # Create data slightly over the limit (1 byte over)
        oversized = b"A" * (max_bytes + 2)
        f = MockUploadFile(oversized, content_type="application/pdf", filename="big.pdf")
        with pytest.raises(FileValidationError) as exc_info:
            run(validate_upload(f, slot_key="__dev__"))
        assert exc_info.value.status_code == 413

    def test_empty_rejected(self) -> None:
        f = MockUploadFile(b"", content_type="application/pdf", filename="empty.pdf")
        with pytest.raises(FileValidationError) as exc_info:
            run(validate_upload(f, slot_key="__dev__"))
        assert exc_info.value.status_code == 400
