""" crypto for git privacy"""
import sys
from base64 import b64encode, b64decode
import hashlib
import hmac

from nacl import pwhash, secret, utils


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

    def encrypt(self, data: str) -> bytes:
        return self.__box.encrypt(str(data).encode('utf-8'))

    def decrypt(self, data: bytes) -> str:
        decrypted_data = self.__box.decrypt(data)
        return decrypted_data.decode('utf-8')

    def hmac(self, data: str) -> str:
        mac = hmac.digest(self.__mackey, data.encode('utf-8'), 'SHA256')
        return b64encode(mac).decode('utf-8')


def generate_salt() -> str:
    """Generate and return base64url encoded salt."""
    return b64encode(utils.random(pwhash.scrypt.SALTBYTES)).decode('utf-8')
