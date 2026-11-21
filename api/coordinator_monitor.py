import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

try:
    from django.conf import settings
except ImportError:
    settings = None

try:
    from django.utils import timezone
except ImportError:
    from datetime import datetime as _dt, timezone as _tz
    class _MockTimezone:
        @staticmethod
        def now():
            return _dt.now(_tz.utc)
        @staticmethod
        def timedelta(**kwargs):
            from datetime import timedelta
            return timedelta(**kwargs)
    timezone = _MockTimezone()

try:
    from api.models.coordinator_monitor import CoordinatorCheckLog, CoordinatorNode
except ImportError:
    CoordinatorCheckLog = None
    CoordinatorNode = None

logger = logging.getLogger(__name__)

DEFAULT_FEDERATION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "api", "federation.json"
)


class CoordinatorMonitorService:
    """
    Monitoring service that continuously tracks the availability, latency,
    order book capacity, and state transitions of all RoboSats coordinators
    in the federation.
    """

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url or self._detect_tor_proxy()

    @staticmethod
    def _detect_tor_proxy() -> Optional[str]:
        """Detect configured Tor socks5 proxy from environment or Django settings."""
        # Check settings
        if hasattr(settings, "TOR_PROXY") and settings.TOR_PROXY:
            return settings.TOR_PROXY
        if hasattr(settings, "TOR_SOCKS_PROXY") and settings.TOR_SOCKS_PROXY:
            return settings.TOR_SOCKS_PROXY

        # Check env vars
        env_proxy = os.getenv("TOR_PROXY") or os.getenv("TOR_SOCKS_PROXY")
        if env_proxy:
            return env_proxy

        # Check standard default 9050 or 9051 port
        tor_host = os.getenv("TOR_HOST", "127.0.0.1")
        tor_port = os.getenv("TOR_PORT", "9050")
        candidate = f"socks5h://{tor_host}:{tor_port}"
        return candidate

    def _get_session(self, is_onion: bool = False) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "RoboSats-Coordinator-Monitor/1.0",
                "Accept": "application/json",
            }
        )
        if is_onion and self.proxy_url:
            session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }
        return session

    def sync_coordinators_from_federation(
        self, federation_path: Optional[str] = None
    ) -> int:
        """
        Loads coordinators from federation.json and syncs them with CoordinatorNode records.
        Returns count of synced nodes.
        """
        path = federation_path or DEFAULT_FEDERATION_PATH
        if not os.path.exists(path):
            alt_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "frontend",
                "static",
                "federation.json",
            )
            if os.path.exists(alt_path):
                path = alt_path
            else:
                logger.error(f"Federation file not found at {path}")
                return 0

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        synced = 0
        for alias, info in data.items():
            if not isinstance(info, dict):
                continue

            mainnet = info.get("mainnet", {}) or {}
            onion_url = mainnet.get("onion") or ""
            clearnet_url = mainnet.get("clearnet") or None
            nostr_pubkey = info.get("nostrHexPubkey") or ""
            mainnet_nodes = info.get("mainnetNodesPubkeys") or []
            lightning_node = mainnet_nodes[0] if mainnet_nodes else ""

            node, _ = CoordinatorNode.objects.update_or_create(
                alias=alias,
                defaults={
                    "name": info.get("longAlias") or alias.capitalize(),
                    "description": info.get("description", "")[:500],
                    "onion_url": onion_url,
                    "clearnet_url": clearnet_url,
                    "nostr_pubkey": nostr_pubkey,
                    "lightning_node_pubkey": lightning_node,
                    "is_active": True,
                },
            )
            synced += 1

        logger.info(f"Successfully synced {synced} coordinators from federation")
        return synced

    def check_coordinator(
        self, node: CoordinatorNode, timeout: float = 12.0
    ) -> CoordinatorCheckLog:
        """
        Performs a full health-check on a single coordinator:
        - Measures response time for /api/info/
        - Verifies /api/book/ availability
        - Extracts version, lightning status, and active order count
        - Detects state transitions (ONLINE -> DEGRADED -> OFFLINE)
        - Records CoordinatorCheckLog
        """
        # Determine candidate endpoints
        targets: List[Tuple[str, bool]] = []
        if node.clearnet_url:
            targets.append((node.clearnet_url.rstrip("/"), False))
        if node.onion_url:
            targets.append((node.onion_url.rstrip("/"), True))

        if not targets:
            log = CoordinatorCheckLog.objects.create(
                coordinator=node,
                status=CoordinatorNode.Status.OFFLINE,
                error_message="No clearnet or onion URL configured for coordinator",
                state_changed=(node.status != CoordinatorNode.Status.OFFLINE),
                previous_status=node.status,
            )
            node.status = CoordinatorNode.Status.OFFLINE
            node.last_checked_at = timezone.now()
            node.last_error = log.error_message
            node.save()
            return log

        best_status = CoordinatorNode.Status.OFFLINE
        best_latency_ms = 0.0
        http_code = None
        order_count = 0
        book_liquidity = 0
        version = ""
        ln_status = ""
        error_msg = ""
        raw_details: Dict = {}

        for base_url, is_onion in targets:
            session = self._get_session(is_onion=is_onion)
            info_url = f"{base_url}/api/info/"
            book_url = f"{base_url}/api/book/"

            start_t = time.perf_counter()
            try:
                res = session.get(info_url, timeout=timeout)
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                http_code = res.status_code

                if res.status_code == 200:
                    info_data = res.json()
                    version = str(info_data.get("version", ""))
                    ln_status = str(info_data.get("node", {}).get("status", "ok"))
                    buy_orders = int(info_data.get("num_public_buy_orders", 0) or 0)
                    sell_orders = int(info_data.get("num_public_sell_orders", 0) or 0)
                    order_count = buy_orders + sell_orders
                    book_liquidity = int(info_data.get("book_liquidity", 0) or 0)
                    raw_details["info"] = info_data

                    # Also verify /api/book/
                    try:
                        book_res = session.get(book_url, timeout=timeout / 2)
                        if book_res.status_code == 200:
                            book_data = book_res.json()
                            if isinstance(book_data, list):
                                order_count = len(book_data)
                            raw_details["book_verified"] = True
                    except Exception as e:
                        raw_details["book_error"] = str(e)

                    best_latency_ms = round(elapsed_ms, 2)
                    if best_latency_ms > 8000:
                        best_status = CoordinatorNode.Status.DEGRADED
                    else:
                        best_status = CoordinatorNode.Status.ONLINE
                    error_msg = ""
                    break  # Successful check found
                else:
                    error_msg = f"HTTP {res.status_code}: {res.text[:200]}"
                    best_status = CoordinatorNode.Status.DEGRADED

            except requests.RequestException as exc:
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                best_latency_ms = round(elapsed_ms, 2)
                error_msg = f"Network error ({base_url}): {str(exc)}"
                logger.debug(f"Coordinator {node.alias} check failed via {base_url}: {exc}")

        previous_status = node.status
        state_changed = previous_status != best_status

        if state_changed:
            try:
                prev_label = CoordinatorNode.Status(previous_status).label
            except Exception:
                prev_label = str(previous_status)
            try:
                new_label = CoordinatorNode.Status(best_status).label
            except Exception:
                new_label = str(best_status)
            logger.warning(
                f"[COORDINATOR STATE CHANGE] {node.alias}: {prev_label} -> {new_label} "
                f"(Latency: {best_latency_ms}ms, Orders: {order_count})"
            )

        now = timezone.now()
        node.status = best_status
        node.last_response_time_ms = best_latency_ms
        node.last_order_count = order_count
        node.last_book_liquidity = book_liquidity
        node.last_checked_at = now
        node.last_error = error_msg
        if version:
            node.version = version
        if ln_status:
            node.lightning_status = ln_status
        if best_status == CoordinatorNode.Status.ONLINE:
            node.last_seen_online = now

        node.save(
            update_fields=[
                "status",
                "last_response_time_ms",
                "last_order_count",
                "last_book_liquidity",
                "last_checked_at",
                "last_error",
                "version",
                "lightning_status",
                "last_seen_online",
            ]
        )

        log = CoordinatorCheckLog.objects.create(
            coordinator=node,
            checked_at=now,
            status=best_status,
            response_time_ms=best_latency_ms,
            http_status_code=http_code,
            order_count=order_count,
            book_liquidity=book_liquidity,
            state_changed=state_changed,
            previous_status=previous_status,
            error_message=error_msg,
            details=raw_details,
        )
        return log

    def check_all(self, timeout: float = 12.0, max_workers: int = 6) -> List[CoordinatorCheckLog]:
        """Runs concurrent checks on all active coordinator nodes."""
        nodes = list(CoordinatorNode.objects.filter(is_active=True))
        if not nodes:
            self.sync_coordinators_from_federation()
            nodes = list(CoordinatorNode.objects.filter(is_active=True))

        results: List[CoordinatorCheckLog] = []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(nodes) or 1)) as executor:
            future_to_node = {
                executor.submit(self.check_coordinator, node, timeout): node
                for node in nodes
            }
            for future in as_completed(future_to_node):
                try:
                    log = future.result()
                    results.append(log)
                except Exception as exc:
                    node = future_to_node[future]
                    logger.error(f"Error checking coordinator {node.alias}: {exc}")

        return results

    @staticmethod
    def get_federation_summary() -> dict:
        """Aggregates real-time federation health metrics."""
        nodes = CoordinatorNode.objects.filter(is_active=True)
        total = nodes.count()
        online = nodes.filter(status=CoordinatorNode.Status.ONLINE).count()
        degraded = nodes.filter(status=CoordinatorNode.Status.DEGRADED).count()
        offline = nodes.filter(status=CoordinatorNode.Status.OFFLINE).count()

        total_orders = sum(n.last_order_count for n in nodes)
        total_liquidity = sum(n.last_book_liquidity for n in nodes)

        valid_latencies = [
            n.last_response_time_ms
            for n in nodes
            if n.last_response_time_ms is not None and n.status == CoordinatorNode.Status.ONLINE
        ]
        avg_latency = round(sum(valid_latencies) / len(valid_latencies), 1) if valid_latencies else 0.0

        # Recent state changes (last 24 hours)
        since_24h = timezone.now() - timezone.timedelta(hours=24)
        recent_changes = (
            CoordinatorCheckLog.objects.filter(state_changed=True, checked_at__gte=since_24h)
            .select_related("coordinator")
            .order_by("-checked_at")[:20]
        )

        changes_list = []
        for ch in recent_changes:
            try:
                from_label = CoordinatorNode.Status(ch.previous_status).label
            except Exception:
                from_label = str(ch.previous_status)
            try:
                to_label = CoordinatorNode.Status(ch.status).label
            except Exception:
                to_label = str(ch.status)
            changes_list.append(
                {
                    "alias": ch.coordinator.alias,
                    "from_status": from_label,
                    "to_status": to_label,
                    "timestamp": ch.checked_at.isoformat(),
                    "response_time_ms": ch.response_time_ms,
                    "error": ch.error_message,
                }
            )

        coordinator_list = []
        for n in nodes:
            coordinator_list.append(
                {
                    "alias": n.alias,
                    "name": n.name,
                    "status": n.get_status_display(),
                    "status_code": n.status,
                    "onion_url": n.onion_url,
                    "clearnet_url": n.clearnet_url,
                    "response_time_ms": n.last_response_time_ms,
                    "order_count": n.last_order_count,
                    "book_liquidity_sats": n.last_book_liquidity,
                    "version": n.version,
                    "lightning_status": n.lightning_status,
                    "uptime_24h_percent": n.calculate_uptime_24h(),
                    "last_seen_online": (
                        n.last_seen_online.isoformat() if n.last_seen_online else None
                    ),
                    "last_checked_at": (
                        n.last_checked_at.isoformat() if n.last_checked_at else None
                    ),
                    "last_error": n.last_error,
                }
            )

        return {
            "total_coordinators": total,
            "online_coordinators": online,
            "degraded_coordinators": degraded,
            "offline_coordinators": offline,
            "average_latency_ms": avg_latency,
            "total_federation_orders": total_orders,
            "total_liquidity_sats": total_liquidity,
            "coordinators": coordinator_list,
            "recent_state_changes": changes_list,
            "generated_at": timezone.now().isoformat(),
        }
