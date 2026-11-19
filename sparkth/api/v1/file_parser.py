import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from pypdf import PdfReader

from sparkth.lib.auth import get_current_user_id
from sparkth.lib.i18n import _
from sparkth.lib.permissions import FILE_UPLOAD
from sparkth.lib.permissions.scopes import USER

router: APIRouter = APIRouter()

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB
ALLOWED_TYPES = {
    "text/plain",
    "application/pdf",
}


class UploadResponse(BaseModel):
    filename: str | None
    length: int
    text: str


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

    content = await file.read()
    size = len(content)

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=_("File size exceeds 30MB limit"),
        )

    if file.content_type == "text/plain":
        text = await parse_txt(content)

    elif file.content_type == "application/pdf":
        text = await parse_pdf(content)

    else:
        raise HTTPException(status_code=400, detail=_("Unsupported file type"))

    return UploadResponse(filename=file.filename, length=len(text), text=text)
