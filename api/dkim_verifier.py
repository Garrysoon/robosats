import email
from email import policy
import re
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any

TRUSTED_BANK_DOMAINS = {
    "tbank.ru",
    "tinkoff.ru",
    "sberbank.ru",
    "sber.ru",
    "alfabank.ru",
    "raiffeisen.ru",
    "vtb.ru",
    "gazprombank.ru",
    "sovcombank.ru",
}


def _extract_domain(email_address: str) -> str:
    """Extracts root/subdomain from an email address or domain string."""
    if not email_address:
        return ""
    if "@" in email_address:
        domain = email_address.split("@")[-1].strip("> \t\r\n").lower()
        return domain
    return email_address.strip().lower()


def is_trusted_bank_domain(domain: str) -> bool:
    """Checks if a domain belongs to or is a subdomain of a trusted bank."""
    domain = _extract_domain(domain)
    for trusted in TRUSTED_BANK_DOMAINS:
        if domain == trusted or domain.endswith(f".{trusted}"):
            return True
    return False


def verify_dkim_signature(raw_bytes: bytes) -> Tuple[bool, str]:
    """
    Verifies the cryptographic DKIM signature against DNS public keys.
    Requires dkimpy.
    """
    try:
        import dkim
        valid = dkim.verify(raw_bytes)
        if valid:
            return True, "DKIM verification passed (cryptographically valid)"
        return False, "DKIM signature failed verification"
    except ImportError:
        return False, "dkimpy library is not installed"
    except Exception as e:
        return False, f"DKIM verification error: {str(e)}"


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts plain text from raw PDF bytes across all pages using pypdf.
    """
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return ""
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                extracted.append(t)
        return "\n".join(extracted)
    except Exception as e:
        return ""


def parse_standalone_pdf_receipt(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Parses a standalone bank receipt PDF file directly uploaded by a user.
    Extracts text, reference code (ROBO-<id>), and amounts.
    """
    pdf_text = extract_text_from_pdf(pdf_bytes)

    # Search for ROBO reference code
    ref_match = re.search(r"ROBO-\d+", pdf_text, re.IGNORECASE)
    reference_code = ref_match.group(0).upper() if ref_match else None

    # Search for monetary amounts
    amounts = []
    for match in re.finditer(r"(\d[\d\s]{1,12}(?:[.,]\d{2})?)\s*(?:₽|руб|RUB|EUR|USD|sats)?", pdf_text):
        raw_val = match.group(1).replace(" ", "").replace(",", ".")
        try:
            val = Decimal(raw_val)
            if val > 0:
                amounts.append(val)
        except Exception:
            pass

    # Detect recognized bank keywords inside the PDF
    detected_bank = None
    for domain in TRUSTED_BANK_DOMAINS:
        bank_name = domain.split(".")[0]
        if bank_name.lower() in pdf_text.lower():
            detected_bank = domain
            break

    first_amount = float(amounts[0]) if amounts else None

    return {
        "from": f"PDF Document ({detected_bank or 'Unknown Bank'})",
        "to": "",
        "domain": detected_bank or "bank.pdf",
        "subject": "Standalone PDF Receipt",
        "date": "",
        "body_preview": pdf_text[:500] if pdf_text else "",
        "reference": reference_code,
        "reference_code": reference_code,
        "amount": first_amount,
        "detected_amounts": [float(a) for a in amounts[:5]],
        "is_trusted_bank": bool(detected_bank),
        "is_dkim_valid": False,  # Standalone PDFs do not carry SMTP DKIM signatures
        "is_standalone_pdf": True,
        "pdf_attachments_count": 1,
        "dkim_verified": False,
        "dkim_message": "Standalone PDF receipt (no SMTP DKIM signature). Parameters extracted from PDF document stream.",
    }


def parse_bank_receipt(raw_bytes: bytes) -> Dict[str, Any]:
    """
    Parses an RFC 822 / MIME (.eml) email file or standalone PDF.
    Extracts headers, sender domain, DKIM status, body, PDF attachments, reference codes and amounts.
    """
    if raw_bytes.startswith(b"%PDF"):
        return parse_standalone_pdf_receipt(raw_bytes)

    msg = email.message_from_bytes(raw_bytes, policy=policy.default)

    sender = str(msg.get("From", ""))
    recipient = str(msg.get("To", ""))
    subject = str(msg.get("Subject", ""))
    date_str = str(msg.get("Date", ""))
    domain = _extract_domain(sender)

    # Extract body text from MIME parts (both text/plain, text/html, and application/pdf attachments)
    body_parts = []
    pdf_texts = []
    pdf_filenames = []

    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename() or ""

        if content_type in ["text/plain", "text/html"]:
            try:
                content = part.get_content()
                if content:
                    body_parts.append(str(content))
            except Exception:
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="ignore"))

        elif content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            payload = part.get_payload(decode=True)
            if payload and payload.startswith(b"%PDF"):
                pdf_filenames.append(filename or "receipt.pdf")
                pdf_text = extract_text_from_pdf(payload)
                if pdf_text:
                    pdf_texts.append(pdf_text)

    # Combine text from body and any attached PDFs
    combined_text = "\n".join(body_parts + pdf_texts)
    if not combined_text:
        combined_text = subject

    # Search for ROBO reference code
    ref_match = re.search(r"ROBO-\d+", combined_text, re.IGNORECASE) or re.search(r"ROBO-\d+", subject, re.IGNORECASE)
    reference_code = ref_match.group(0).upper() if ref_match else None

    # Search for monetary amounts (e.g. 50 184.20 or 50184.20 or 50 000)
    amounts = []
    for match in re.finditer(r"(\d[\d\s]{1,12}(?:[.,]\d{2})?)\s*(?:₽|руб|RUB|EUR|USD|sats)?", combined_text):
        raw_val = match.group(1).replace(" ", "").replace(",", ".")
        try:
            val = Decimal(raw_val)
            if val > 0:
                amounts.append(val)
        except Exception:
            pass

    dkim_valid, dkim_msg = verify_dkim_signature(raw_bytes)
    trusted = is_trusted_bank_domain(domain)

    first_amount = float(amounts[0]) if amounts else None

    return {
        "from": sender,
        "to": recipient,
        "domain": domain,
        "subject": subject,
        "date": date_str,
        "body_preview": combined_text[:500] if combined_text else "",
        "reference": reference_code,
        "reference_code": reference_code,
        "amount": first_amount,
        "detected_amounts": [float(a) for a in amounts[:5]],
        "is_trusted_bank": trusted,
        "is_dkim_valid": dkim_valid,
        "is_standalone_pdf": False,
        "pdf_attachments_count": len(pdf_filenames),
        "pdf_filenames": pdf_filenames,
        "dkim_verified": dkim_valid,
        "dkim_message": dkim_msg,
    }


def validate_receipt_for_order(order, raw_bytes: bytes) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates that a raw .eml bank receipt (or attached/standalone PDF) proves legitimate fiat transfer for a given Order.
    Checks:
    1. Valid DKIM cryptographic signature (or standalone PDF format)
    2. Originates from a verified banking domain (or recognized bank document)
    3. Contains matching order reference code (ROBO-<order.id>)
    4. Matches the expected fiat amount
    """
    receipt = parse_bank_receipt(raw_bytes)

    is_standalone_pdf = receipt.get("is_standalone_pdf", False)

    if not is_standalone_pdf:
        if not receipt["is_trusted_bank"]:
            return False, f"Sender domain '{receipt['domain']}' is not a recognised trusted bank.", receipt

        if not receipt["is_dkim_valid"]:
            return False, f"DKIM verification failed: {receipt['dkim_message']}", receipt

    expected_ref = f"ROBO-{order.id}"
    if receipt["reference"] != expected_ref:
        return False, f"Reference mismatch. Expected '{expected_ref}', found '{receipt['reference']}'.", receipt

    if order.amount is not None:
        expected_amount = float(order.amount)
        # Check if expected amount matches any detected amount within 0.05 margin
        matched = any(abs(a - expected_amount) < 0.05 for a in receipt["detected_amounts"])
        if not matched:
            return False, f"Amount mismatch. Expected {expected_amount}, detected in receipt: {receipt['detected_amounts']}", receipt

    if is_standalone_pdf:
        return True, "Standalone PDF receipt parameters match order (Note: unverified by SMTP DKIM).", receipt

    pdf_info = f" (verified across {receipt['pdf_attachments_count']} PDF attachments)" if receipt.get("pdf_attachments_count", 0) > 0 else ""
    return True, f"Receipt mathematically verified by bank DKIM signature{pdf_info} and matches order parameters.", receipt


class BankReceiptVerifier:
    """Helper wrapper for OOP-style access to DKIM verification services."""
    TRUSTED_DOMAINS = TRUSTED_BANK_DOMAINS

    @staticmethod
    def is_trusted_bank_domain(domain_or_email: str) -> bool:
        return is_trusted_bank_domain(domain_or_email)

    @staticmethod
    def extract_payment_details(text: str, domain: str = "") -> Dict[str, Any]:
        ref_match = re.search(r"ROBO-\d+", text, re.IGNORECASE)
        reference_code = ref_match.group(0).upper() if ref_match else None

        amounts = []
        for match in re.finditer(r"(\d[\d\s]{1,12}(?:[.,]\d{2})?)\s*(?:₽|руб|RUB|EUR|USD|sats)?", text):
            raw_val = match.group(1).replace(" ", "").replace(",", ".")
            try:
                val = Decimal(raw_val)
                if val > 0:
                    amounts.append(float(val))
            except Exception:
                pass

        return {
            "reference": reference_code,
            "amount": amounts[0] if amounts else None,
            "amounts": amounts,
            "domain": domain,
        }

    @staticmethod
    def parse_receipt(raw_bytes: bytes) -> Dict[str, Any]:
        return parse_bank_receipt(raw_bytes)

    @staticmethod
    def validate_receipt_for_order(order, raw_bytes: bytes) -> Tuple[bool, str, Dict[str, Any]]:
        return validate_receipt_for_order(order, raw_bytes)
