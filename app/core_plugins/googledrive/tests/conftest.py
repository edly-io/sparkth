"""Fixtures for Google Drive plugin tests.

Shared fixtures (``session``, ``engine``, the generic test environment, the
autouse cache/email stubs, …) come from :mod:`app.testing`, registered globally
as a pytest plugin by the root ``conftest.py``. This file only adds Google
Drive-specific pieces: route registration, test data, and mocks. All handlers
are async, so tests use the shared async ``session`` fixture throughout.
"""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.googledrive.routes import router as drive_router
from app.lib.db import get_async_session
from app.main import app
from app.models.drive import DriveFile, DriveFolder, DriveOAuthToken
from app.models.user import User
from app.rag.config import RAGSettings

# Register Drive routes on the app (normally done by plugin lifespan)
_DRIVE_PREFIX = "/api/v1/googledrive"
_drive_routes_registered = False


def _ensure_drive_routes() -> None:
    global _drive_routes_registered
    if _drive_routes_registered:
        return
    existing = {getattr(r, "path", None) for r in app.routes}
    if f"{_DRIVE_PREFIX}/folders" not in existing:
        app.include_router(drive_router, prefix=_DRIVE_PREFIX, tags=["Google Drive"])
    _drive_routes_registered = True


_ensure_drive_routes()


@pytest.fixture(autouse=True)
def _default_rag_settings() -> Generator[None, None, None]:
    """Patch get_rag_settings in utils so the local .env does not affect tests."""
    mock_settings = MagicMock(spec=RAGSettings)
    mock_settings.RAG_MAX_FILE_SIZE_MB = 50
    mock_settings.RAG_CONCURRENCY = 1
    with patch("app.core_plugins.googledrive.utils.get_rag_settings", return_value=mock_settings):
        yield


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user in the shared test database."""
    user = User(
        name="Drive Test User",
        username="driveuser",
        email="drive@example.com",
        hashed_password="fakehashedpassword",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_oauth_token(session: AsyncSession, test_user: User) -> DriveOAuthToken:
    """Create a test OAuth token record in the shared test database."""
    from app.core_plugins.googledrive.oauth import encrypt_token

    token = DriveOAuthToken(
        user_id=cast(int, test_user.id),
        access_token_encrypted=encrypt_token("fake_access_token"),
        refresh_token_encrypted=encrypt_token("fake_refresh_token"),
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        scopes="https://www.googleapis.com/auth/drive.file",
    )
    session.add(token)
    await session.flush()
    await session.refresh(token)
    return token


@pytest.fixture
async def test_folder(session: AsyncSession, test_user: User) -> DriveFolder:
    """Create a test synced folder in the shared test database."""
    folder = DriveFolder(
        user_id=cast(int, test_user.id),
        drive_folder_id="drive_folder_abc123",
        drive_folder_name="Test Folder",
        drive_parent_id=None,
        last_synced_at=datetime.now(timezone.utc),
        sync_status="synced",
    )
    session.add(folder)
    await session.flush()
    await session.refresh(folder)
    return folder


@pytest.fixture
async def test_file(session: AsyncSession, test_user: User, test_folder: DriveFolder) -> DriveFile:
    """Create a test drive file in the shared test database."""
    drive_file = DriveFile(
        folder_id=cast(int, test_folder.id),
        user_id=cast(int, test_user.id),
        drive_file_id="drive_file_xyz789",
        name="test_document.pdf",
        mime_type="application/pdf",
        size=1024,
        md5_checksum="abc123md5",
        modified_time=datetime.now(timezone.utc),
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(drive_file)
    await session.flush()
    await session.refresh(drive_file)
    return drive_file


@pytest.fixture
def mock_drive_credentials() -> Generator[None, None, None]:
    """Mock Google Drive OAuth credentials."""
    creds = ("fake_client_id", "fake_client_secret", "http://localhost/callback")
    with (
        patch("app.core_plugins.googledrive.routes.oauth.get_drive_credentials", return_value=creds),
        patch("app.core_plugins.googledrive.routes.folders.get_drive_credentials", return_value=creds),
        patch("app.core_plugins.googledrive.routes.files.get_drive_credentials", return_value=creds),
    ):
        yield


@pytest.fixture
def mock_valid_access_token() -> Generator[None, None, None]:
    """Mock get_valid_access_token to return a fake token."""
    with (
        patch("app.core_plugins.googledrive.routes.oauth.get_valid_access_token", return_value="fake_access_token"),
        patch("app.core_plugins.googledrive.routes.folders.get_valid_access_token", return_value="fake_access_token"),
        patch("app.core_plugins.googledrive.routes.files.get_valid_access_token", return_value="fake_access_token"),
    ):
        yield


@pytest.fixture
async def drive_client(
    session: AsyncSession,
    test_user: User,
    mock_drive_credentials: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with the shared async session and Drive auth overridden.

    All Drive route handlers are async, so overriding ``get_async_session`` with
    the shared ``session`` fixture lets handlers, data fixtures, and test-body
    assertions all operate on the same session/transaction.
    """

    async def get_async_session_override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def get_user_override() -> User:
        return test_user

    app.dependency_overrides[get_async_session] = get_async_session_override
    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_async_session, None)
    app.dependency_overrides.pop(get_current_user, None)
