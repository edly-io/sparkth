"""Public API for the symmetric-encryption service.

Import ``get_encryption_service`` (and ``EncryptionService``) from here instead of
reaching into ``sparkth.core.encryption`` directly. It encrypts stored secrets — such
as LLM API keys — at rest with Fernet. Implementation lives in
``sparkth/core/encryption.py``.
"""

from sparkth.core.encryption import EncryptionService, get_encryption_service

__all__ = ["EncryptionService", "get_encryption_service"]
