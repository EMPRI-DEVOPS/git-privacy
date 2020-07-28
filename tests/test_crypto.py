import unittest
from nacl.exceptions import CryptoError

from gitprivacy.crypto import (PasswordSecretBox, SecretBox, MultiSecretBox,
                               MultiSecretDecryptor)


class CryptoTestCase(unittest.TestCase):
    def test_roundtrip(self):
        salt = PasswordSecretBox.generate_salt()
        c = PasswordSecretBox(salt, "passw0rd")
        enc = c.encrypt("foobar")
        self.assertEqual(c.decrypt(enc), "foobar")
        # test keyfile interop
        mbox = MultiSecretBox(key=c._export_key(), keyarchive=[])
        self.assertEqual(mbox.decrypt(enc), "foobar")
        enc2 = mbox.encrypt("foobar")
        self.assertEqual(mbox.decrypt(enc2), "foobar")

    def test_wrongpwd(self):
        salt = PasswordSecretBox.generate_salt()
        c = PasswordSecretBox(salt, "passw0rd")
        c2 = PasswordSecretBox(salt, "password")
        enc = c.encrypt("foobar")
        self.assertEqual(c2.decrypt(enc), None)

    def test_keyarchive(self):
        key = SecretBox.generate_key()
        box = SecretBox(key=key)
        enc = box.encrypt("hello")
        self.assertEqual(box.decrypt(enc), "hello")
        mdec = MultiSecretDecryptor(keyarchive=[key])
        self.assertEqual(mdec.decrypt(enc), "hello")
        # different key in archive
        key2 = SecretBox.generate_key()
        mdec2 = MultiSecretDecryptor(keyarchive=[key2])
        self.assertEqual(mdec2.decrypt(enc), None)
        # both keys in archive
        mdec3 = MultiSecretDecryptor(keyarchive=[key2, key])
        self.assertEqual(mdec3.decrypt(enc), "hello")
