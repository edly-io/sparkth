"""Column types shared by the models."""

import json
from typing import Any

from sqlalchemy import Dialect, Text
from sqlalchemy.types import TypeDecorator

from sparkth.core.config import get_settings
from sparkth.core.encryption import EncryptionService, get_encryption_service


def _cipher() -> EncryptionService:
    return get_encryption_service(get_settings().ENCRYPTION_KEY)


class EncryptedJSON(TypeDecorator[dict[str, Any]]):
    """A JSON object stored encrypted with ``ENCRYPTION_KEY``; a value that won't decrypt raises ``ValueError``."""

    # The column type the database actually stores: the encrypted text.
    impl = Text
    # Safe for SQLAlchemy to cache statements using this type: it has no per-instance state.
    cache_ok = True

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Dialect) -> str | None:
        return None if value is None else _cipher().encrypt(json.dumps(value))

    def process_result_value(self, value: str | None, dialect: Dialect) -> dict[str, Any] | None:
        return None if value is None else json.loads(_cipher().decrypt(value))
