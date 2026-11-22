from django.db import models
from django.utils import timezone


class EmailInboxConfig(models.Model):
    """
    Configuration model for inbound IMAP email receipt ingestion.
    Allows coordinator administrators to configure mailboxes where
    buyers send bank receipts directly from their mobile banking apps.
    """

    class Meta:
        verbose_name = "Email Receipt Inbox"
        verbose_name_plural = "Email Receipt Inboxes"

    host = models.CharField(
        max_length=255,
        default="imap.yandex.ru",
        help_text="IMAP server hostname (e.g., imap.yandex.ru, imap.gmail.com, imap.mail.ru)",
    )
    port = models.PositiveIntegerField(default=993, help_text="IMAP server port (usually 993 for SSL)")
    username = models.CharField(
        max_length=255,
        help_text="Email address / login used to authenticate with IMAP server",
    )
    password = models.CharField(
        max_length=255,
        help_text="IMAP App Password or secret key",
    )
    use_ssl = models.BooleanField(
        default=True,
        help_text="Connect using SSL/TLS encryption",
    )
    folder = models.CharField(
        max_length=100,
        default="INBOX",
        help_text="IMAP mailbox folder to inspect for unread bank receipts",
    )
    public_receipt_email = models.CharField(
        max_length=255,
        blank=True,
        help_text="Public email address shown to traders in order view (e.g., pay@coordinator.org)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable or disable automated polling for this mailbox",
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=255, default="Never checked")
    processed_count = models.PositiveIntegerField(default=0)

    def get_display_receipt_address(self) -> str:
        """Returns the public email address if set, or falls back to the username."""
        return self.public_receipt_email.strip() or self.username.strip()

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.get_display_receipt_address()} ({self.host}:{self.port}) - {status}"
