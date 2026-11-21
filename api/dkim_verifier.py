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
    """Extracts root/subdomain from an email address."""
    if not email_address:
        return ""
    if "@" in email_address:
        domain = email_address.split("@")[-1].strip("> \t\r\n").lower()
        return domain
    return ""


def is_trusted_bank_domain(domain: str) -> bool:
    """Checks if a domain belongs to or is a subdomain of a trusted bank."""
    domain = domain.lower()
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


def parse_bank_receipt(raw_bytes: bytes) -> Dict[str, Any]:
    """
    Parses an RFC 822 / MIME (.eml) email file.
    Extracts headers, sender domain, DKIM status, body, reference codes and amounts.
    """
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)

    sender = str(msg.get("From", ""))
    recipient = str(msg.get("To", ""))
    subject = str(msg.get("Subject", ""))
    date_str = str(msg.get("Date", ""))
    domain = _extract_domain(sender)

    # Extract body text
    body = ""
    try:
        body_part = msg.get_body(preferencelist=("plain", "html"))
        if body_part:
            body = body_part.get_content()
    except Exception:
        body = msg.get_payload()
        if isinstance(body, list):
            body = " ".join(str(p) for p in body)

    # Search for ROBO reference code
    ref_match = re.search(r"ROBO-\d+", body, re.IGNORECASE) or re.search(r"ROBO-\d+", subject, re.IGNORECASE)
    reference_code = ref_match.group(0).upper() if ref_match else None

    # Search for monetary amounts (e.g. 50 184.20 or 50184.20 or 50 000)
    amounts = []
    for match in re.finditer(r"(\d[\d\s]{1,12}(?:[.,]\d{2})?)\s*(?:₽|руб|RUB|EUR|USD|sats)?", body):
        raw_val = match.group(1).replace(" ", "").replace(",", ".")
        try:
            val = Decimal(raw_val)
            if val > 0:
                amounts.append(val)
        except Exception:
            pass

    dkim_valid, dkim_msg = verify_dkim_signature(raw_bytes)
    trusted = is_trusted_bank_domain(domain)

    return {
        "from": sender,
        "to": recipient,
        "domain": domain,
        "subject": subject,
        "date": date_str,
        "body_preview": body[:500] if body else "",
        "reference_code": reference_code,
        "detected_amounts": [float(a) for a in amounts[:5]],
        "is_trusted_bank": trusted,
        "dkim_verified": dkim_valid,
        "dkim_message": dkim_msg,
    }


def validate_receipt_for_order(order, raw_bytes: bytes) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates that a raw .eml bank receipt proves legitimate fiat transfer for a given Order.
    Checks:
    1. Valid DKIM cryptographic signature
    2. Originates from a verified banking domain
    3. Contains matching order reference code (ROBO-<order.id>)
    4. Matches the expected fiat amount
    """
    receipt = parse_bank_receipt(raw_bytes)

    if not receipt["is_trusted_bank"]:
        return False, f"Sender domain '{receipt['domain']}' is not a recognised trusted bank.", receipt

    if not receipt["dkim_verified"]:
        return False, f"DKIM verification failed: {receipt['dkim_message']}", receipt

    expected_ref = f"ROBO-{order.id}"
    if receipt["reference_code"] != expected_ref:
        return False, f"Reference code mismatch. Expected '{expected_ref}', found '{receipt['reference_code']}'.", receipt

    if order.amount is not None:
        expected_amount = float(order.amount)
        # Check if expected amount matches any detected amount within 0.05 margin
        matched = any(abs(a - expected_amount) < 0.05 for a in receipt["detected_amounts"])
        if not matched:
            return False, f"Amount mismatch. Expected {expected_amount}, detected in receipt: {receipt['detected_amounts']}", receipt

    return True, "Receipt mathematically verified by bank DKIM signature and matches order parameters.", receipt
