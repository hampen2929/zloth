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

    def test_encrypted_value_differs_from_plaintext(self, crypto_service: CryptoService) -> None:
        """Test that encrypted value is different from plaintext."""
        plaintext = "my-secret-api-key"
        encrypted = crypto_service.encrypt(plaintext)
        assert encrypted != plaintext

    def test_same_key_produces_consistent_encryption(self) -> None:
        """Test that same encryption key derives the same Fernet key."""
        key = "consistent-encryption-key"
        service1 = CryptoService(key)
        service2 = CryptoService(key)

        plaintext = "test-value"
        encrypted = service1.encrypt(plaintext)
        # Should be able to decrypt with another instance using same key
        decrypted = service2.decrypt(encrypted)
        assert decrypted == plaintext

    def test_different_keys_cannot_decrypt(self) -> None:
        """Test that different encryption keys cannot decrypt each other's data."""
        service1 = CryptoService("key-one")
        service2 = CryptoService("key-two")

        plaintext = "secret-data"
        encrypted = service1.encrypt(plaintext)

        with pytest.raises(InvalidToken):
            service2.decrypt(encrypted)

    def test_encrypt_empty_string(self, crypto_service: CryptoService) -> None:
        """Test encryption of empty string."""
        original = ""
        encrypted = crypto_service.encrypt(original)
        decrypted = crypto_service.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_unicode_content(self, crypto_service: CryptoService) -> None:
        """Test encryption of unicode content."""
        original = "APIキー: sk-test-12345-日本語"
        encrypted = crypto_service.encrypt(original)
        decrypted = crypto_service.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_long_content(self, crypto_service: CryptoService) -> None:
        """Test encryption of long content."""
        original = "x" * 10000  # 10KB of data
        encrypted = crypto_service.encrypt(original)
        decrypted = crypto_service.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_special_characters(self, crypto_service: CryptoService) -> None:
        """Test encryption with special characters."""
        original = "key!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = crypto_service.encrypt(original)
        decrypted = crypto_service.decrypt(encrypted)
        assert decrypted == original

    def test_invalid_ciphertext_raises_error(self, crypto_service: CryptoService) -> None:
        """Test that invalid ciphertext raises InvalidToken."""
        with pytest.raises(InvalidToken):
            crypto_service.decrypt("not-valid-encrypted-data")

    def test_tampered_ciphertext_raises_error(self, crypto_service: CryptoService) -> None:
        """Test that tampered ciphertext raises InvalidToken."""
        encrypted = crypto_service.encrypt("original-value")
        # Tamper with the encrypted data
        tampered = encrypted[:-5] + "XXXXX"
        with pytest.raises(InvalidToken):
            crypto_service.decrypt(tampered)

    def test_auto_generate_key_when_empty(self) -> None:
        """Test that empty encryption key generates a random one."""
        service = CryptoService("")
        plaintext = "test-value"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

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
