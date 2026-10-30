"""Public API for the symmetric-encryption service.

Import ``get_encryption_service`` (and ``EncryptionService``, ``mask_secret``) from here instead of
reaching into ``sparkth.core.encryption`` directly. It encrypts stored secrets — such
as LLM API keys — at rest with Fernet. Implementation lives in
``sparkth/core/encryption.py``.
"""

from sparkth.core.encryption import EncryptionService, get_encryption_service, mask_secret

__all__ = ["EncryptionService", "get_encryption_service", "mask_secret"]
