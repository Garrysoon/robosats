from django.db import models
from django.utils import timezone


class TaprootEscrowContract(models.Model):
    class Status(models.IntegerChoices):
        CREATED = 0, "Created"
        WAITING_DEPOSIT = 1, "Waiting for deposit"
        FUNDED = 2, "Escrow funded"
        RELEASED = 3, "Released to buyer (cooperative)"
        DISPUTED = 4, "In dispute"
        RESOLVED = 5, "Arbitrated by coordinator"
        REFUNDED = 6, "Refunded to seller"

    order = models.OneToOneField(
        "api.Order",
        related_name="taproot_escrow_contract",
        on_delete=models.CASCADE,
    )

    address = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Derived 2-of-3 Taproot address (tb1p... or bc1p...)",
    )
    descriptor = models.TextField(
        help_text="Miniscript Taproot descriptor tr(coord, multi_a(2, maker, taker, coord))"
    )
    network = models.CharField(max_length=16, default="testnet")

    maker_pubkey = models.CharField(max_length=128, help_text="Maker public key / xpub")
    taker_pubkey = models.CharField(max_length=128, help_text="Taker public key / xpub")
    coordinator_pubkey = models.CharField(
        max_length=128, help_text="Coordinator public key / xpub"
    )

    required_sats = models.PositiveBigIntegerField(
        help_text="Total escrow amount in satoshis including collateral"
    )
    funded_sats = models.PositiveBigIntegerField(default=0)
    funding_txid = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    funding_vout = models.IntegerField(blank=True, null=True)
    funding_confirmed = models.BooleanField(default=False)
    confirmations_count = models.IntegerField(default=0)

    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.CREATED, db_index=True
    )

    payout_address = models.CharField(max_length=100, blank=True, default="")
    payout_psbt = models.TextField(
        blank=True, default="", help_text="Current base64 PSBT with partial signatures"
    )
    payout_txid = models.CharField(max_length=64, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Taproot Escrow Contract"
        verbose_name_plural = "Taproot Escrow Contracts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Taproot Escrow for Order #{self.order_id} - {self.get_status_display()} ({self.address})"
