from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from api.models import Order, Robot
from chat.models import ChatRoom, Message
from api.tasks import nostr_send_chat_message_task

User = get_user_model()


class NostrChatRelayTestCase(TestCase):
    def setUp(self):
        self.maker = User.objects.create_user(username="maker_nostr")
        self.maker.robot.nostr_pubkey = "npub1maker000000000000000000000000000000000000000000000000000000"
        self.maker.robot.save()

        self.taker = User.objects.create_user(username="taker_nostr")
        self.taker.robot.nostr_pubkey = "npub1taker000000000000000000000000000000000000000000000000000000"
        self.taker.robot.save()

        self.order = Order.objects.create(
            maker=self.maker,
            taker=self.taker,
            type=Order.Types.BUY,
            amount=100.0,
            status=Order.Status.CHA,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        self.chatroom = ChatRoom.objects.create(
            id=self.order.id,
            order=self.order,
            maker=self.maker,
            taker=self.taker,
        )
        self.msg = Message.objects.create(
            index=1,
            order=self.order,
            chatroom=self.chatroom,
            sender=self.maker,
            receiver=self.taker,
            PGP_message="-----BEGIN PGP MESSAGE-----\ntest\n-----END PGP MESSAGE-----",
        )

    @patch("api.nostr.Nostr.send_chat_message_event", new_callable=AsyncMock)
    def test_nostr_chat_mirroring_task(self, mock_send):
        nostr_send_chat_message_task(self.msg.id)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs.get("order") or args[2], self.order)
        self.assertEqual(kwargs.get("index") or args[4], 1)

    def test_security_headers_in_settings(self):
        self.assertTrue(getattr(settings, "SECURE_CONTENT_TYPE_NOSNIFF", False))
        self.assertTrue(getattr(settings, "SECURE_BROWSER_XSS_FILTER", False))
        self.assertEqual(getattr(settings, "X_FRAME_OPTIONS", None), "DENY")
