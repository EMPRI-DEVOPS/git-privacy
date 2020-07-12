from base64 import b64encode
from typing import Iterable, Optional

from nacl import secret, utils  # type: ignore
from nacl.encoding import Base64Encoder  # type: ignore
from nacl.exceptions import CryptoError  # type: ignore

from . import DecryptionProvider
from . import EncryptionProvider


class SecretBox(EncryptionProvider):
    """Wrapper for NaCl SecretBox."""
    def __init__(self, key: str) -> None:
        """Initialise SecretBox from a Base64-encoded key."""
        self._box = secret.SecretBox(
            key.encode('utf-8'),
            Base64Encoder,
        )

    def encrypt(self, data: str) -> str:
        """Encrypts data and returns an Base64-encoded string"""
        return self._box.encrypt(
            str(data).encode('utf-8'),
            encoder=Base64Encoder
        ).decode('utf-8')

    def decrypt(self, data: str) -> Optional[str]:
        try:
            return self._box.decrypt(
                str(data).encode('utf-8'),
                encoder=Base64Encoder
            ).decode('utf-8')
        except CryptoError:
            return None

    @staticmethod
    def generate_key() -> str:
        """Generate and return base64-encoded key."""
        key = utils.random(secret.SecretBox.KEY_SIZE)
        return b64encode(key).decode('utf-8')


class MultiSecretDecryptor(DecryptionProvider):
    """Decryptor supporting multiple decryption keys."""
    def __init__(self, keyarchive: Iterable[str]) -> None:
        """Initialise SecretBox from a Base64-encoded key."""
        self.__archive = tuple(
            map(SecretBox, keyarchive)
        )

    def decrypt(self, data: str) -> Optional[str]:
        """Attempt to decrypt data with any available key."""
        for box in self.__archive:
            res = box.decrypt(data)
            if res is not None:
                return res
        return None


class MultiSecretBox(MultiSecretDecryptor, SecretBox):
    """SecretBox supporting multiple decryption keys."""
    def __init__(self, key: str, keyarchive: Iterable[str]) -> None:
        SecretBox.__init__(self, key)
        MultiSecretDecryptor.__init__(self, keyarchive)

    def decrypt(self, data: str) -> Optional[str]:
        """Attempt to decrypt data with any available key."""
        res = SecretBox.decrypt(self, data)
        if res is not None:
            return res
        return MultiSecretDecryptor.decrypt(self, data)
