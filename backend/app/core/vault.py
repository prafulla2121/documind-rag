"""
Secure Vault — symmetric encryption for API keys and sensitive user data.
Uses Fernet (AES-128 in CBC mode with HMAC-SHA256).
"""
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.core.config import settings

logger = logging.getLogger(__name__)

class KeyVault:
    """
    Handles encryption and decryption of sensitive strings.
    Initializes with the ENCRYPTION_KEY from settings.
    """
    def __init__(self, key: str = None):
        self.key = key or settings.ENCRYPTION_KEY
        try:
            # Ensure the key is valid for Fernet (must be 32 url-safe base64-encoded bytes)
            # If the key is just a plain string, we derive a proper key from it.
            if len(self.key) != 44:  # standard Fernet key length
                logger.info("Deriving secure Fernet key from provided string...")
                salt = b'documind_static_salt' # In production, use a dynamic salt per user or a fixed system salt
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                derived_key = base64.urlsafe_b64encode(kdf.derive(self.key.encode()))
                self.fernet = Fernet(derived_key)
            else:
                self.fernet = Fernet(self.key.encode())
        except Exception as e:
            logger.error(f"Failed to initialize KeyVault: {e}")
            raise RuntimeError("KeyVault initialization failed. Check ENCRYPTION_KEY.")

    def encrypt(self, plain_text: str) -> str:
        """Encrypts a string and returns the base64 encoded ciphertext."""
        if not plain_text:
            return ""
        return self.fernet.encrypt(plain_text.encode()).decode()

    def decrypt(self, cipher_text: str) -> str:
        """Decrypts a base64 encoded ciphertext and returns the plain text."""
        if not cipher_text:
            return ""
        try:
            return self.fernet.decrypt(cipher_text.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ""

# Singleton instance
vault = KeyVault()
