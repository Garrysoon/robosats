import os
import sys
from unittest.mock import MagicMock

# Stub any missing grpc proto modules if running outside full Docker LND build
for mod in [
    "api.lightning.invoices_pb2", "api.lightning.invoices_pb2_grpc",
    "api.lightning.lightning_pb2", "api.lightning.lightning_pb2_grpc",
    "api.lightning.router_pb2", "api.lightning.router_pb2_grpc",
    "api.lightning.signer_pb2", "api.lightning.signer_pb2_grpc",
    "api.lightning.verrpc_pb2", "api.lightning.verrpc_pb2_grpc",
    "api.lightning.node_pb2", "api.lightning.node_pb2_grpc",
    "api.lightning.hold_pb2", "api.lightning.hold_pb2_grpc",
    "api.lightning.primitives_pb2", "api.lightning.primitives_pb2_grpc",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

os.environ.setdefault("FEE", "0.002")
os.environ.setdefault("MAX_TRADE", "5000000")
os.environ.setdefault("MIN_TRADE", "10000")
os.environ.setdefault("LND_CERT_BASE64", "ZHVtbXk=")
os.environ.setdefault("LND_MACAROON_BASE64", "ZHVtbXk=")
os.environ.setdefault("LND_GRPC_HOST", "127.0.0.1:10009")

import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

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
            DEFAULT_PUBLIC_ORDER_DURATION=24,
            MIN_PUBLIC_ORDER_DURATION=0.16,
            MAX_PUBLIC_ORDER_DURATION=24,
            INVOICE_AND_ESCROW_DURATION=180,
            DEFAULT_BOND_SIZE=3.0,
            MIN_BOND_SIZE=2.0,
            MAX_BOND_SIZE=15.0,
            LIMIT_TOTAL_FIAT_PAYMENT_MINUTES=60,
            DEV_DONATIONS_PERCENT=0.01,
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "control",
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
except Exception:
    pass

from django.utils import timezone
from api.models.order import Order
from api.dispute_automation import (
    DisputeRecommendationEngine,
    DisputeAutomationService,
    DisputeRecommendation,
)


class DisputeAutomationTestCase(unittest.TestCase):
    def setUp(self):
        self.order = MagicMock(spec=Order)
        self.order.id = 501
        self.order.is_disputed = True
        self.order.status = Order.Status.DIS
        self.order.maker = MagicMock()
        self.order.maker.pk = 10
        self.order.taker = MagicMock()
        self.order.taker.pk = 20
        self.order.maker_statement = None
        self.order.taker_statement = None
        self.order.check_is_f2f.return_value = False
        self.order.f2f_arrived_maker = False
        self.order.f2f_arrived_taker = False
        self.order.logs = []
        self.order.maker_bond = MagicMock(num_satoshis=10000)
        self.order.taker_bond = MagicMock(num_satoshis=10000)
        self.order.trade_escrow = MagicMock(num_satoshis=100000)
        self.order.payout = MagicMock(num_satoshis=100000)
        self.order.is_swap = False

    def test_non_disputed_order_returns_none(self):
        self.order.is_disputed = False
        rec = DisputeRecommendationEngine.analyze_order(self.order)
        self.assertEqual(rec.action, "none")
        self.assertEqual(rec.confidence, 1.0)

    @patch("api.logics.Logics.is_buyer", return_value=False)
    @patch("api.dispute_automation.validate_receipt_for_order")
    def test_valid_dkim_recommends_successful_trade(self, mock_validate, mock_is_buyer):
        # Taker is buyer, provides valid DKIM receipt
        self.order.taker_statement = (
            "From: receipts@tbank.ru\r\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=tbank.ru;\r\n"
            "Payment ROBO-501 confirmed.\r\n"
        )
        mock_validate.return_value = (
            True,
            "Valid DKIM",
            {
                "is_dkim_valid": True,
                "domain": "tbank.ru",
                "reference": "ROBO-501",
                "amount": 5000.0,
            },
        )

        rec = DisputeRecommendationEngine.analyze_order(self.order)
        self.assertEqual(rec.action, "successful_trade")
        self.assertGreaterEqual(rec.confidence, 0.95)
        self.assertEqual(rec.stage, "DKIM")
        self.assertIn("tbank.ru", rec.reason)

    @patch("api.logics.Logics.is_buyer", return_value=True)
    def test_silence_sla_taker_silent_recommends_maker_wins(self, mock_is_buyer):
        # Maker submitted statement, taker has been silent
        self.order.maker_statement = "I sent the payment hours ago and seller disappeared."
        self.order.taker_statement = ""

        rec = DisputeRecommendationEngine.analyze_order(self.order, silence_hours=24)
        self.assertEqual(rec.action, "maker_wins")
        self.assertGreaterEqual(rec.confidence, 0.90)
        self.assertEqual(rec.stage, "SILENCE_SLA")
        self.assertIn("silent in dispute", rec.reason)

    @patch("api.logics.Logics.is_buyer", return_value=True)
    def test_silence_sla_maker_silent_recommends_taker_wins(self, mock_is_buyer):
        # Taker submitted statement, maker has been silent
        self.order.maker_statement = ""
        self.order.taker_statement = "Buyer never paid and stopped answering messages."

        rec = DisputeRecommendationEngine.analyze_order(self.order, silence_hours=24)
        self.assertEqual(rec.action, "taker_wins")
        self.assertGreaterEqual(rec.confidence, 0.90)
        self.assertEqual(rec.stage, "SILENCE_SLA")

    @patch("api.logics.Logics.is_buyer", return_value=True)
    def test_f2f_no_show_recommends_arrived_party(self, mock_is_buyer):
        self.order.check_is_f2f.return_value = True
        self.order.f2f_arrived_maker = True
        self.order.f2f_arrived_taker = False

        rec = DisputeRecommendationEngine.analyze_order(self.order)
        self.assertEqual(rec.action, "maker_wins")
        self.assertEqual(rec.stage, "F2F")
        self.assertIn("Taker failed to check in", rec.reason)

    @patch("api.logics.Logics.is_buyer", return_value=True)
    def test_conflicting_dispute_requires_manual_investigation(self, mock_is_buyer):
        # Both parties submitted statements
        self.order.maker_statement = "I paid 10,000 cash."
        self.order.taker_statement = "No, buyer gave me counterfeit bills."

        rec = DisputeRecommendationEngine.analyze_order(self.order)
        self.assertEqual(rec.action, "needs_human_investigation")
        self.assertEqual(rec.stage, "MANUAL")
        self.assertEqual(rec.confidence, 0.50)

    @patch("api.logics.Logics.is_buyer", return_value=False)
    @patch("api.models.Order.objects.select_for_update")
    @patch("api.models.Robot.objects.filter")
    @patch("api.tasks.send_notification.delay")
    def test_apply_resolution_maker_wins(self, mock_notify, mock_robot_filter, mock_select, mock_is_buyer):
        mock_select.return_value.get.return_value = self.order
        mock_robot_filter.return_value.update.return_value = 1

        success, msg = DisputeAutomationService.apply_resolution(
            self.order, action="maker_wins", actor="test_runner", reason="Taker breached SLA"
        )
        self.assertTrue(success)
        self.order.update_status.assert_called_with(Order.Status.TLD)
        self.assertEqual(len(self.order.logs), 1)
        self.assertEqual(self.order.logs[0]["action"], "maker_wins")

    @patch("api.logics.Logics.is_buyer", return_value=False)
    @patch("api.logics.Logics.pay_buyer", return_value=True)
    @patch("api.models.Order.objects.select_for_update")
    @patch("api.models.Robot.objects.filter")
    def test_apply_resolution_successful_trade(self, mock_robot_filter, mock_select, mock_pay_buyer, mock_is_buyer):
        mock_select.return_value.get.return_value = self.order
        mock_robot_filter.return_value.update.return_value = 1

        success, msg = DisputeAutomationService.apply_resolution(
            self.order, action="successful_trade", actor="test_runner", reason="Valid DKIM"
        )
        self.assertTrue(success)
        self.order.update_status.assert_called_with(Order.Status.PAY)
        mock_pay_buyer.assert_called_once_with(self.order)


if __name__ == "__main__":
    unittest.main()
