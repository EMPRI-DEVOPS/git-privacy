from base64 import b64encode, b64decode
import sys

from nacl import pwhash, secret, utils
from nacl.encoding import Base64Encoder


class Crypto():
    def __init__(self, salt: str, password: str) -> None:
        keys = pwhash.scrypt.kdf(
            secret.SecretBox.KEY_SIZE * 2,
            password.encode('utf-8'),
            b64decode(salt.encode('utf-8')),
            pwhash.SCRYPT_OPSLIMIT_INTERACTIVE,
            pwhash.SCRYPT_MEMLIMIT_INTERACTIVE,
        )
        enckey = keys[:secret.SecretBox.KEY_SIZE]
        self.__mackey = keys[secret.SecretBox.KEY_SIZE:]
        self.__box = secret.SecretBox(enckey)

    def encrypt(self, data: str) -> str:
        """Encrypts data and returns an Base64-encoded string"""
        return self.__box.encrypt(
            str(data).encode('utf-8'),
            encoder=Base64Encoder
        ).decode('utf-8')

    def decrypt(self, data: str) -> str:
        return self.__box.decrypt(
            str(data).encode('utf-8'),
            encoder=Base64Encoder
        ).decode('utf-8')


def generate_salt() -> str:
    """Generate and return base64-encoded salt."""
    return b64encode(utils.random(pwhash.scrypt.SALTBYTES)).decode('utf-8')
