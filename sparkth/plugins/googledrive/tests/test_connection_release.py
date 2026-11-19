"""Folder sync and file ingestion hold no database connection while slow work runs.

A session with an open transaction keeps a pooled connection checked out, so each
test asserts that no transaction is open at the moment the slow step starts.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import partial
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib import db
from sparkth.plugins.googledrive.constants import GOOGLE_DRIVE_PLUGIN_NAME
from sparkth.plugins.googledrive.models import DriveFile, DriveFolder, DriveOAuthToken
from sparkth.plugins.googledrive.utils import _process_single_file

BASE = f"/api/v1/{GOOGLE_DRIVE_PLUGIN_NAME}"
_REAL_SESSION_SCOPE = db.session_scope


@asynccontextmanager
async def _recording_session_scope(opened: list[AsyncSession]) -> AsyncGenerator[AsyncSession]:
    """Open a real session and remember it in ``opened``."""
    async with _REAL_SESSION_SCOPE() as session:
        opened.append(session)
        yield session


async def _record_open_transaction(sessions: list[AsyncSession], seen: list[bool], *_args: object) -> MagicMock:
    """Append whether any of ``sessions`` has a transaction open right now."""
    seen.append(any(session.in_transaction() for session in sessions))
    return MagicMock(new_chunks=1, reused_chunks=0)


async def _download_and_record(session: AsyncSession, seen: list[bool], *_args: object) -> bytes:
    """Append whether ``session`` has a transaction open right now, then return file bytes."""
    seen.append(session.in_transaction())
    return b"file-bytes"


def _build_drive_client_mock() -> AsyncMock:
    """Return a Drive client mock that reports one folder holding one file."""
    client = AsyncMock()
    client.get_folder.return_value = {"id": "new_drive_folder_id", "name": "My Folder", "parents": ["root"]}
    client.list_files.return_value = {
        "files": [{"id": "new_file_1", "name": "synced.pdf", "mimeType": "application/pdf", "size": "512"}]
    }
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client


async def _post_and_record_transaction_at_ingestion_start(
    drive_client: AsyncClient, url: str, json: dict[str, str] | None = None
) -> list[bool]:
    """POST to ``url`` and return whether a request session was mid-transaction when ingestion started."""
    request_sessions: list[AsyncSession] = []
    seen: list[bool] = []
    with (
        patch.object(db, "session_scope", partial(_recording_session_scope, request_sessions)),
        patch("sparkth.plugins.googledrive.routes.folders.GoogleDriveClient") as client_cls,
        patch(
            "sparkth.plugins.googledrive.routes.folders.process_folder_rag",
            new=AsyncMock(side_effect=partial(_record_open_transaction, request_sessions, seen)),
        ),
    ):
        client_cls.return_value = _build_drive_client_mock()
        client_cls.FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
        response = await drive_client.post(url, json=json)

    assert response.status_code == status.HTTP_200_OK
    assert request_sessions
    return seen


async def test_refresh_holds_no_transaction_when_ingestion_starts(
    drive_client: AsyncClient,
    test_folder: DriveFolder,
    test_oauth_token: DriveOAuthToken,
    mock_valid_access_token: None,
) -> None:
    seen = await _post_and_record_transaction_at_ingestion_start(
        drive_client, f"{BASE}/folders/{test_folder.id}/refresh"
    )

    assert seen == [False]


async def test_sync_holds_no_transaction_when_ingestion_starts(
    drive_client: AsyncClient,
    test_oauth_token: DriveOAuthToken,
    mock_valid_access_token: None,
) -> None:
    seen = await _post_and_record_transaction_at_ingestion_start(
        drive_client, f"{BASE}/folders/sync", {"drive_folder_id": "new_drive_folder_id"}
    )

    assert seen == [False]


async def test_file_session_holds_no_transaction_during_download_and_ingest(
    session: AsyncSession, test_file: DriveFile
) -> None:
    during_download: list[bool] = []
    during_ingest: list[bool] = []

    with (
        patch(
            "sparkth.plugins.googledrive.utils._download_file",
            new=AsyncMock(side_effect=partial(_download_and_record, session, during_download)),
        ),
        patch(
            "sparkth.plugins.googledrive.utils.ingest_document",
            new=AsyncMock(side_effect=partial(_record_open_transaction, [session], during_ingest)),
        ),
    ):
        await _process_single_file(test_file, test_file.user_id, "tok", session)

    assert during_download == [False]
    assert during_ingest == [False]
