"""Fixtures for Google Drive plugin tests.

Shared fixtures (``session``, ``engine``, the generic test environment, the
autouse cache/email stubs, …) come from :mod:`app.testing`, registered globally
as a pytest plugin by the root ``conftest.py``. This file only adds Google
Drive-specific pieces: test data and mocks. All handlers
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
from app.core_plugins.googledrive.config import GoogleDriveSettings
from app.core_plugins.googledrive.models import DriveFile, DriveFolder, DriveOAuthToken
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
def _default_ingestion_settings() -> Generator[None, None, None]:
    """Patch get_googledrive_settings in utils so the local .env does not affect tests."""
    mock_settings = MagicMock(spec=GoogleDriveSettings)
    mock_settings.INGESTION_MAX_FILE_SIZE_MB = 50
    mock_settings.INGESTION_CONCURRENCY = 1
    with patch("app.core_plugins.googledrive.utils.get_googledrive_settings", return_value=mock_settings):
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
    await session.commit()
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
    await session.commit()
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
    await session.commit()
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
    await session.commit()
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
    """AsyncClient with Drive auth overridden.

    Handlers open their own engine-backed session via the real ``session_scope`` on
    the same in-memory StaticPool database as the ``session`` fixture, so data seeded
    (and committed) through ``session`` is visible to handlers and vice versa. Only
    auth is faked here.
    """

    assert test_user.id is not None
    auth_user = User(
        id=test_user.id,
        name=test_user.name,
        username=test_user.username,
        email=test_user.email,
        hashed_password=test_user.hashed_password,
        is_superuser=test_user.is_superuser,
        email_verified=test_user.email_verified,
        email_verified_at=test_user.email_verified_at,
    )

    async def get_user_override() -> User:
        return auth_user

    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_current_user, None)
