import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.f2f_security import F2FSecurityService, SAFE_TRADE_CHECKLIST


class F2FSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.maker_user = MagicMock()
        self.maker_user.username = "AdequateAlice01"
        self.taker_user = MagicMock()
        self.taker_user.username = "BoldBob02"

        # Mock Order
        self.order = MagicMock()
        self.order.id = 1234
        self.order.maker = self.maker_user
        self.order.taker = self.taker_user
        self.order.type = 0  # BUY (Maker is buyer, Taker is seller)
        self.order.is_f2f = True
        self.order.f2f_release_secret_hash = None
        self.order.f2f_arrived_maker = False
        self.order.f2f_arrived_taker = False
        self.order.f2f_pin_attempts = 0
        self.order.check_is_f2f = MagicMock(return_value=True)
        self.order.save = MagicMock()
        self.order.log = MagicMock()

    def test_generate_release_pin(self):
        pin, pin_hash = F2FSecurityService.generate_release_pin()
        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isdigit())
        self.assertEqual(len(pin_hash), 64)

        import hashlib
        expected_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest()
        self.assertEqual(pin_hash, expected_hash)

    def test_setup_f2f_order(self):
        with patch("api.f2f_security.cache.get", return_value=None), \
             patch("api.f2f_security.cache.set") as mock_cache_set:

            pin = F2FSecurityService.setup_f2f_order(self.order, force=True)
            self.assertEqual(len(pin), 6)
            self.assertIsNotNone(self.order.f2f_release_secret_hash)
            mock_cache_set.assert_called_once()
            self.order.save.assert_called_with(update_fields=["is_f2f", "f2f_release_secret_hash"])

    def test_arrival_registration(self):
        # Maker arrives
        res1 = F2FSecurityService.register_arrival(self.order, self.maker_user)
        self.assertTrue(res1["arrived_maker"])
        self.assertFalse(res1["both_arrived"])

        # Taker arrives
        res2 = F2FSecurityService.register_arrival(self.order, self.taker_user)
        self.assertTrue(res2["arrived_taker"])
        self.assertTrue(res2["both_arrived"])

    def test_seller_pin_verification_success(self):
        pin, pin_hash = F2FSecurityService.generate_release_pin()
        self.order.f2f_release_secret_hash = pin_hash

        mock_logics = MagicMock()
        mock_logics.is_seller.side_effect = lambda o, u: u == self.taker_user
        mock_logics.confirm_fiat.return_value = (True, None)

        with patch("api.f2f_security.Logics", mock_logics):
            # Seller submits correct PIN
            result = F2FSecurityService.verify_release_pin(self.order, pin, self.taker_user)
            self.assertTrue(result["success"])
            self.assertTrue(result["released"])
            mock_logics.confirm_fiat.assert_called_once_with(self.order, self.taker_user)

    def test_buyer_forbidden_from_verifying_own_pin(self):
        pin, pin_hash = F2FSecurityService.generate_release_pin()
        self.order.f2f_release_secret_hash = pin_hash

        mock_logics = MagicMock()
        mock_logics.is_seller.return_value = False

        with patch("api.f2f_security.Logics", mock_logics):
            result = F2FSecurityService.verify_release_pin(self.order, pin, self.maker_user)
            self.assertFalse(result["success"])
            self.assertIn("Only the seller", result["error"])

    def test_brute_force_rate_limiting(self):
        _, pin_hash = F2FSecurityService.generate_release_pin()
        self.order.f2f_release_secret_hash = pin_hash

        mock_logics = MagicMock()
        mock_logics.is_seller.return_value = True

        with patch("api.f2f_security.Logics", mock_logics):
            # 5 incorrect attempts
            for i in range(5):
                res = F2FSecurityService.verify_release_pin(self.order, "000000", self.taker_user)
                self.assertFalse(res["success"])

            self.assertEqual(self.order.f2f_pin_attempts, 5)

            # 6th attempt should be locked out
            res_locked = F2FSecurityService.verify_release_pin(self.order, "000000", self.taker_user)
            self.assertFalse(res_locked["success"])
            self.assertIn("Maximum PIN verification attempts exceeded", res_locked["error"])

    def test_safe_trade_checklist_contents(self):
        self.assertTrue(len(SAFE_TRADE_CHECKLIST) >= 5)
        titles = [rule["title"] for rule in SAFE_TRADE_CHECKLIST]
        self.assertTrue(any("ATM Cash-In" in t for t in titles))
        self.assertTrue(any("Public Safe Zones" in t for t in titles))
        self.assertTrue(any("Release PIN Handshake" in t for t in titles))


if __name__ == "__main__":
    unittest.main()
