import pytest

from sparkth.core.encryption import EncryptionService


def test_reads_a_value_encrypted_with_an_older_key() -> None:
    old, new = EncryptionService.generate_key(), EncryptionService.generate_key()
    token = EncryptionService(old).encrypt("s3cret")

    assert EncryptionService(f"{new},{old}").decrypt(token) == "s3cret"


def test_encrypts_with_the_first_key() -> None:
    old, new = EncryptionService.generate_key(), EncryptionService.generate_key()
    token = EncryptionService(f"{new},{old}").encrypt("s3cret")

    assert EncryptionService(new).decrypt(token) == "s3cret"


def test_rejects_a_value_no_key_can_read() -> None:
    token = EncryptionService(EncryptionService.generate_key()).encrypt("s3cret")

    with pytest.raises(ValueError):
        EncryptionService(EncryptionService.generate_key()).decrypt(token)


def test_rejects_an_invalid_key_in_the_list() -> None:
    with pytest.raises(ValueError):
        EncryptionService(f"{EncryptionService.generate_key()},not-a-key")
