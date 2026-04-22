import uuid
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.config import settings
from app.middleware.auth import get_current_user
from app.services.storage.facade import FileStorageService
from app.services.storage.signing import verify_download_token
from app.services.storage.validation import validate_upload, FileValidationError, get_file_extension

router = APIRouter()


@router.get("/api/files/serve/{token}", tags=["files"])
async def serve_file(
    token: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        token_data = verify_download_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user_broker_id = current_user.get("broker_id")
    if token_data["broker_id"] != user_broker_id:
        raise HTTPException(status_code=403, detail="Access denied")

    key: str = token_data["key"]

    try:
        meta = await FileStorageService.head(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    stream = await FileStorageService.open_stream(key)

    filename = key.rsplit("/", 1)[-1]
    content_type = meta.content_type or "application/octet-stream"

    async def _generator():
        async for chunk in stream:
            yield chunk

    return StreamingResponse(
        _generator(),
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={filename!r}"},
    )


if settings.ENVIRONMENT != "production":

    @router.post("/api/files/_dev/test-upload", tags=["files"])
    async def dev_test_upload(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user),
    ):
        broker_id: int = current_user.get("broker_id", 0)

        try:
            data, mime_type, sha256 = await validate_upload(file, slot_key="__dev__")
        except FileValidationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message)

        ext = get_file_extension(mime_type)
        key = f"test/{uuid.uuid4().hex}.{ext}"

        stored = await FileStorageService.upload(data, key, mime_type)

        base_url = settings.BASE_URL if hasattr(settings, "BASE_URL") else ""
        signed_url = FileStorageService.sign_download_url(key, broker_id, base_url)

        return {
            "key": stored.key,
            "size_bytes": stored.size_bytes,
            "sha256": stored.sha256,
            "signed_url": signed_url,
        }
