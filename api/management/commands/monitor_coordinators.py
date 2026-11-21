import time
from django.core.management.base import BaseCommand
from api.coordinator_monitor import CoordinatorMonitorService
from api.models.coordinator_monitor import CoordinatorNode


class Command(BaseCommand):
    help = "Monitor RoboSats federation coordinators for uptime, latency, order counts, and state changes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one check cycle across all coordinators and exit",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Interval in seconds between consecutive health checks (default: 60)",
        )
        parser.add_argument(
            "--alias",
            type=str,
            default=None,
            help="Check only a specific coordinator by alias (e.g. temple, lake)",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Force sync coordinators list from federation.json before checking",
        )

    def handle(self, *args, **options):
        service = CoordinatorMonitorService()

        if options["sync"] or CoordinatorNode.objects.count() == 0:
            self.stdout.write(self.style.NOTICE("Syncing coordinator list from federation.json..."))
            count = service.sync_coordinators_from_federation()
            self.stdout.write(self.style.SUCCESS(f"Synced {count} coordinators."))

        single_alias = options.get("alias")
        run_once = options.get("once", False)
        interval = max(5, options.get("interval", 60))

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting RoboSats Federation Coordinator Monitor (Interval: {interval}s)..."
            )
        )

        try:
            while True:
                self.stdout.write("\n" + "=" * 70)
                self.stdout.write(
                    f"Checking coordinators at {time.strftime('%Y-%m-%d %H:%M:%S')}..."
                )
                self.stdout.write("=" * 70)

                if single_alias:
                    try:
                        node = CoordinatorNode.objects.get(alias=single_alias)
                        logs = [service.check_coordinator(node)]
                    except CoordinatorNode.DoesNotExist:
                        self.stderr.write(
                            self.style.ERROR(f"Coordinator '{single_alias}' not found in database.")
                        )
                        return
                else:
                    logs = service.check_all()

                # Print formatted status table
                header = f"{'Alias':<12} | {'Status':<10} | {'Latency':<10} | {'Orders':<8} | {'State Changed':<14} | {'Version'}"
                self.stdout.write(header)
                self.stdout.write("-" * len(header))

                for log in logs:
                    node = log.coordinator
                    status_label = CoordinatorNode.Status(log.status).label
                    changed_str = "YES (!)" if log.state_changed else "no"
                    latency_str = f"{log.response_time_ms:.1f}ms" if log.response_time_ms else "N/A"

                    line = (
                        f"{node.alias:<12} | "
                        f"{status_label:<10} | "
                        f"{latency_str:<10} | "
                        f"{log.order_count:<8} | "
                        f"{changed_str:<14} | "
                        f"{node.version or 'N/A'}"
                    )

                    if log.status == CoordinatorNode.Status.ONLINE:
                        self.stdout.write(self.style.SUCCESS(line))
                    elif log.status == CoordinatorNode.Status.DEGRADED:
                        self.stdout.write(self.style.WARNING(line))
                    else:
                        self.stdout.write(self.style.ERROR(line))

                    if log.error_message:
                        self.stdout.write(f"   ↳ Error: {log.error_message[:120]}")

                if run_once:
                    break

                self.stdout.write(f"\nWaiting {interval} seconds until next sweep (Ctrl+C to stop)...")
                time.sleep(interval)

        except KeyboardInterrupt:
            self.stdout.write(self.style.NOTICE("\nCoordinator monitor stopped by user."))
