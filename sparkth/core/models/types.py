"""Column types shared by the models."""

import json
from typing import Any

from sqlalchemy import Dialect, Text
from sqlalchemy.types import TypeDecorator

from sparkth.core.config import get_settings
from sparkth.core.encryption import EncryptionService, get_encryption_service
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


def _cipher() -> EncryptionService:
    return get_encryption_service(get_settings().ENCRYPTION_KEY)


class EncryptedJSON(TypeDecorator[dict[str, Any]]):
    """A JSON object stored encrypted with ``ENCRYPTION_KEY``; a value that won't decrypt loads as ``{}``.

    Attributes:
        impl: The column type stored in the database: the encrypted text.
        cache_ok: Statements using this type can be cached; it holds no per-instance state.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Dialect) -> str | None:
        return None if value is None else _cipher().encrypt(json.dumps(value))

    def process_result_value(self, value: str | None, dialect: Dialect) -> dict[str, Any] | None:
        if value is None:
            return None
        try:
            config: dict[str, Any] = json.loads(_cipher().decrypt(value))
        except ValueError:
            logger.error("A stored plugin config could not be decrypted with ENCRYPTION_KEY; loading it empty")
            return {}
        return config
