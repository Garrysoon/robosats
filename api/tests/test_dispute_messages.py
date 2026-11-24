from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from api.models import Order, Robot, Currency, DisputeMessage


class DisputeMessagesTestCase(TestCase):
    def setUp(self):
        self.maker_user = User.objects.create_user(username="maker_robot", password="password")
        self.taker_user = User.objects.create_user(username="taker_robot", password="password")
        self.admin_user = User.objects.create_superuser(username="admin_user", password="adminpassword")

        self.maker_robot = getattr(self.maker_user, "robot", None) or Robot.objects.filter(user=self.maker_user).first()
        self.taker_robot = getattr(self.taker_user, "robot", None) or Robot.objects.filter(user=self.taker_user).first()
        self.currency = Currency.objects.create(currency=17)  # RUB

        self.order = Order.objects.create(
            maker=self.maker_user,
            taker=self.taker_user,
            type=Order.Types.BUY,
            status=Order.Status.DIS,
            is_disputed=True,
            amount=10000.0,
            currency=self.currency,
            expires_at=timezone.now() + timedelta(hours=2),
            maker_statement="Maker: I paid 10000 RUB via SBP.",
            taker_statement="Taker: Did not receive the funds.",
        )

    def test_dispute_message_creation_and_isolation(self):
        # 1. Coordinator messages Maker
        m_msg = DisputeMessage.objects.create(
            order=self.order,
            party=DisputeMessage.Party.MAKER,
            sender_type=DisputeMessage.SenderType.COORDINATOR,
            sender_user=self.admin_user,
            text="Please upload bank PDF receipt.",
        )
        self.assertEqual(m_msg.party, "maker")
        self.assertEqual(m_msg.sender_type, "coordinator")

        # 2. Coordinator messages Taker
        t_msg = DisputeMessage.objects.create(
            order=self.order,
            party=DisputeMessage.Party.TAKER,
            sender_type=DisputeMessage.SenderType.COORDINATOR,
            sender_user=self.admin_user,
            text="Please check incoming transfers between 14:00 and 15:00.",
        )
        self.assertEqual(t_msg.party, "taker")

        # 3. Isolation verification: Maker only sees Maker messages
        maker_messages = list(self.order.dispute_messages.filter(party=DisputeMessage.Party.MAKER))
        self.assertIn(m_msg, maker_messages)
        self.assertNotIn(t_msg, maker_messages)

        # 4. Isolation verification: Taker only sees Taker messages
        taker_messages = list(self.order.dispute_messages.filter(party=DisputeMessage.Party.TAKER))
        self.assertIn(t_msg, taker_messages)
        self.assertNotIn(m_msg, taker_messages)

    def test_send_dispute_message_admin_view(self):
        client = Client()
        client.force_login(self.admin_user)

        url = f"/coordinator/api/order/{self.order.id}/send_dispute_message/"
        resp = client.post(url, {
            "party": "maker",
            "message_text": "Coordinator request: Provide payment ID.",
        })
        self.assertEqual(resp.status_code, 302)

        # Verify created
        msg = DisputeMessage.objects.filter(order=self.order, party="maker").first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.text, "Coordinator request: Provide payment ID.")
        self.assertEqual(msg.sender_type, DisputeMessage.SenderType.COORDINATOR)

    def test_send_dispute_message_non_staff_forbidden(self):
        client = Client()
        client.force_login(self.maker_user)  # Not staff

        url = f"/coordinator/api/order/{self.order.id}/send_dispute_message/"
        resp = client.post(url, {
            "party": "maker",
            "message_text": "Attempt to bypass staff check",
        })
        # Django admin_view redirects non-staff to login (302) or returns 403
        self.assertIn(resp.status_code, [302, 403])
        # Ensure no message was created by non-staff
        self.assertEqual(DisputeMessage.objects.filter(text="Attempt to bypass staff check").count(), 0)

    def test_dispute_cockpit_renders_isolated_channels(self):
        from api.admin import OrderAdmin
        from unfold.admin import ModelAdmin
        from django.contrib.admin.sites import AdminSite

        site = AdminSite()
        admin_instance = OrderAdmin(Order, site)

        DisputeMessage.objects.create(
            order=self.order,
            party=DisputeMessage.Party.MAKER,
            sender_type=DisputeMessage.SenderType.COORDINATOR,
            sender_user=self.admin_user,
            text="Special inquiry to maker only",
        )
        DisputeMessage.objects.create(
            order=self.order,
            party=DisputeMessage.Party.TAKER,
            sender_type=DisputeMessage.SenderType.COORDINATOR,
            sender_user=self.admin_user,
            text="Special inquiry to taker only",
        )

        cockpit_html = admin_instance.dispute_cockpit(self.order)
        self.assertIn("КАНАЛ: МЕЙКЕРУ", cockpit_html)
        self.assertIn("КАНАЛ: ТЕЙКЕРУ", cockpit_html)
        self.assertIn("Special inquiry to maker only", cockpit_html)
        self.assertIn("Special inquiry to taker only", cockpit_html)
        self.assertIn("Изолирован", cockpit_html)
