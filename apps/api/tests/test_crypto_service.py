"""Tests for CryptoService - security-critical encryption/decryption."""

import pytest
from cryptography.fernet import InvalidToken

from zloth_api.services.crypto_service import CryptoService


class TestCryptoService:
    """Test suite for CryptoService."""

    def test_encrypt_decrypt_roundtrip(self, crypto_service: CryptoService) -> None:
        """Test that encryption followed by decryption returns original value."""
        original = "sk-test-api-key-12345"
        encrypted = crypto_service.encrypt(original)
        decrypted = crypto_service.decrypt(encrypted)
        assert decrypted == original

    def test_different_keys_cannot_decrypt(self) -> None:
        """Test that different encryption keys cannot decrypt each other's data."""
        service1 = CryptoService("key-one")
        service2 = CryptoService("key-two")

        plaintext = "secret-data"
        encrypted = service1.encrypt(plaintext)

        with pytest.raises(InvalidToken):
            service2.decrypt(encrypted)

    def test_invalid_ciphertext_raises_error(self, crypto_service: CryptoService) -> None:
        """Test that invalid ciphertext raises InvalidToken."""
        with pytest.raises(InvalidToken):
            crypto_service.decrypt("not-valid-encrypted-data")

    def test_each_encryption_produces_different_ciphertext(
        self, crypto_service: CryptoService
    ) -> None:
        """Test that encrypting same value twice produces different ciphertext.

        This is important for security - Fernet uses random IV for each encryption.
        """
        plaintext = "same-value"
        encrypted1 = crypto_service.encrypt(plaintext)
        encrypted2 = crypto_service.encrypt(plaintext)
        # Ciphertexts should be different due to random IV
        assert encrypted1 != encrypted2
        # But both should decrypt to same value
        assert crypto_service.decrypt(encrypted1) == plaintext
        assert crypto_service.decrypt(encrypted2) == plaintext
