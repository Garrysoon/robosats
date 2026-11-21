import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.coordinator_monitor import CoordinatorMonitorService

try:
    from api.models.coordinator_monitor import CoordinatorCheckLog, CoordinatorNode
except ImportError:
    class CoordinatorNode:
        class Status:
            UNKNOWN = 0
            ONLINE = 1
            DEGRADED = 2
            OFFLINE = 3
    class CoordinatorCheckLog:
        pass


class CoordinatorMonitorTestCase(unittest.TestCase):
    def setUp(self):
        self.service = CoordinatorMonitorService(proxy_url="socks5h://127.0.0.1:9050")
        import api.coordinator_monitor as cm
        if cm.CoordinatorCheckLog is None:
            cm.CoordinatorCheckLog = MagicMock()
        if cm.CoordinatorNode is None:
            cm.CoordinatorNode = CoordinatorNode

    def test_sync_coordinators_from_federation_parsing(self):
        # Test loading and parsing federation JSON
        federation_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "federation.json"
        )
        self.assertTrue(os.path.exists(federation_path))
        import json

        with open(federation_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("temple", data)
        self.assertIn("lake", data)
        self.assertIn("gumpellite", data)
        self.assertTrue(data["temple"]["mainnet"]["onion"].endswith(".onion"))

    @patch("requests.Session.get")
    def test_check_coordinator_online(self, mock_get):
        # Mock successful /api/info/ response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "version": "0.8.8-alpha",
            "node": {"status": "ok"},
            "num_public_buy_orders": 5,
            "num_public_sell_orders": 7,
            "book_liquidity": 12500000,
        }
        mock_get.return_value = mock_response

        # Mock CoordinatorNode instance
        node = MagicMock(spec=CoordinatorNode)
        node.alias = "test_coord"
        node.clearnet_url = "https://coord.example.com"
        node.onion_url = "http://testcoord.onion"
        node.status = CoordinatorNode.Status.UNKNOWN
        node.save = MagicMock()

        with patch("api.coordinator_monitor.CoordinatorCheckLog.objects.create") as mock_log_create:
            mock_log = MagicMock(spec=CoordinatorCheckLog)
            mock_log.status = CoordinatorNode.Status.ONLINE
            mock_log.order_count = 12
            mock_log_create.return_value = mock_log

            log = self.service.check_coordinator(node)
            self.assertEqual(node.status, CoordinatorNode.Status.ONLINE)
            self.assertEqual(node.last_order_count, 12)
            self.assertEqual(node.last_book_liquidity, 12500000)
            self.assertEqual(node.version, "0.8.8-alpha")

    @patch("requests.Session.get")
    def test_check_coordinator_offline(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("Connection refused")

        node = MagicMock(spec=CoordinatorNode)
        node.alias = "offline_coord"
        node.clearnet_url = "https://offline.example.com"
        node.onion_url = ""
        node.status = CoordinatorNode.Status.ONLINE
        node.save = MagicMock()

        with patch("api.coordinator_monitor.CoordinatorCheckLog.objects.create") as mock_log_create:
            mock_log = MagicMock(spec=CoordinatorCheckLog)
            mock_log.status = CoordinatorNode.Status.OFFLINE
            mock_log.state_changed = True
            mock_log_create.return_value = mock_log

            log = self.service.check_coordinator(node)
            self.assertEqual(node.status, CoordinatorNode.Status.OFFLINE)
            self.assertTrue(mock_log.state_changed)
            self.assertIn("Connection refused", node.last_error)


if __name__ == "__main__":
    unittest.main()
