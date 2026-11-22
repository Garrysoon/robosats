import logging
from django.core.management.base import BaseCommand
from api.dispute_automation import DisputeAutomationService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scans disputed RoboSats orders and automatically resolves those meeting high-confidence criteria (DKIM, 24h silence SLA)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate dispute arbitration without applying changes to the database",
        )
        parser.add_argument(
            "--silence-hours",
            type=int,
            default=24,
            help="Number of hours of counterparty silence required to trigger auto-default (default: 24)",
        )
        parser.add_argument(
            "--dkim-veto-minutes",
            type=int,
            default=30,
            help="Veto window in minutes after valid DKIM receipt before auto-release (default: 30)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        silence_hours = options["silence_hours"]
        dkim_veto_minutes = options["dkim_veto_minutes"]

        mode_str = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.NOTICE(
                f"{mode_str}Starting automated dispute arbitration scan (SLA: {silence_hours}h, DKIM veto: {dkim_veto_minutes}m)..."
            )
        )

        results = DisputeAutomationService.scan_and_auto_resolve(
            silence_hours=silence_hours,
            dkim_veto_minutes=dkim_veto_minutes,
            dry_run=dry_run,
        )

        if not results:
            self.stdout.write(self.style.SUCCESS("No disputed orders met automated resolution criteria."))
            return

        for res in results:
            order_id = res["order_id"]
            action = res["action"]
            confidence = int(res["confidence"] * 100)
            reason = res["reason"]

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"[SIMULATED] Order #{order_id} -> {action} ({confidence}% confidence): {reason}"
                    )
                )
            else:
                applied = res.get("applied", False)
                msg = res.get("message", "")
                if applied:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[RESOLVED] Order #{order_id} -> {action} ({confidence}% confidence): {msg}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[FAILED] Order #{order_id} -> {action}: {msg}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS(f"Completed dispute arbitration scan. Processed: {len(results)} orders."))
