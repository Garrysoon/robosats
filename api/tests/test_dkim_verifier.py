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

    def test_extract_text_and_validate_pdf_attachment_in_email(self):
        # Construct a minimal authentic-looking PDF stream
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            b"4 0 obj <</Length 62>> stream\n"
            b"BT /F1 12 Tf 100 700 Td (T-Bank Transfer 5000.42 RUB Ref: ROBO-789) Tj ET\n"
            b"endstream endobj\n"
            b"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000357 00000 n \n"
            b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n433\n%%EOF"
        )

        import base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

        # Multi-part MIME email with PDF attachment
        mime_email = (
            "From: receipts@tbank.ru\r\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=tbank.ru; s=mail;\r\n"
            "Subject: Чек по операции\r\n"
            "MIME-Version: 1.0\r\n"
            "Content-Type: multipart/mixed; boundary=\"BOUNDARY\"\r\n\r\n"
            "--BOUNDARY\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "Здравствуйте! Во вложении чек по вашей операции.\r\n\r\n"
            "--BOUNDARY\r\n"
            "Content-Type: application/pdf; name=\"receipt.pdf\"\r\n"
            "Content-Disposition: attachment; filename=\"receipt.pdf\"\r\n"
            "Content-Transfer-Encoding: base64\r\n\r\n"
            f"{pdf_b64}\r\n"
            "--BOUNDARY--\r\n"
        ).encode("utf-8")

        with patch("dkim.verify", return_value=True):
            is_valid, msg, receipt = validate_receipt_for_order(self.sample_order, mime_email)
            self.assertTrue(is_valid)
            self.assertTrue(receipt["is_dkim_valid"])
            self.assertEqual(receipt["pdf_attachments_count"], 1)
            self.assertEqual(receipt["reference"], "ROBO-789")
            self.assertEqual(receipt["amount"], 5000.42)
            self.assertIn("verified across 1 PDF attachments", msg)

    def test_validate_standalone_pdf_receipt(self):
        # Direct raw PDF file upload
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            b"4 0 obj <</Length 62>> stream\n"
            b"BT /F1 12 Tf 100 700 Td (Sberbank Online 5000.42 RUB Ref: ROBO-789) Tj ET\n"
            b"endstream endobj\n"
            b"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000357 00000 n \n"
            b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n433\n%%EOF"
        )

        is_valid, msg, receipt = validate_receipt_for_order(self.sample_order, pdf_bytes)
        self.assertTrue(is_valid)
        self.assertTrue(receipt["is_standalone_pdf"])
        self.assertEqual(receipt["reference"], "ROBO-789")
        self.assertEqual(receipt["amount"], 5000.42)
        self.assertTrue("sber" in receipt["domain"])


if __name__ == "__main__":
    unittest.main()
