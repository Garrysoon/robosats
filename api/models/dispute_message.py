from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .order import Order


class DisputeMessage(models.Model):
    """
    Isolated dispute communication between Coordinator and individual counterparties (Maker/Taker).
    Guarantees privacy: Maker and Taker have separate communication channels with the arbitrator
    and cannot see each other's private dispute messages or evidence disclosures.
    """

    class Party(models.TextChoices):
        MAKER = "maker", _("Мейкер")
        TAKER = "taker", _("Тейкер")

    class SenderType(models.TextChoices):
        COORDINATOR = "coordinator", _("Координатор (Арбитр)")
        PEER = "peer", _("Участник сделки")

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="dispute_messages",
        verbose_name=_("Сделка"),
    )
    party = models.CharField(
        max_length=10,
        choices=Party.choices,
        verbose_name=_("Канал участника"),
        help_text=_("Определяет изолированный канал диалога: с Мейкером или с Тейкером."),
    )
    sender_type = models.CharField(
        max_length=15,
        choices=SenderType.choices,
        verbose_name=_("Тип отправителя"),
    )
    sender_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Пользователь"),
    )
    text = models.TextField(
        verbose_name=_("Текст сообщения"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Время отправки"),
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_("Прочитано"),
    )

    class Meta:
        verbose_name = _("Сообщение спора")
        verbose_name_plural = _("Сообщения споров")
        ordering = ["created_at"]

    def __str__(self):
        return f"Order #{self.order_id} [{self.party}] {self.sender_type}: {self.text[:30]}"
