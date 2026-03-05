"""Fixtures for Google Drive plugin tests."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

from app.api.v1.auth import get_current_user
from app.core.db import get_session
from app.core_plugins.googledrive.routes import router as drive_router
from app.main import app
from app.models.drive import DriveFile, DriveFolder, DriveOAuthToken
from app.models.user import User

# Register Drive routes on the app (normally done by plugin lifespan)
_DRIVE_PREFIX = "/api/v1/googledrive"
_drive_routes_registered = False


def _ensure_drive_routes() -> None:
    global _drive_routes_registered
    if _drive_routes_registered:
        return
    existing = {r.path for r in app.routes}
    if f"{_DRIVE_PREFIX}/folders" not in existing:
        app.include_router(drive_router, prefix=_DRIVE_PREFIX, tags=["Google Drive"])
    _drive_routes_registered = True


_ensure_drive_routes()


@pytest.fixture
def test_user(sync_session: Session) -> User:
    """Create a test user in the database."""
    user = User(
        name="Drive Test User",
        username="driveuser",
        email="drive@example.com",
        hashed_password="fakehashedpassword",
    )
    sync_session.add(user)
    sync_session.commit()
    sync_session.refresh(user)
    return user


@pytest.fixture
def test_oauth_token(sync_session: Session, test_user: User) -> DriveOAuthToken:
    """Create a test OAuth token record."""
    from app.core_plugins.googledrive.oauth import encrypt_token

    token = DriveOAuthToken(
        user_id=cast(int, test_user.id),
        access_token_encrypted=encrypt_token("fake_access_token"),
        refresh_token_encrypted=encrypt_token("fake_refresh_token"),
        token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        scopes="https://www.googleapis.com/auth/drive.file",
    )
    sync_session.add(token)
    sync_session.commit()
    sync_session.refresh(token)
    return token


@pytest.fixture
def test_folder(sync_session: Session, test_user: User) -> DriveFolder:
    """Create a test synced folder."""
    folder = DriveFolder(
        user_id=cast(int, test_user.id),
        drive_folder_id="drive_folder_abc123",
        drive_folder_name="Test Folder",
        drive_parent_id=None,
        last_synced_at=datetime.now(timezone.utc),
        sync_status="synced",
    )
    sync_session.add(folder)
    sync_session.commit()
    sync_session.refresh(folder)
    return folder


@pytest.fixture
def test_file(sync_session: Session, test_user: User, test_folder: DriveFolder) -> DriveFile:
    """Create a test drive file."""
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
    sync_session.add(drive_file)
    sync_session.commit()
    sync_session.refresh(drive_file)
    return drive_file


@pytest.fixture
def mock_drive_credentials():
    """Mock Google Drive OAuth credentials."""
    with patch(
        "app.core_plugins.googledrive.routes.get_drive_credentials",
        return_value=("fake_client_id", "fake_client_secret", "http://localhost/callback"),
    ):
        yield


@pytest.fixture
def mock_valid_access_token():
    """Mock get_valid_access_token to return a fake token."""
    with patch(
        "app.core_plugins.googledrive.routes.get_valid_access_token",
        return_value="fake_access_token",
    ):
        yield


@pytest.fixture
async def drive_client(
    sync_session: Session,
    test_user: User,
    mock_drive_credentials: Any,
) -> AsyncClient:
    """AsyncClient with overridden session and auth for Drive route tests."""

    def get_session_override() -> Generator[Session, None, None]:
        yield sync_session

    async def get_user_override() -> User:
        return test_user

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
