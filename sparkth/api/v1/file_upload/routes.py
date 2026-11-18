"""Endpoint that reads the text out of an uploaded .txt or .pdf file."""

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pypdf import PdfReader

from sparkth.api.v1.file_upload.constants import ALLOWED_TYPES, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from sparkth.api.v1.file_upload.schemas import UploadResponse
from sparkth.lib.auth import get_current_user_id
from sparkth.lib.i18n import _
from sparkth.lib.permissions import FILE_UPLOAD
from sparkth.lib.permissions.scopes import USER

router: APIRouter = APIRouter()


async def parse_txt(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


async def parse_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))

    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text.strip()


@router.post(
    "/upload",
    response_model=UploadResponse,
    dependencies=[Depends(FILE_UPLOAD.require_for_object(USER, get_current_user_id))],
)
async def upload_text(file: UploadFile = File(...)) -> UploadResponse:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=_("Only .txt and .pdf files are supported"),
        )

    # Reading one byte past the limit is enough to tell that a file is too large.
    content = await file.read(MAX_FILE_SIZE_BYTES + 1)

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=_("File size exceeds {limit_mb}MB limit").format(limit_mb=MAX_FILE_SIZE_MB),
        )

    if file.content_type == "text/plain":
        text = await parse_txt(content)

    elif file.content_type == "application/pdf":
        text = await parse_pdf(content)

    else:
        raise HTTPException(status_code=400, detail=_("Unsupported file type"))

    # A scanned PDF or an empty file gives nothing to send to the model.
    if not text.strip():
        raise HTTPException(status_code=400, detail=_("No text could be read from this file"))

    return UploadResponse(filename=file.filename, length=len(text), text=text)
