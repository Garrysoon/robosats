import time
from datetime import datetime
from datetime import timezone as datetime_timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.contrib.auth import get_user_model

from api.models import Robot
from api.utils import (
    validate_action_signature,
    validate_signed_action_timestamp,
    ACTION_SIGNATURE_WINDOW,
)

User = get_user_model()


class ActionSignatureTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_robot_sig")
        self.robot = self.user.robot
        self.robot.public_key = "FAKE_PGP_KEY"
        self.robot.save()

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    def test_missing_signature_strict_mode(self):
        valid, err = validate_action_signature(self.user, "take:123:localdev", None)
        self.assertFalse(valid)
        self.assertEqual(err["error_code"], 1059)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", False)
    def test_missing_signature_shadow_mode(self):
        valid, err = validate_action_signature(self.user, "take:123:localdev", None)
        self.assertTrue(valid)
        self.assertIsNone(err)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    @patch("api.utils.verify_signed_message")
    def test_invalid_pgp_signature(self, mock_verify):
        mock_verify.return_value = (False, None)
        valid, err = validate_action_signature(
            self.user, "take:123:localdev", "BAD_SIG"
        )
        self.assertFalse(valid)
        self.assertEqual(err["error_code"], 1048)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    @patch("api.utils.verify_signed_message")
    def test_mismatched_content_signature(self, mock_verify):
        mock_verify.return_value = (True, "take:999:localdev")
        valid, err = validate_action_signature(
            self.user, "take:123:localdev", "VALID_SIG_FOR_OTHER"
        )
        self.assertFalse(valid)
        self.assertEqual(err["error_code"], 1048)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    @patch("api.utils.verify_signed_message")
    def test_valid_action_signature(self, mock_verify):
        mock_verify.return_value = (True, "take:123:localdev")
        valid, err = validate_action_signature(
            self.user, "take:123:localdev", "VALID_SIG"
        )
        self.assertTrue(valid)
        self.assertIsNone(err)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    @patch("api.utils.get_federation_short_alias", return_value="localdev")
    @patch("api.utils.verify_signed_message")
    def test_timed_signature_wrong_alias(self, mock_verify, mock_alias):
        now_ts = int(time.time())
        mock_verify.return_value = (True, f"make:othercoordinator:{now_ts}")
        valid, err = validate_signed_action_timestamp(
            self.user, "make", "VALID_SIG"
        )
        self.assertFalse(valid)
        self.assertEqual(err["error_code"], 1061)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    @patch("api.utils.get_federation_short_alias", return_value="localdev")
    @patch("api.utils.verify_signed_message")
    def test_timed_signature_expired(self, mock_verify, mock_alias):
        old_ts = int(time.time()) - (ACTION_SIGNATURE_WINDOW + 50)
        mock_verify.return_value = (True, f"make:localdev:{old_ts}")
        valid, err = validate_signed_action_timestamp(
            self.user, "make", "VALID_SIG"
        )
        self.assertFalse(valid)
        self.assertEqual(err["error_code"], 1060)

    @patch("api.utils.REQUIRE_SIGNED_ACTIONS", True)
    @patch("api.utils.get_federation_short_alias", return_value="localdev")
    @patch("api.utils.verify_signed_message")
    def test_timed_signature_valid(self, mock_verify, mock_alias):
        now_ts = int(time.time())
        mock_verify.return_value = (True, f"make:localdev:{now_ts}")
        valid, err = validate_signed_action_timestamp(
            self.user, "make", "VALID_SIG"
        )
        self.assertTrue(valid)
        self.assertIsNone(err)
