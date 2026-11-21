import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.dkim_verifier import BankReceiptVerifier, TRUSTED_BANK_DOMAINS, validate_receipt_for_order


class DKIMVerifierTestCase(unittest.TestCase):
    def setUp(self):
        self.sample_order = MagicMock()
        self.sample_order.id = 789
        self.sample_order.amount = 5000.42

    def test_trusted_bank_domains_presence(self):
        # Verify key major banks are in trusted list
        self.assertIn("tbank.ru", TRUSTED_BANK_DOMAINS)
        self.assertIn("tinkoff.ru", TRUSTED_BANK_DOMAINS)
        self.assertIn("sberbank.ru", TRUSTED_BANK_DOMAINS)
        self.assertIn("alfabank.ru", TRUSTED_BANK_DOMAINS)
        self.assertIn("raiffeisen.ru", TRUSTED_BANK_DOMAINS)
        self.assertIn("vtb.ru", TRUSTED_BANK_DOMAINS)

    def test_detect_trusted_bank(self):
        self.assertTrue(BankReceiptVerifier.is_trusted_bank_domain("notify@tbank.ru"))
        self.assertTrue(BankReceiptVerifier.is_trusted_bank_domain("receipts.sberbank.ru"))
        self.assertTrue(BankReceiptVerifier.is_trusted_bank_domain("noreply@alfabank.ru"))
        self.assertFalse(BankReceiptVerifier.is_trusted_bank_domain("attacker@gmail.com"))
        self.assertFalse(BankReceiptVerifier.is_trusted_bank_domain("evilbank.ru"))

    def test_extract_payment_details_sberbank(self):
        sber_body = (
            "СберБанк Онлайн. Перевод выполнен успешно.\n"
            "Сумма: 5 000,42 RUB\n"
            "Сообщение получателю: ROBO-789\n"
            "Номер документа: 123456789\n"
        )
        details = BankReceiptVerifier.extract_payment_details(sber_body, "sberbank.ru")
        self.assertEqual(details["amount"], 5000.42)
        self.assertEqual(details["reference"], "ROBO-789")

    def test_extract_payment_details_tbank(self):
        tbank_body = (
            "Т-Банк. Перевод по номеру телефона.\n"
            "Сумма перевода: 15 200.50 ₽\n"
            "Назначение: ROBO-1050 оплата заказа\n"
        )
        details = BankReceiptVerifier.extract_payment_details(tbank_body, "tbank.ru")
        self.assertEqual(details["amount"], 15200.50)
        self.assertEqual(details["reference"], "ROBO-1050")

    def test_validate_receipt_for_order_matching(self):
        raw_email = (
            "From: notifications@tbank.ru\r\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=tbank.ru; s=mail;\r\n"
            "Subject: Перевод клиенту\r\n\r\n"
            "Перевод отправлен. Сумма: 5000.42 RUB. Сообщение: ROBO-789\r\n"
        ).encode("utf-8")

        # Mock dkim.verify to return True for authentic bank DKIM
        with patch("dkim.verify", return_value=True):
            is_valid, msg, receipt = validate_receipt_for_order(self.sample_order, raw_email)
            self.assertTrue(is_valid)
            self.assertTrue(receipt["is_dkim_valid"])
            self.assertEqual(receipt["domain"], "tbank.ru")
            self.assertEqual(receipt["amount"], 5000.42)
            self.assertEqual(receipt["reference"], "ROBO-789")

    def test_validate_receipt_mismatched_reference_rejected(self):
        raw_email = (
            "From: notifications@tbank.ru\r\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=tbank.ru; s=mail;\r\n"
            "Subject: Перевод клиенту\r\n\r\n"
            "Перевод отправлен. Сумма: 5000.42 RUB. Сообщение: ROBO-999\r\n"
        ).encode("utf-8")

        with patch("dkim.verify", return_value=True):
            is_valid, msg, receipt = validate_receipt_for_order(self.sample_order, raw_email)
            self.assertFalse(is_valid)
            self.assertIn("Reference mismatch", msg)

    def test_validate_receipt_mismatched_amount_rejected(self):
        raw_email = (
            "From: notifications@tbank.ru\r\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=tbank.ru; s=mail;\r\n"
            "Subject: Перевод клиенту\r\n\r\n"
            "Перевод отправлен. Сумма: 1000.00 RUB. Сообщение: ROBO-789\r\n"
        ).encode("utf-8")

        with patch("dkim.verify", return_value=True):
            is_valid, msg, receipt = validate_receipt_for_order(self.sample_order, raw_email)
            self.assertFalse(is_valid)
            self.assertIn("Amount mismatch", msg)


if __name__ == "__main__":
    unittest.main()
