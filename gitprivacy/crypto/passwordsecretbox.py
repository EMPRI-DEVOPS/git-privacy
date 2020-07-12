from base64 import b64encode, b64decode

from nacl import pwhash, secret, utils  # type: ignore

from .secretbox import SecretBox


class PasswordSecretBox(SecretBox):
    """NaCl SecretBox with secret derived from password."""
    def __init__(self, salt: str, password: str) -> None:
        # pylint: disable=super-init-not-called
        enckey = self.derive_key(password, salt)
        self._box = secret.SecretBox(enckey)

    @staticmethod
    def derive_key(password: str, salt: str) -> bytes:
        return pwhash.scrypt.kdf(
            secret.SecretBox.KEY_SIZE,
            password.encode('utf-8'),
            b64decode(salt.encode('utf-8')),
            pwhash.SCRYPT_OPSLIMIT_INTERACTIVE,
            pwhash.SCRYPT_MEMLIMIT_INTERACTIVE,
        )

    @staticmethod
    def generate_salt() -> str:
        """Generate and return base64-encoded salt."""
        return b64encode(utils.random(pwhash.scrypt.SALTBYTES)).decode('utf-8')

    def _export_key(self) -> str:
        """Export Base64-encoded secret key."""
        return b64encode(bytes(self._box)).decode('utf-8')
