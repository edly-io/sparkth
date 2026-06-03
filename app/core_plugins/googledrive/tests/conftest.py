"""Fixtures for Google Drive plugin tests."""

import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import Settings
from app.core_plugins.googledrive.routes import router as drive_router
from app.lib.db import get_async_session, get_session
from app.main import app
from app.models.drive import DriveFile, DriveFolder, DriveOAuthToken
from app.models.user import User

# ---------------------------------------------------------------------------
# Shared named in-memory SQLite database
#
# The googledrive tests exercise both sync and async route handlers. SQLite's
# named in-memory databases (with ?cache=shared) let a pysqlite sync engine
# and an aiosqlite async engine connect to the same database, so test data
# written by the sync fixtures is visible to async handlers and vice versa.
# ---------------------------------------------------------------------------
_DRIVE_DB_NAME = f"sparkth_drive_{os.getpid()}"
_DRIVE_SYNC_URL = f"sqlite:///file:{_DRIVE_DB_NAME}?mode=memory&cache=shared&uri=true"
_DRIVE_ASYNC_URL = f"sqlite+aiosqlite:///file:{_DRIVE_DB_NAME}?mode=memory&cache=shared&uri=true"

# StaticPool pins a single underlying connection per engine for the whole
# session. That keeps the shared in-memory database alive (SQLite drops an
# in-memory DB when its last connection closes) and lets the sync and async
# engines see each other's committed data via the shared cache.
_drive_sync_engine = create_engine(
    _DRIVE_SYNC_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_drive_async_engine = create_async_engine(
    _DRIVE_ASYNC_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(_drive_sync_engine)

# Route registration
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


# Test isolation: truncate drive tables before every test
@pytest.fixture(autouse=True)
def _clean_drive_tables() -> Generator[None, None, None]:
    """Truncate drive-specific tables before each test for clean isolation."""
    with Session(_drive_sync_engine) as s:
        s.exec(delete(DriveOAuthToken))
        s.exec(delete(DriveFile))
        s.exec(delete(DriveFolder))
        s.exec(delete(User).where(User.username == "driveuser"))  # type: ignore[arg-type]
        s.commit()
    yield


# Autouse: RAG settings stub
@pytest.fixture(autouse=True)
def _default_rag_settings() -> Generator[None, None, None]:
    """Patch get_settings in utils so the local .env does not block test files.

    Tests that need a specific RAG_ALLOWED_EXTENSIONS value override this with
    their own inner patch() context manager.
    """
    mock_settings = MagicMock(spec=Settings)
    mock_settings.RAG_ALLOWED_EXTENSIONS = ""
    mock_settings.RAG_MAX_FILE_SIZE_MB = 50
    mock_settings.RAG_CONCURRENCY = 1
    with patch("app.core_plugins.googledrive.utils.get_settings", return_value=mock_settings):
        yield


# Test data fixtures
@pytest.fixture
def sync_session() -> Generator[Session, None, None]:
    """Override root conftest sync_session for googledrive tests.

    Uses the shared drive test database so sync helpers operate on the same
    data as route handlers.
    """
    with Session(_drive_sync_engine) as s:
        yield s


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session backed by the shared drive test database.

    Used by test_oauth.py to exercise the async oauth helper functions against
    the same data that the sync data fixtures create.
    """
    async with AsyncSession(_drive_async_engine) as s:
        yield s


@pytest.fixture
def test_user(sync_session: Session) -> User:
    """Create a test user in the shared drive test database."""
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
    """Create a test OAuth token record in the shared drive test database."""
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
    """Create a test synced folder in the shared drive test database."""
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
    """Create a test drive file in the shared drive test database."""
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


# Mocking fixtures
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


# HTTP test client
@pytest.fixture
async def drive_client(
    test_user: User,
    mock_drive_credentials: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with overridden session dependencies for Drive route tests.

    Both get_session (sync handlers) and get_async_session (async handlers)
    are overridden with sessions backed by the shared named in-memory SQLite
    database, so all route handlers see the same test data.
    """

    def get_session_override() -> Generator[Session, None, None]:
        with Session(_drive_sync_engine) as s:
            yield s

    async def get_async_session_override() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(_drive_async_engine) as s:
            yield s

    async def get_user_override() -> User:
        return test_user

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_async_session] = get_async_session_override
    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_async_session, None)
    app.dependency_overrides.pop(get_current_user, None)
