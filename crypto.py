""" crypto for git privacy"""
import sys
import base64
import cryptography.exceptions
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class Crypto(object):
    """crypto stuff"""
    def __init__(self, salt, password):
        super(Crypto, self).__init__()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=base64.urlsafe_b64decode(salt),
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
        self.fernet = Fernet(key)

    def encrypt(self, data):
        """ Encrpyt data with password and salt """
        token = self.fernet.encrypt(str(data).encode('utf-8'))
        return token

    def decrypt(self, data):
        """ Decrypt data with password and salt
            To decrypt you need the same password
            and salt which was used for encryption"""
        try:
            decrypted_data = self.fernet.decrypt(data)
            return decrypted_data.decode('utf-8')
        except (cryptography.exceptions.InvalidSignature, cryptography.fernet.InvalidToken) as decryption_error:
            print("Decrypt error {}".format(decryption_error), file=sys.stderr)