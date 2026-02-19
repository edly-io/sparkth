from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.logger import get_logger

logger = get_logger(__name__)


class EncryptionService:
    def __init__(self, encryption_key: str):
        try:
            self._cipher = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, plaintext: str) -> str:
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_text: str) -> str:
        try:
            decrypted_bytes = self._cipher.decrypt(encrypted_text.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or wrong encryption key")
            raise ValueError("Failed to decrypt: Invalid encryption key or corrupted data")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Decryption error: {e}")

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()


@lru_cache(maxsize=1)
def get_encryption_service(encryption_key: str) -> EncryptionService:
    return EncryptionService(encryption_key)
