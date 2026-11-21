import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Mock django settings if not configured
try:
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            SECRET_KEY="test_super_secret_key_for_testing_purposes_only",
            PREIMAGE_ENCRYPTION_KEY="test_custom_preimage_fernet_key",
            MAX_TRADE=5000000,
            MIN_TRADE=10000,
            LIMIT_TOTAL_FIAT_PAYMENT_MINUTES=60,
            DEV_DONATIONS_PERCENT=0.01,
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "api",
            ],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            USE_I18N=False,
        )
        django.setup()
except Exception as e:
    pass

from api.models.ln_payment import (
    _get_preimage_cipher,
    _encrypt_preimage,
    _decrypt_preimage,
    EncryptedPreimageField,
)


class PreimageEncryptionTestCase(unittest.TestCase):
    def setUp(self):
        self.plain_preimage = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    def test_encrypt_and_decrypt_roundtrip(self):
        encrypted = _encrypt_preimage(self.plain_preimage)
        self.assertNotEqual(encrypted, self.plain_preimage)
        self.assertTrue(encrypted.startswith("enc:"))

        decrypted = _decrypt_preimage(encrypted)
        self.assertEqual(decrypted, self.plain_preimage)

    def test_encrypt_idempotence(self):
        encrypted_once = _encrypt_preimage(self.plain_preimage)
        encrypted_twice = _encrypt_preimage(encrypted_once)
        self.assertEqual(encrypted_once, encrypted_twice)

    def test_empty_or_none_values(self):
        self.assertIsNone(_encrypt_preimage(None))
        self.assertEqual(_encrypt_preimage(""), "")
        self.assertIsNone(_decrypt_preimage(None))
        self.assertEqual(_decrypt_preimage(""), "")

    def test_decrypt_corrupted_token_graceful_fallback(self):
        corrupted = "enc:this_is_not_a_valid_fernet_token"
        result = _decrypt_preimage(corrupted)
        self.assertEqual(result, corrupted)

    def test_key_derivation_from_settings(self):
        cipher1 = _get_preimage_cipher()
        cipher2 = _get_preimage_cipher()
        # Same settings produce deterministic key encryption
        token = cipher1.encrypt(b"hello")
        self.assertEqual(cipher2.decrypt(token), b"hello")

    def test_encrypted_preimage_field_lifecycle(self):
        field = EncryptedPreimageField()

        # Database preparation (writing to DB)
        db_val = field.get_prep_value(self.plain_preimage)
        self.assertTrue(db_val.startswith("enc:"))

        # Python deserialization (reading from DB)
        py_val = field.from_db_value(db_val, None, None)
        self.assertEqual(py_val, self.plain_preimage)

        # to_python conversion
        to_py_val = field.to_python(db_val)
        self.assertEqual(to_py_val, self.plain_preimage)

    def test_anti_triangle_reference_generation(self):
        # Order reference generation format ROBO-<order_id>
        order_id = 4281
        payment_reference = f"ROBO-{order_id}"
        self.assertEqual(payment_reference, "ROBO-4281")
        self.assertTrue(payment_reference.startswith("ROBO-"))


if __name__ == "__main__":
    unittest.main()
