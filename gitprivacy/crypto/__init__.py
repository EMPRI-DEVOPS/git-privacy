import abc
from typing import Optional


class EncryptionProvider(abc.ABC):
    """Abstract EncryptionProvider."""
    @abc.abstractmethod
    def encrypt(self, data: str) -> str:
        """Encrypts data and returns an Base64-encoded string"""
        pass

    @abc.abstractmethod
    def decrypt(self, data: str) -> Optional[str]:
        """Tries to decrypt Base64-encoded string and return plaintext or None."""
        pass


from .passwordsecretbox import PasswordSecretBox
