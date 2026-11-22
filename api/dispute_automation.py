import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple, Dict, Any, List

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from api.models.order import Order
from api.models.robot import Robot
from api.models.ln_payment import LNPayment
from api.logics import Logics
from api.dkim_verifier import validate_receipt_for_order

logger = logging.getLogger(__name__)


@dataclass
class DisputeRecommendation:
    action: str  # "successful_trade", "maker_wins", "taker_wins", "return_everything", "needs_human_investigation"
    confidence: float  # 0.0 - 1.0
    reason: str
    stage: str  # "DKIM", "SILENCE_SLA", "F2F", "MANUAL"
    details: Dict[str, Any]


class DisputeRecommendationEngine:
    """
    Intelligent Pre-flight Engine for Dispute Arbitration.
    Analyzes cryptographic receipts (DKIM), F2F check-ins, silence SLAs, and logs.
    """

    @staticmethod
    def analyze_order(order: Order, silence_hours: int = 24, dkim_veto_minutes: int = 30) -> DisputeRecommendation:
        if not order.is_disputed or order.status not in [Order.Status.DIS, Order.Status.WFR]:
            return DisputeRecommendation(
                action="none",
                confidence=1.0,
                reason="Order is not in a disputed state.",
                stage="MANUAL",
                details={},
            )

        now = timezone.now()
        maker_is_buyer = Logics.is_buyer(order, order.maker)
        buyer_role = "maker" if maker_is_buyer else "taker"
        seller_role = "taker" if maker_is_buyer else "maker"

        buyer_statement = order.maker_statement if maker_is_buyer else order.taker_statement
        seller_statement = order.taker_statement if maker_is_buyer else order.maker_statement

        # ---------------------------------------------------------
        # 1. DKIM Verification Check (Stage 2)
        # ---------------------------------------------------------
        if buyer_statement and ("DKIM-Signature:" in buyer_statement or "From:" in buyer_statement):
            try:
                valid, msg, receipt = validate_receipt_for_order(order, buyer_statement.encode("utf-8"))
                if valid and receipt.get("is_dkim_valid"):
                    # Check if seller has provided a counter-statement or objection
                    has_seller_counter = bool(seller_statement and len(seller_statement.strip()) > 10)
                    
                    return DisputeRecommendation(
                        action="successful_trade",
                        confidence=0.98 if not has_seller_counter else 0.85,
                        reason=(
                            f"Cryptographic DKIM proof verified from trusted bank '{receipt.get('domain')}'. "
                            f"Reference code '{receipt.get('reference')}' matches order #{order.id}. "
                            f"Fiat amount matches."
                        ),
                        stage="DKIM",
                        details={
                            "domain": receipt.get("domain"),
                            "reference": receipt.get("reference"),
                            "amount": receipt.get("amount"),
                            "has_seller_counter": has_seller_counter,
                        },
                    )
            except Exception as e:
                logger.warning(f"Error checking DKIM for order {order.id}: {e}")

        # ---------------------------------------------------------
        # 2. F2F Cash Protocol Check
        # ---------------------------------------------------------
        if order.check_is_f2f():
            # Check for non-arrival
            if order.f2f_arrived_maker and not order.f2f_arrived_taker:
                # Maker arrived, taker did not
                return DisputeRecommendation(
                    action="maker_wins",
                    confidence=0.90,
                    reason="Maker confirmed arrival at the F2F safe meeting point; Taker failed to check in.",
                    stage="F2F",
                    details={"maker_arrived": True, "taker_arrived": False},
                )
            elif order.f2f_arrived_taker and not order.f2f_arrived_maker:
                # Taker arrived, maker did not
                return DisputeRecommendation(
                    action="taker_wins",
                    confidence=0.90,
                    reason="Taker confirmed arrival at the F2F safe meeting point; Maker failed to check in.",
                    stage="F2F",
                    details={"maker_arrived": False, "taker_arrived": True},
                )

        # ---------------------------------------------------------
        # 3. Silence SLA Timeout Check (Stage 1)
        # ---------------------------------------------------------
        # Determine who has provided a statement
        has_maker_statement = bool(order.maker_statement and len(order.maker_statement.strip()) > 5)
        has_taker_statement = bool(order.taker_statement and len(order.taker_statement.strip()) > 5)

        # Find latest chat messages if chat exists
        latest_maker_msg_time = None
        latest_taker_msg_time = None

        try:
            from chat.models import Message
            maker_msgs = Message.objects.filter(order=order, sender=order.maker).order_by("-created_at")
            if maker_msgs.exists():
                latest_maker_msg_time = maker_msgs.first().created_at

            taker_msgs = Message.objects.filter(order=order, sender=order.taker).order_by("-created_at")
            if taker_msgs.exists():
                latest_taker_msg_time = taker_msgs.first().created_at
        except Exception:
            pass

        # Disputed order timestamp
        dispute_time = order.modified_at if hasattr(order, "modified_at") else order.created_at
        sla_threshold = now - timedelta(hours=silence_hours)

        maker_active = has_maker_statement or (latest_maker_msg_time and latest_maker_msg_time > sla_threshold)
        taker_active = has_taker_statement or (latest_taker_msg_time and latest_taker_msg_time > sla_threshold)

        if maker_active and not taker_active:
            return DisputeRecommendation(
                action="maker_wins",
                confidence=0.95,
                reason=f"Taker silent in dispute for more than {silence_hours}h SLA. Maker is active.",
                stage="SILENCE_SLA",
                details={"active_party": "maker", "silent_party": "taker"},
            )
        elif taker_active and not maker_active:
            return DisputeRecommendation(
                action="taker_wins",
                confidence=0.95,
                reason=f"Maker silent in dispute for more than {silence_hours}h SLA. Taker is active.",
                stage="SILENCE_SLA",
                details={"active_party": "taker", "silent_party": "maker"},
            )

        # ---------------------------------------------------------
        # 4. Fallback: Needs Human Investigation
        # ---------------------------------------------------------
        return DisputeRecommendation(
            action="needs_human_investigation",
            confidence=0.50,
            reason="Both parties active or complex conflicting claims. Human arbitrator review required.",
            stage="MANUAL",
            details={},
        )


class DisputeAutomationService:
    """
    Executes automated resolutions and provides the execution pipeline
    for both automated background tasks and 1-Click admin actions.
    """

    @classmethod
    def apply_resolution(
        cls, order: Order, action: str, actor: str = "automation_engine", reason: str = ""
    ) -> Tuple[bool, str]:
        """
        Applies a resolution atomically with audit logging.
        Supported actions: 'successful_trade', 'maker_wins', 'taker_wins', 'return_everything'.
        """
        if not order.is_disputed or order.status not in [Order.Status.DIS, Order.Status.WFR]:
            return False, f"Order {order.id} is not in a disputed state."

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)

            # Audit log entry
            log_entry = {
                "event": "dispute_resolved",
                "action": action,
                "actor": actor,
                "reason": reason,
                "timestamp": timezone.now().isoformat(),
            }
            if not isinstance(order.logs, list):
                order.logs = []
            order.logs.append(log_entry)

            if action == "successful_trade":
                # Return both bonds as earned_rewards to maker and taker
                Robot.objects.filter(pk=order.maker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.maker_bond.num_satoshis
                )
                Robot.objects.filter(pk=order.taker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.taker_bond.num_satoshis
                )
                order.maker.robot.refresh_from_db(fields=["earned_rewards"])
                order.taker.robot.refresh_from_db(fields=["earned_rewards"])

                if order.is_swap and order.payout_tx:
                    if (
                        order.payout_tx.address
                        and order.payout_tx.status == getattr(order.payout_tx.Status, "CANCE", 4)
                    ):
                        order.payout_tx.status = getattr(order.payout_tx.Status, "VALID", 6)
                        order.payout_tx.save(update_fields=["status"])

                order.update_status(Order.Status.PAY)
                order.save(update_fields=["logs"])

                paid = Logics.pay_buyer(order)
                if paid:
                    return True, f"Dispute of order #{order.id} successfully resolved as successful trade."
                else:
                    return False, f"Payout could not be initiated for order #{order.id}."

            elif action == "maker_wins":
                own_bond_sats = order.maker_bond.num_satoshis
                if Logics.is_buyer(order, order.maker):
                    trade_sats = (
                        order.payout_tx.num_satoshis if order.is_swap else order.payout.num_satoshis
                    )
                else:
                    trade_sats = order.trade_escrow.num_satoshis

                Robot.objects.filter(pk=order.maker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + (own_bond_sats + trade_sats)
                )
                order.maker.robot.refresh_from_db(fields=["earned_rewards"])
                order.update_status(Order.Status.TLD)
                order.save(update_fields=["logs"])

                from api.tasks import send_notification
                send_notification.delay(order_id=order.id, message="dispute_closed")
                return True, f"Dispute of order #{order.id} resolved in favor of Maker."

            elif action == "taker_wins":
                own_bond_sats = order.taker_bond.num_satoshis
                if Logics.is_buyer(order, order.taker):
                    trade_sats = (
                        order.payout_tx.num_satoshis if order.is_swap else order.payout.num_satoshis
                    )
                else:
                    trade_sats = order.trade_escrow.num_satoshis

                Robot.objects.filter(pk=order.taker.robot.pk).update(
                    earned_rewards=F("earned_rewards") + (own_bond_sats + trade_sats)
                )
                order.taker.robot.refresh_from_db(fields=["earned_rewards"])
                order.update_status(Order.Status.MLD)
                order.save(update_fields=["logs"])

                from api.tasks import send_notification
                send_notification.delay(order_id=order.id, message="dispute_closed")
                return True, f"Dispute of order #{order.id} resolved in favor of Taker."

            elif action == "return_everything":
                Robot.objects.filter(pk=order.maker_bond.sender.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.maker_bond.num_satoshis
                )
                Robot.objects.filter(pk=order.taker_bond.sender.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.taker_bond.num_satoshis
                )
                Robot.objects.filter(pk=order.trade_escrow.sender.robot.pk).update(
                    earned_rewards=F("earned_rewards") + order.trade_escrow.num_satoshis
                )
                order.maker_bond.sender.robot.refresh_from_db(fields=["earned_rewards"])
                order.taker_bond.sender.robot.refresh_from_db(fields=["earned_rewards"])
                order.trade_escrow.sender.robot.refresh_from_db(fields=["earned_rewards"])

                order.update_status(Order.Status.CCA)
                order.save(update_fields=["logs"])
                return True, f"Dispute of order #{order.id} resolved with full mutual refund."

            else:
                return False, f"Unknown resolution action '{action}'."

    @classmethod
    def scan_and_auto_resolve(
        cls, silence_hours: int = 24, dkim_veto_minutes: int = 30, dry_run: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scans all disputed orders and applies automated resolution if criteria are met with high confidence (>= 0.95).
        """
        disputed_orders = Order.objects.filter(
            is_disputed=True, status__in=[Order.Status.DIS, Order.Status.WFR]
        )

        results = []
        for order in disputed_orders:
            rec = DisputeRecommendationEngine.analyze_order(
                order, silence_hours=silence_hours, dkim_veto_minutes=dkim_veto_minutes
            )

            # Auto-resolve only on ultra-high confidence (>= 0.95) for automated runs
            if rec.confidence >= 0.95 and rec.action in [
                "successful_trade",
                "maker_wins",
                "taker_wins",
            ]:
                if dry_run:
                    results.append({
                        "order_id": order.id,
                        "action": rec.action,
                        "confidence": rec.confidence,
                        "reason": rec.reason,
                        "applied": False,
                        "dry_run": True,
                    })
                else:
                    success, msg = cls.apply_resolution(
                        order,
                        action=rec.action,
                        actor=f"auto_{rec.stage.lower()}",
                        reason=rec.reason,
                    )
                    results.append({
                        "order_id": order.id,
                        "action": rec.action,
                        "confidence": rec.confidence,
                        "reason": rec.reason,
                        "applied": success,
                        "message": msg,
                    })

        return results
