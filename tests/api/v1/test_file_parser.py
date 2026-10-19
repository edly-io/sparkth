import httpx

from sparkth.core.models.user import User
from sparkth.main import assemble_app


async def test_upload_returns_extracted_text(client: httpx.AsyncClient, current_user: User) -> None:
    response = await client.post("/api/v1/parser/upload", files={"file": ("notes.txt", b"hello", "text/plain")})

    assert response.status_code == 200
    assert response.json() == {"filename": "notes.txt", "length": 5, "text": "hello"}


def test_upload_response_is_published_in_the_schema() -> None:
    """The generated frontend types read the upload body from the published schema."""
    responses = assemble_app().openapi()["paths"]["/api/v1/parser/upload"]["post"]["responses"]

    assert responses["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/UploadResponse"
