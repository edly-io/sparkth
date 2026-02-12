import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pypdf import PdfReader

router: APIRouter = APIRouter()

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB
ALLOWED_TYPES = {
    "text/plain",
    "application/pdf",
}


async def parse_txt(file: UploadFile) -> str:
    content = await file.read()
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


async def parse_pdf(file: UploadFile) -> str:
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))

    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text.strip()


@router.post("/upload")
async def upload_text(file: UploadFile = File(...)) -> JSONResponse:
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

    file.file.seek(0)

    if file.content_type == "text/plain":
        text = await parse_txt(file)

    elif file.content_type == "application/pdf":
        text = await parse_pdf(file)

    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    return JSONResponse(
        {
            "filename": file.filename,
            "length": len(text),
            "text": text,
        }
    )
