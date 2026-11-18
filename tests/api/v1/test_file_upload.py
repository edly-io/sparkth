import io

import httpx
from pypdf import PdfWriter
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.permissions import SPARKTH_USER_ROLE, revoke_role
from sparkth.lib.permissions.scopes import USER
from sparkth.lib.testing import AuditEventsFetcher, grant_global_permission
from sparkth.main import assemble_app

UPLOAD = "/api/v1/parser/upload"
TEXT_FILE = {"file": ("notes.txt", b"hello", "text/plain")}
THREE_MB = 3 * 1024 * 1024


def blank_pdf() -> bytes:
    """A one-page PDF with no text on it."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def revoke_own_role(session: AsyncSession) -> None:
    await revoke_role(1, SPARKTH_USER_ROLE, USER, "1", session)
    await session.commit()


async def test_upload_returns_extracted_text(client: httpx.AsyncClient, current_user: User) -> None:
    response = await client.post("/api/v1/parser/upload", files={"file": ("notes.txt", b"hello", "text/plain")})

    assert response.status_code == 200
    assert response.json() == {"filename": "notes.txt", "length": 5, "text": "hello"}


def test_upload_response_is_published_in_the_schema() -> None:
    """The generated frontend types read the upload body from the published schema."""
    responses = assemble_app().openapi()["paths"]["/api/v1/parser/upload"]["post"]["responses"]

    assert responses["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/UploadResponse"


async def test_upload_refused_without_file_upload(
    client: httpx.AsyncClient, current_user: User, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await revoke_own_role(session)

    response = await client.post(UPLOAD, files=TEXT_FILE)

    assert response.status_code == 403
    event = (await audit_events())[-1]
    assert (event.category, event.action, event.target_id, event.error_detail) == (
        "permission",
        "denied",
        "file.upload",
        "scope=user:1",
    )


async def test_upload_allowed_by_a_global_grant(
    client: httpx.AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await revoke_own_role(session)
    await grant_global_permission(session, 1, "file.upload")
    await session.commit()

    response = await client.post(UPLOAD, files=TEXT_FILE)

    assert response.status_code == 200


async def test_upload_asks_an_anonymous_caller_to_log_in(client: httpx.AsyncClient) -> None:
    response = await client.post(UPLOAD, files=TEXT_FILE)

    assert response.status_code == 401


async def test_upload_accepts_a_file_of_3mb(client: httpx.AsyncClient, current_user: User) -> None:
    response = await client.post(UPLOAD, files={"file": ("notes.txt", b"a" * THREE_MB, "text/plain")})

    assert response.status_code == 200


async def test_upload_refuses_a_file_over_3mb(client: httpx.AsyncClient, current_user: User) -> None:
    response = await client.post(UPLOAD, files={"file": ("notes.txt", b"a" * (THREE_MB + 1), "text/plain")})

    assert response.status_code == 400
    assert response.json() == {"detail": "File size exceeds 3MB limit"}


async def test_upload_refuses_a_text_file_with_no_text(client: httpx.AsyncClient, current_user: User) -> None:
    response = await client.post(UPLOAD, files={"file": ("notes.txt", b"  \n\t ", "text/plain")})

    assert response.status_code == 400
    assert response.json() == {"detail": "No text could be read from this file"}


async def test_upload_refuses_a_pdf_with_no_text(client: httpx.AsyncClient, current_user: User) -> None:
    response = await client.post(UPLOAD, files={"file": ("scan.pdf", blank_pdf(), "application/pdf")})

    assert response.status_code == 400
    assert response.json() == {"detail": "No text could be read from this file"}
