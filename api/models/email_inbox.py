from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class EmailInboxConfig(models.Model):
    """
    Configuration model for inbound IMAP email receipt ingestion.
    Allows coordinator administrators to configure mailboxes where
    buyers send bank receipts directly from their mobile banking apps.
    """

    class Meta:
        verbose_name = _("Email Receipt Inbox")
        verbose_name_plural = _("Email Receipt Inboxes")

    host = models.CharField(
        verbose_name=_("IMAP Host"),
        max_length=255,
        default="imap.yandex.ru",
        help_text=_("IMAP server hostname (e.g., imap.yandex.ru, imap.gmail.com, imap.mail.ru)"),
    )
    port = models.PositiveIntegerField(
        verbose_name=_("IMAP Port"),
        default=993,
        help_text=_("IMAP server port (usually 993 for SSL)"),
    )
    username = models.CharField(
        verbose_name=_("Username / Login"),
        max_length=255,
        help_text=_("Email address / login used to authenticate with IMAP server"),
    )
    password = models.CharField(
        verbose_name=_("Password / App Token"),
        max_length=255,
        help_text=_("IMAP App Password or secret key"),
    )
    use_ssl = models.BooleanField(
        verbose_name=_("Use SSL/TLS"),
        default=True,
        help_text=_("Connect using SSL/TLS encryption"),
    )
    folder = models.CharField(
        verbose_name=_("Mailbox Folder"),
        max_length=100,
        default="INBOX",
        help_text=_("IMAP mailbox folder to inspect for unread bank receipts"),
    )
    public_receipt_email = models.CharField(
        verbose_name=_("Public Receipt Email"),
        max_length=255,
        blank=True,
        help_text=_("Public email address shown to traders in order view (e.g., pay@coordinator.org)"),
    )
    is_active = models.BooleanField(
        verbose_name=_("Active"),
        default=True,
        help_text=_("Enable or disable automated polling for this mailbox"),
    )
    last_checked_at = models.DateTimeField(
        verbose_name=_("Last Checked At"),
        null=True,
        blank=True,
    )
    last_status = models.CharField(
        verbose_name=_("Last Status"),
        max_length=255,
        default="Never checked",
    )
    processed_count = models.PositiveIntegerField(
        verbose_name=_("Processed Receipts Count"),
        default=0,
    )

    def get_display_receipt_address(self) -> str:
        """Returns the public email address if set, or falls back to the username."""
        return self.public_receipt_email.strip() or self.username.strip()

    def __str__(self):
        status = _("Active") if self.is_active else _("Inactive")
        return f"{self.get_display_receipt_address()} ({self.host}:{self.port}) - {status}"
