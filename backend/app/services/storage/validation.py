"""
File validation for Deal document uploads.

Validates:
- MIME type (whitelist per slot, detected from file magic bytes — not trusting client header)
- File size (STORAGE_MAX_FILE_MB global cap)
- SHA-256 computed during streaming (for dedup/tampering detection)
- TODO: ClamAV antivirus hook (not implemented, placeholder)
"""
import hashlib

from fastapi import UploadFile

from app.core.config import settings
from app.services.deals.slots import ALLOWED_MIME_TYPES, SLOT_DEFINITIONS


class FileValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def detect_mime(data: bytes) -> str:
    """Detect MIME type from file magic bytes."""
    try:
        import magic
        return magic.from_buffer(data[:2048], mime=True)
    except ImportError:
        # Fallback: basic magic-byte sniffing for common types
        head = data[:8]
        if head[:4] == b"%PDF":
            return "application/pdf"
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if head[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if head[:4] in (b"RIFF",) and data[8:12] == b"WEBP":
            return "image/webp"
        return "application/octet-stream"


async def validate_upload(
    file: UploadFile,
    slot_key: str,
) -> tuple[bytes, str, str]:
    """
    Validate an uploaded file for a given slot.

    Returns: (file_bytes, detected_mime_type, sha256_hex)
    Raises: FileValidationError with clear message
    """
    max_bytes = settings.STORAGE_MAX_FILE_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise FileValidationError(
            f"Archivo demasiado grande. Máximo permitido: {settings.STORAGE_MAX_FILE_MB} MB",
            status_code=413,
        )

    if len(data) == 0:
        raise FileValidationError("El archivo está vacío")

    detected_mime = detect_mime(data)

    slot_def = SLOT_DEFINITIONS.get(slot_key)
    allowed_mimes = slot_def.mime_whitelist if slot_def else ALLOWED_MIME_TYPES

    if detected_mime not in allowed_mimes:
        raise FileValidationError(
            f"Tipo de archivo no permitido: {detected_mime}. "
            f"Formatos aceptados: {', '.join(sorted(allowed_mimes))}"
        )

    sha256 = hashlib.sha256(data).hexdigest()

    # TODO: ClamAV antivirus scan
    # _clam_scan(data)  # not implemented

    return data, detected_mime, sha256


_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


def get_file_extension(mime_type: str) -> str:
    """Return safe file extension for a given MIME type."""
    return _MIME_TO_EXT.get(mime_type, "bin")
