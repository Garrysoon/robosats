import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import MagicMock, patch

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
from django.utils import timezone

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

from api.models.order import Order
from api.models.email_inbox import EmailInboxConfig
from api.email_ingestion import process_inbound_email_bytes, BankReceiptEmailWatcher


class EmailIngestionTestCase(unittest.TestCase):
    def setUp(self):
        self.sample_order = MagicMock(spec=Order)
        self.sample_order.id = 882
        self.sample_order.amount = 15200.50
        self.sample_order.status = Order.Status.FSE
        self.sample_order.is_fiat_sent = False
        self.sample_order.is_disputed = False
        self.sample_order.logs = []
        self.sample_order.maker = MagicMock()
        self.sample_order.taker = MagicMock()

        self.inbox_config = EmailInboxConfig(
            host="imap.yandex.ru",
            port=993,
            username="receipts@robosats.org",
            password="secret_app_password",
            use_ssl=True,
            folder="INBOX",
            public_receipt_email="pay@robosats.org",
            is_active=True,
        )

    def test_inbox_config_display_address(self):
        self.assertEqual(self.inbox_config.get_display_receipt_address(), "pay@robosats.org")
        self.inbox_config.public_receipt_email = ""
        self.assertEqual(self.inbox_config.get_display_receipt_address(), "receipts@robosats.org")

    def test_process_email_missing_reference_fails(self):
        email_bytes = (
            "From: notifications@tbank.ru\r\n"
            "Subject: Перевод выполнен\r\n\r\n"
            "Вы перевели 5000 руб без кода заказа.\r\n"
        ).encode("utf-8")

        res = process_inbound_email_bytes(email_bytes)
        self.assertFalse(res["success"])
        self.assertIn("No ROBO-<id>", res["reason"])

    @patch("api.models.Order.objects.get")
    def test_process_email_nonexistent_order_fails(self, mock_order_get):
        mock_order_get.side_effect = Order.DoesNotExist

        email_bytes = (
            "From: notifications@tbank.ru\r\n"
            "Subject: Перевод ROBO-9999\r\n\r\n"
            "Сумма 1000 руб.\r\n"
        ).encode("utf-8")

        res = process_inbound_email_bytes(email_bytes)
        self.assertFalse(res["success"])
        self.assertIn("does not exist", res["reason"])

    @patch("api.logics.Logics.is_buyer", return_value=False)
    @patch("api.models.Order.objects.select_for_update")
    @patch("api.models.Order.objects.get")
    @patch("dkim.verify", return_value=True)
    def test_process_email_successful_matching(self, mock_dkim, mock_get, mock_select, mock_is_buyer):
        mock_get.return_value = self.sample_order
        mock_select.return_value.get.return_value = self.sample_order

        email_bytes = (
            "From: receipts@tbank.ru\r\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=tbank.ru; s=mail;\r\n"
            "Subject: Перевод клиенту\r\n\r\n"
            "Перевод отправлен. Сумма: 15200.50 RUB. Назначение: ROBO-882\r\n"
        ).encode("utf-8")

        res = process_inbound_email_bytes(email_bytes)
        self.assertTrue(res["success"])
        self.assertEqual(res["order_id"], 882)
        self.assertEqual(res["domain"], "tbank.ru")
        self.assertTrue(res["is_dkim_valid"])
        self.assertTrue(self.sample_order.is_fiat_sent)
        self.assertEqual(len(self.sample_order.logs), 1)
        self.assertEqual(self.sample_order.logs[0]["event"], "email_receipt_ingested")

    @patch("imaplib.IMAP4_SSL")
    def test_imap_connection_success(self, mock_imap_cls):
        mock_imap = MagicMock()
        mock_imap.login.return_value = ("OK", [b"Logged in"])
        mock_imap.select.return_value = ("OK", [b"10"])
        mock_imap_cls.return_value = mock_imap

        success, msg = BankReceiptEmailWatcher.test_connection(self.inbox_config)
        self.assertTrue(success)
        self.assertIn("Successfully connected", msg)
        mock_imap.login.assert_called_with("receipts@robosats.org", "secret_app_password")

    @patch("imaplib.IMAP4_SSL")
    def test_imap_connection_auth_failure(self, mock_imap_cls):
        mock_imap = MagicMock()
        mock_imap.login.side_effect = Exception("AUTHENTICATIONFAILED Invalid credentials")
        mock_imap_cls.return_value = mock_imap

        success, msg = BankReceiptEmailWatcher.test_connection(self.inbox_config)
        self.assertFalse(success)
        self.assertIn("AUTHENTICATIONFAILED", msg)

    @patch("api.email_ingestion.process_inbound_email_bytes")
    @patch("imaplib.IMAP4_SSL")
    def test_poll_inbox_fetches_and_processes(self, mock_imap_cls, mock_process):
        mock_imap = MagicMock()
        mock_imap.select.return_value = ("OK", [b"2"])
        mock_imap.search.return_value = ("OK", [b"101 102"])
        mock_imap.fetch.return_value = ("OK", [(b"101 (RFC822 {100}", b"From: tbank.ru\r\nROBO-882")])
        mock_imap_cls.return_value = mock_imap

        mock_process.return_value = {"success": True, "order_id": 882}

        results = BankReceiptEmailWatcher.poll_inbox(self.inbox_config, mark_seen=True)
        self.assertEqual(len(results), 2)
        mock_imap.store.assert_called()


if __name__ == "__main__":
    unittest.main()
