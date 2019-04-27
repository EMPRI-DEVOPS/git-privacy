import unittest
from nacl.exceptions import CryptoError

from gitprivacy.crypto import PasswordSecretBox


class CryptoTestCase(unittest.TestCase):
    def test_roundtrip(self):
        salt = PasswordSecretBox.generate_salt()
        c = PasswordSecretBox(salt, "passw0rd")
        enc = c.encrypt("foobar")
        self.assertEqual(c.decrypt(enc), "foobar")

    def test_wrongpwd(self):
        salt = PasswordSecretBox.generate_salt()
        c = PasswordSecretBox(salt, "passw0rd")
        c2 = PasswordSecretBox(salt, "password")
        enc = c.encrypt("foobar")
        self.assertEqual(c2.decrypt(enc), None)
