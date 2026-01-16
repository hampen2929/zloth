"""Cryptography service for API key encryption."""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self, encryption_key: str):
        """Initialize with an encryption key.

        Args:
            encryption_key: Base key for encryption. If empty, generates a random one.
        """
        if not encryption_key:
            # Generate a random key for development
            encryption_key = Fernet.generate_key().decode()

        # Derive a proper Fernet key from the input
        self._fernet = self._create_fernet(encryption_key)

    def _create_fernet(self, key: str) -> Fernet:
        """Create a Fernet instance from a key string.

        Args:
            key: Key string (any length).

        Returns:
            Fernet instance.
        """
        # Use PBKDF2 to derive a proper key
        salt = b"dursor_salt_v1"  # Fixed salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(derived_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string.

        Args:
            plaintext: String to encrypt.

        Returns:
            Encrypted string (base64 encoded).
        """
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string.

        Args:
            ciphertext: Encrypted string (base64 encoded).

        Returns:
            Decrypted plaintext string.
        """
        decrypted = self._fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
