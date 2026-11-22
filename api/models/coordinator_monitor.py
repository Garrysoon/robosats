from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CoordinatorNode(models.Model):
    class Status(models.IntegerChoices):
        UNKNOWN = 0, _("Unknown")
        ONLINE = 1, _("Online")
        DEGRADED = 2, _("Degraded")
        OFFLINE = 3, _("Offline")

    alias = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    onion_url = models.CharField(max_length=255, blank=True, default="")
    clearnet_url = models.CharField(max_length=255, blank=True, null=True, default=None)
    nostr_pubkey = models.CharField(max_length=128, blank=True, default="")
    lightning_node_pubkey = models.CharField(max_length=128, blank=True, default="")

    is_active = models.BooleanField(default=True, help_text="Whether this coordinator is monitored")
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.UNKNOWN, db_index=True
    )

    last_response_time_ms = models.FloatField(null=True, blank=True)
    last_order_count = models.IntegerField(default=0)
    last_book_liquidity = models.BigIntegerField(default=0)
    version = models.CharField(max_length=64, blank=True, default="")
    lightning_status = models.CharField(max_length=64, blank=True, default="")
    last_error = models.TextField(blank=True, default="")

    last_seen_online = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Coordinator Node")
        verbose_name_plural = _("Coordinator Nodes")
        ordering = ["alias"]

    def __str__(self):
        return f"{self.name} ({self.alias}) - {self.get_status_display()}"

    @property
    def is_online(self) -> bool:
        return self.status == self.Status.ONLINE

    def calculate_uptime_24h(self) -> float:
        """Calculates percentage of successful (ONLINE) checks in the last 24 hours."""
        since = timezone.now() - timezone.timedelta(hours=24)
        total_checks = self.checks.filter(checked_at__gte=since).count()
        if total_checks == 0:
            return 100.0 if self.is_online else 0.0
        online_checks = self.checks.filter(
            checked_at__gte=since, status=self.Status.ONLINE
        ).count()
        return round((online_checks / total_checks) * 100.0, 1)


class CoordinatorCheckLog(models.Model):
    coordinator = models.ForeignKey(
        CoordinatorNode, related_name="checks", on_delete=models.CASCADE
    )
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.PositiveSmallIntegerField(
        choices=CoordinatorNode.Status.choices, default=CoordinatorNode.Status.UNKNOWN
    )
    response_time_ms = models.FloatField(default=0.0)
    http_status_code = models.IntegerField(null=True, blank=True)
    order_count = models.IntegerField(default=0)
    book_liquidity = models.BigIntegerField(default=0)
    state_changed = models.BooleanField(
        default=False,
        help_text="True if coordinator transitioned state (e.g. ONLINE -> OFFLINE)",
    )
    previous_status = models.PositiveSmallIntegerField(
        choices=CoordinatorNode.Status.choices, null=True, blank=True
    )
    error_message = models.TextField(blank=True, default="")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Coordinator Check Log")
        verbose_name_plural = _("Coordinator Check Logs")
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["coordinator", "-checked_at"]),
            models.Index(fields=["state_changed", "-checked_at"]),
        ]

    def __str__(self):
        return (
            f"Check [{self.coordinator.alias}] at {self.checked_at.strftime('%Y-%m-%d %H:%M:%S')} "
            f"- {CoordinatorNode.Status(self.status).label} ({self.response_time_ms:.1f}ms)"
        )
