"""The files uploaded from the computer in a conversation, kept in the cache between turns.

A file's text arrives once, with the turn it is attached to. The cache holds it for the turns after
that, so it never enters the database, and forgets it when the conversation goes quiet.
"""

from uuid import UUID

from sparkth.lib.cache import CacheService, get_cache_service
from sparkth.lib.i18n import _
from sparkth.lib.settings import get_settings
from sparkth.plugins.compose.constants import (
    COMPOSE_PLUGIN_NAME,
    MAX_COMBINED_UPLOAD_MB,
    UPLOADED_FILES_TTL_SECONDS,
)
from sparkth.plugins.compose.exceptions import UploadedFilesTooLarge
from sparkth.plugins.compose.schemas import UploadedFile


def _get_cache() -> CacheService:
    settings = get_settings()
    return get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL)


def _get_cache_key(conversation_uuid: UUID) -> str:
    return _get_cache().make_key(COMPOSE_PLUGIN_NAME, "files", str(conversation_uuid))


async def get_uploaded_files(conversation_uuid: UUID) -> list[UploadedFile]:
    """Return the conversation's uploaded files, oldest first.

    There are none once they have expired, or when the cache can't be reached.
    """
    cached_files = await _get_cache().get_json(_get_cache_key(conversation_uuid)) or []
    return [UploadedFile.model_validate(file) for file in cached_files]


async def add_uploaded_files(conversation_uuid: UUID, new_files: list[UploadedFile]) -> list[UploadedFile]:
    """Add ``new_files`` to the conversation's existing files and return them all, oldest first.

    A new file replaces an existing one of the same name, so a retried turn or an edited file is
    never kept twice. Every call keeps the files for another full period, so they last as long as
    the conversation is in use. When the cache can't be reached, the new files are returned but not
    kept.

    Raises:
        UploadedFilesTooLarge: ``new_files`` would take the conversation's files' text over the limit. Nothing
            is kept.
    """
    existing_files = await get_uploaded_files(conversation_uuid)
    new_names = {file.name for file in new_files}
    files = [file for file in existing_files if file.name not in new_names] + new_files
    if new_files and sum(len(file.text) for file in files) > MAX_COMBINED_UPLOAD_MB * 1024 * 1024:
        raise UploadedFilesTooLarge(
            _("The files in this conversation can total at most {limit_mb} MB.").format(limit_mb=MAX_COMBINED_UPLOAD_MB)
        )
    if files:
        await _get_cache().set_json(
            _get_cache_key(conversation_uuid), [file.model_dump() for file in files], UPLOADED_FILES_TTL_SECONDS
        )
    return files
