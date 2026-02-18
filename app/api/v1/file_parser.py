import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pypdf import PdfReader

from app.api.v1.auth import get_current_user
from app.models.user import User

router: APIRouter = APIRouter()

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB
ALLOWED_TYPES = {
    "text/plain",
    "application/pdf",
}


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


@router.post("/upload")
async def upload_text(current_user: User = Depends(get_current_user), file: UploadFile = File(...)) -> JSONResponse:
    if not current_user or not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated.")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .pdf files are supported",
        )

    content = await file.read()
    size = len(content)

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 30MB limit",
        )

    if file.content_type == "text/plain":
        text = await parse_txt(content)

    elif file.content_type == "application/pdf":
        text = await parse_pdf(content)

    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    return JSONResponse(
        {
            "filename": file.filename,
            "length": len(text),
            "text": text,
        }
    )
