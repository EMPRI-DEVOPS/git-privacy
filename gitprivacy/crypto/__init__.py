import abc
from typing import Optional


class DecryptionProvider(abc.ABC):
    """Abstract DecryptionProvider."""
    @abc.abstractmethod
    def decrypt(self, data: str) -> Optional[str]:
        """Tries to decrypt Base64-encoded string and return plaintext or None."""


class EncryptionProvider(DecryptionProvider):
    """Abstract EncryptionProvider."""
    @abc.abstractmethod
    def encrypt(self, data: str) -> str:
        """Encrypts data and returns an Base64-encoded string"""


from .secretbox import SecretBox as SecretBox
from .secretbox import MultiSecretBox as MultiSecretBox
from .secretbox import MultiSecretDecryptor as MultiSecretDecryptor
from .passwordsecretbox import PasswordSecretBox as PasswordSecretBox
