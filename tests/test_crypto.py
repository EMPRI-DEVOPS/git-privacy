import unittest
from nacl.exceptions import CryptoError

from gitprivacy import crypto

class CryptoTestCase(unittest.TestCase):
    def test_roundtrip(self):
        salt = crypto.generate_salt()
        c = crypto.Crypto(salt, "passw0rd")
        enc = c.encrypt("foobar")
        self.assertEqual(c.decrypt(enc), "foobar")

    def test_wrongpwd(self):
        salt = crypto.generate_salt()
        c = crypto.Crypto(salt, "passw0rd")
        c2 = crypto.Crypto(salt, "password")
        enc = c.encrypt("foobar")
        with self.assertRaises(CryptoError):
            c2.decrypt(enc)
