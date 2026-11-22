import imaplib
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from django.db import transaction
from django.utils import timezone
from decouple import config

from api.models import Order
from api.models.email_inbox import EmailInboxConfig
from api.dkim_verifier import parse_bank_receipt, validate_receipt_for_order
from api.logics import Logics

logger = logging.getLogger(__name__)


def process_inbound_email_bytes(raw_bytes: bytes) -> Dict[str, Any]:
    """
    Processes raw RFC 822 / MIME bytes of a bank receipt email received via IMAP.
    Validates cryptographic DKIM signature and extracts ROBO-<id> and fiat amount.
    If a matching active or disputed order is found, records the receipt and updates order state.
    """
    receipt = parse_bank_receipt(raw_bytes)
    reference = receipt.get("reference")
    domain = receipt.get("domain", "")
    is_dkim_valid = receipt.get("is_dkim_valid", False)
    is_trusted = receipt.get("is_trusted_bank", False)
    detected_amounts = receipt.get("detected_amounts", [])

    if not reference:
        return {
            "success": False,
            "reason": "No ROBO-<id> reference code found in email subject, body, or PDF attachments.",
            "receipt": receipt,
        }

    # Extract integer Order ID
    match = re.search(r"ROBO-(\d+)", reference, re.IGNORECASE)
    if not match:
        return {
            "success": False,
            "reason": f"Invalid reference format '{reference}'.",
            "receipt": receipt,
        }

    order_id = int(match.group(1))

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return {
            "success": False,
            "reason": f"Order #{order_id} does not exist in coordinator database.",
            "receipt": receipt,
        }

    # Validate receipt against this order's expected amount
    is_valid, msg, validated_receipt = validate_receipt_for_order(order, raw_bytes)

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)

        maker_is_buyer = Logics.is_buyer(order, order.maker)
        email_text_repr = raw_bytes.decode("utf-8", errors="replace")

        # Record receipt statement
        if maker_is_buyer:
            order.maker_statement = email_text_repr
        else:
            order.taker_statement = email_text_repr

        # Add audit log
        if not isinstance(order.logs, list):
            order.logs = []

        log_entry = {
            "event": "email_receipt_ingested",
            "domain": domain,
            "is_dkim_valid": is_dkim_valid,
            "is_trusted_bank": is_trusted,
            "reference": reference,
            "detected_amounts": detected_amounts,
            "pdf_attachments": receipt.get("pdf_attachments_count", 0),
            "timestamp": timezone.now().isoformat(),
            "validation_msg": msg,
        }
        order.logs.append(log_entry)

        # If fiat was not marked as sent yet and receipt is cryptographically valid, mark fiat sent
        if is_valid and not order.is_fiat_sent and order.status in [Order.Status.FSE, Order.Status.PAY]:
            order.is_fiat_sent = True

        order.save(update_fields=["maker_statement", "taker_statement", "logs", "is_fiat_sent"])

        # If order is in active dispute and DKIM is valid from trusted bank, auto-resolve!
        if is_valid and order.is_disputed and order.status in [Order.Status.DIS, Order.Status.WFR]:
            try:
                from api.dispute_automation import DisputeAutomationService
                DisputeAutomationService.apply_resolution(
                    order,
                    action="successful_trade",
                    actor="imap_email_watcher",
                    reason=f"Automated resolution: valid bank receipt ingested via IMAP from {domain} (DKIM PASS).",
                )
            except Exception as e:
                logger.error(f"Failed to auto-resolve dispute for order #{order_id} on email ingestion: {e}")

    logger.info(f"Successfully processed bank receipt email for order #{order_id} from {domain} (DKIM: {is_dkim_valid})")
    return {
        "success": True,
        "order_id": order_id,
        "domain": domain,
        "is_dkim_valid": is_dkim_valid,
        "message": msg,
        "receipt": receipt,
    }


class BankReceiptEmailWatcher:
    """
    IMAP polling service for coordinator inbound receipt mailboxes.
    Periodically checks for unread emails sent directly from retail bank apps.
    """

    @classmethod
    def get_active_configs(cls) -> List[EmailInboxConfig]:
        """Returns all active inbox configs from DB, or fallback from env if none configured in DB."""
        db_configs = list(EmailInboxConfig.objects.filter(is_active=True))
        if db_configs:
            return db_configs

        # Fallback to .env configuration if present
        env_host = config("IMAP_HOST", default="")
        env_user = config("IMAP_USER", default="")
        env_pass = config("IMAP_PASSWORD", default="")
        if env_host and env_user and env_pass:
            return [
                EmailInboxConfig(
                    host=env_host,
                    port=config("IMAP_PORT", default=993, cast=int),
                    username=env_user,
                    password=env_pass,
                    use_ssl=config("IMAP_USE_SSL", default=True, cast=bool),
                    folder=config("IMAP_FOLDER", default="INBOX"),
                    public_receipt_email=config("RECEIPTS_EMAIL_ADDRESS", default=env_user),
                    is_active=True,
                )
            ]
        return []

    @classmethod
    def test_connection(cls, inbox_config: EmailInboxConfig) -> Tuple[bool, str]:
        """Tests IMAP authentication and connection without processing emails."""
        try:
            if inbox_config.use_ssl:
                imap = imaplib.IMAP4_SSL(inbox_config.host, inbox_config.port)
            else:
                imap = imaplib.IMAP4(inbox_config.host, inbox_config.port)

            imap.login(inbox_config.username, inbox_config.password)
            status, _ = imap.select(inbox_config.folder or "INBOX")
            imap.logout()

            if status == "OK":
                return True, f"Successfully connected to {inbox_config.host}:{inbox_config.port} and opened {inbox_config.folder}."
            return False, f"Connected to IMAP but folder '{inbox_config.folder}' returned status: {status}"
        except Exception as e:
            return False, f"IMAP connection failed: {str(e)}"

    @classmethod
    def poll_inbox(cls, inbox_config: EmailInboxConfig, mark_seen: bool = True) -> List[Dict[str, Any]]:
        """
        Polls a specific IMAP inbox for unread bank receipt emails.
        Fetches RFC822 raw message bytes, validates them, and marks them as processed.
        """
        results = []
        now = timezone.now()

        try:
            if inbox_config.use_ssl:
                imap = imaplib.IMAP4_SSL(inbox_config.host, inbox_config.port)
            else:
                imap = imaplib.IMAP4(inbox_config.host, inbox_config.port)

            imap.login(inbox_config.username, inbox_config.password)
            imap.select(inbox_config.folder or "INBOX")

            # Search for unread emails
            status, search_data = imap.search(None, "UNSEEN")
            if status != "OK" or not search_data or not search_data[0]:
                if inbox_config.pk:
                    inbox_config.last_checked_at = now
                    inbox_config.last_status = "Checked (0 unread)"
                    inbox_config.save(update_fields=["last_checked_at", "last_status"])
                imap.logout()
                return results

            msg_ids = search_data[0].split()

            for msg_id in msg_ids:
                fetch_status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if fetch_status != "OK" or not msg_data:
                    continue

                raw_email_bytes = None
                for part in msg_data:
                    if isinstance(part, tuple) and len(part) >= 2:
                        raw_email_bytes = part[1]
                        break

                if not raw_email_bytes:
                    continue

                # Process the email through our cryptographic validator
                res = process_inbound_email_bytes(raw_email_bytes)
                results.append(res)

                if mark_seen:
                    imap.store(msg_id, "+FLAGS", "(\\Seen)")

            imap.logout()

            if inbox_config.pk:
                inbox_config.last_checked_at = now
                inbox_config.processed_count += len(results)
                inbox_config.last_status = f"Processed {len(results)} new receipts at {now.strftime('%H:%M:%S')}"
                inbox_config.save(update_fields=["last_checked_at", "last_status", "processed_count"])

        except Exception as e:
            err_msg = f"Error polling {inbox_config.host}: {str(e)}"
            logger.error(err_msg)
            if inbox_config.pk:
                inbox_config.last_checked_at = now
                inbox_config.last_status = f"Error: {str(e)[:240]}"
                inbox_config.save(update_fields=["last_checked_at", "last_status"])

        return results

    @classmethod
    def poll_all_inboxes(cls) -> List[Dict[str, Any]]:
        """Polls all active configured mailboxes."""
        configs = cls.get_active_configs()
        all_results = []
        for cfg in configs:
            res = cls.poll_inbox(cfg)
            all_results.extend(res)
        return all_results
