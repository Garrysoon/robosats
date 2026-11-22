import time
import logging
from django.core.management.base import BaseCommand
from api.email_ingestion import BankReceiptEmailWatcher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Polls configured IMAP mailboxes for incoming bank receipts, validates DKIM, and links to orders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single polling cycle and exit immediately",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Polling interval in seconds for continuous mode (default: 60)",
        )

    def handle(self, *args, **options):
        run_once = options["once"]
        interval = options["interval"]

        self.stdout.write(self.style.NOTICE("Starting Bank Receipt Email Watcher (IMAP Ingestion)..."))

        configs = BankReceiptEmailWatcher.get_active_configs()
        if not configs:
            self.stdout.write(
                self.style.WARNING(
                    "No active EmailInboxConfig found in database or .env (IMAP_HOST, IMAP_USER, IMAP_PASSWORD)."
                )
            )

        while True:
            self.stdout.write(f"Polling active inboxes ({len(configs)} configured)...")
            results = BankReceiptEmailWatcher.poll_all_inboxes()

            if results:
                for res in results:
                    success = res.get("success", False)
                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Successfully matched order #{res.get('order_id')} "
                                f"from {res.get('domain')} (DKIM valid: {res.get('is_dkim_valid')})"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠ Unmatched email: {res.get('reason')}"
                            )
                        )
            else:
                self.stdout.write("No new unread receipts found.")

            if run_once:
                break

            time.sleep(interval)
