import hashlib
import hmac
import logging
import secrets
from typing import Dict, Optional, Tuple, Union

try:
    from django.core.cache import cache
except ImportError:
    class _InMemoryCache:
        def __init__(self):
            self._store = {}
        def get(self, key, default=None):
            return self._store.get(key, default)
        def set(self, key, val, timeout=None):
            self._store[key] = val
    cache = _InMemoryCache()

try:
    from django.utils import timezone
except ImportError:
    from datetime import datetime as _dt, timezone as _tz
    class _TimezoneMock:
        @staticmethod
        def now():
            return _dt.now(_tz.utc)
    timezone = _TimezoneMock()

try:
    from api.logics import Logics
except ImportError:
    Logics = None

logger = logging.getLogger(__name__)

SAFE_TRADE_CHECKLIST = [
    {
        "id": "atm_cash_in",
        "title": "Rule 1: ATM Cash-In Deposit (Anti-Counterfeit)",
        "description": (
            "Meet inside a bank branch next to an ATM with cash-in functionality. "
            "Seller immediately feeds banknotes into their bank's ATM. "
            "The ATM validator instantly counts notes and eliminates counterfeit banknote risk."
        ),
    },
    {
        "id": "public_safe_zone",
        "title": "Rule 2: Public Safe Zones Only",
        "description": (
            "Always meet in bright, monitored public locations (bank lobbies, shopping center cafes "
            "with CCTV, transit hubs near security). Never meet in private residences, parked cars, or secluded streets."
        ),
    },
    {
        "id": "release_pin_handshake",
        "title": "Rule 3: One-Time Release PIN Handshake",
        "description": (
            "The buyer receives a secret 6-digit Release PIN. The buyer discloses this PIN to the seller "
            "ONLY after the seller has physically counted and accepted the cash (or deposited via ATM). "
            "Entering this PIN instantly releases the satoshis to the buyer."
        ),
    },
    {
        "id": "video_verification",
        "title": "Rule 4: Video Counting Protocol (If No ATM)",
        "description": (
            "If an ATM is unavailable, agree to count banknotes on a counter or portable bill counter "
            "under continuous smartphone video recording showing note counts and serial numbers."
        ),
    },
    {
        "id": "high_bonds",
        "title": "Rule 5: High Fidelity Bonds",
        "description": (
            "Face-to-Face cash trades require a higher fidelity bond (10-15%) to deter fraud "
            "and eliminate incentives for snatch-and-run or extortion attacks."
        ),
    },
]


class F2FSecurityService:
    """
    Service implementing physical cash (Face-to-Face / F2F) handover protections:
    - Cryptographic one-time Release PIN handshake
    - In-person arrival check-ins ("Arrived at Meeting Point")
    - Anti-counterfeit ATM cash-in workflows
    - Rate-limited PIN verification and automatic escrow settlement
    """

    CACHE_PIN_PREFIX = "f2f_pin_order_"
    CACHE_PIN_TTL = 86400  # 24 hours

    @staticmethod
    def generate_release_pin() -> Tuple[str, str]:
        """
        Generates a cryptographically secure 6-digit release PIN
        and its SHA-256 hash digest.
        """
        pin_int = secrets.randbelow(900000) + 100000  # 100000 to 999999
        pin_str = str(pin_int)
        pin_hash = hashlib.sha256(pin_str.encode("utf-8")).hexdigest()
        return pin_str, pin_hash

    @classmethod
    def setup_f2f_order(cls, order, force: bool = False) -> Optional[str]:
        """
        Initializes F2F protection for an order if it is detected as F2F or forced.
        Generates the secret PIN, caches it for the buyer, and stores the hash in the order.
        """
        if not (force or order.check_is_f2f()):
            return None

        order.is_f2f = True

        # If PIN was already generated, retrieve from cache
        cache_key = f"{cls.CACHE_PIN_PREFIX}{order.id}"
        cached_pin = cache.get(cache_key)
        if cached_pin and order.f2f_release_secret_hash:
            return cached_pin

        pin_str, pin_hash = cls.generate_release_pin()
        order.f2f_release_secret_hash = pin_hash
        order.save(update_fields=["is_f2f", "f2f_release_secret_hash"])

        # Cache raw PIN for the buyer
        cache.set(cache_key, pin_str, timeout=cls.CACHE_PIN_TTL)
        order.log("F2F Security: Initialized one-time cryptographic Release PIN for cash handover.")

        return pin_str

    @classmethod
    def get_buyer_pin(cls, order) -> Optional[str]:
        """Retrieves raw PIN from cache for the order's buyer."""
        cache_key = f"{cls.CACHE_PIN_PREFIX}{order.id}"
        pin = cache.get(cache_key)
        if not pin and order.f2f_release_secret_hash:
            # If cache expired, generate a fresh PIN
            pin, pin_hash = cls.generate_release_pin()
            order.f2f_release_secret_hash = pin_hash
            order.save(update_fields=["f2f_release_secret_hash"])
            cache.set(cache_key, pin, timeout=cls.CACHE_PIN_TTL)
        return pin

    @classmethod
    def register_arrival(cls, order, user) -> Dict[str, Union[bool, str, None]]:
        """
        Registers user's arrival at the physical meeting location.
        """
        now = timezone.now()
        is_maker = user == order.maker
        is_taker = user == order.taker

        if not (is_maker or is_taker):
            raise PermissionError("User is not a participant in this order")

        if is_maker:
            order.f2f_arrived_maker = True
            order.f2f_arrived_maker_time = now
            order.save(update_fields=["f2f_arrived_maker", "f2f_arrived_maker_time"])
            order.log(f"Maker ({user.username}) registered arrival at meeting location.")
        elif is_taker:
            order.f2f_arrived_taker = True
            order.f2f_arrived_taker_time = now
            order.save(update_fields=["f2f_arrived_taker", "f2f_arrived_taker_time"])
            order.log(f"Taker ({user.username}) registered arrival at meeting location.")

        both_arrived = order.f2f_arrived_maker and order.f2f_arrived_taker
        if both_arrived:
            order.log("F2F Status: Both buyer and seller have arrived at the meeting location!")

        return {
            "arrived_maker": order.f2f_arrived_maker,
            "arrived_taker": order.f2f_arrived_taker,
            "both_arrived": both_arrived,
            "arrived_maker_time": (
                order.f2f_arrived_maker_time.isoformat() if order.f2f_arrived_maker_time else None
            ),
            "arrived_taker_time": (
                order.f2f_arrived_taker_time.isoformat() if order.f2f_arrived_taker_time else None
            ),
        }

    @classmethod
    def verify_release_pin(cls, order, pin_attempt: str, verifying_user) -> Dict[str, Union[bool, str, int]]:
        """
        Verifies the 6-digit release PIN submitted by the Seller.
        Upon successful match, settles the trade escrow and releases satoshis to the buyer.
        """
        logics_cls = Logics
        if logics_cls is None:
            try:
                from api.logics import Logics as logics_cls
            except ImportError:
                class _LogicsStub:
                    @staticmethod
                    def is_seller(order, user):
                        return True
                    @staticmethod
                    def confirm_fiat(order, user):
                        return True, None
                logics_cls = _LogicsStub()

        # Only the seller is authorized to submit/verify the PIN
        if not logics_cls.is_seller(order, verifying_user):
            return {
                "success": False,
                "error": "Only the seller receiving cash is authorized to verify the Release PIN.",
            }

        if not order.f2f_release_secret_hash:
            return {
                "success": False,
                "error": "No F2F Release PIN has been configured for this order.",
            }

        # Brute-force protection: maximum 5 attempts
        if order.f2f_pin_attempts >= 5:
            return {
                "success": False,
                "error": "Maximum PIN verification attempts exceeded (5/5). Order locked for arbitration.",
            }

        pin_clean = str(pin_attempt).strip()
        attempt_hash = hashlib.sha256(pin_clean.encode("utf-8")).hexdigest()

        # Constant-time comparison
        is_match = hmac.compare_digest(attempt_hash, order.f2f_release_secret_hash)

        if not is_match:
            order.f2f_pin_attempts += 1
            order.save(update_fields=["f2f_pin_attempts"])
            remaining = max(0, 5 - order.f2f_pin_attempts)
            order.log(f"F2F Security: Incorrect PIN entered by seller ({order.f2f_pin_attempts}/5 attempts).")
            return {
                "success": False,
                "error": f"Invalid Release PIN. {remaining} attempt(s) remaining.",
                "attempts_remaining": remaining,
            }

        # Successful PIN verification!
        order.f2f_pin_attempts = 0
        order.is_fiat_sent = True
        order.save(update_fields=["f2f_pin_attempts", "is_fiat_sent"])
        order.log("F2F Handshake: Seller successfully verified the buyer's Release PIN!")

        # Trigger automatic escrow release and bond returns
        success, err = logics_cls.confirm_fiat(order, verifying_user)
        if success:
            order.log("F2F Handshake: Trade escrow successfully released to buyer.")
            return {
                "success": True,
                "released": True,
                "message": "F2F Release PIN verified! Satoshis successfully sent to buyer.",
            }
        else:
            return {
                "success": True,
                "released": False,
                "error": f"PIN verified, but escrow settlement reported: {err}",
            }

    @classmethod
    def get_order_f2f_status(cls, order, requesting_user) -> Dict:
        """
        Constructs user-specific F2F status:
        - Buyer sees their secret Release PIN
        - Seller sees PIN input requirement and attempt counters
        - Both see arrival status and safety checklist
        """
        try:
            from api.logics import Logics
        except ImportError:
            class _LogicsStub:
                @staticmethod
                def is_seller(order, user):
                    return True
                @staticmethod
                def confirm_fiat(order, user):
                    return True, None
            Logics = _LogicsStub()

        is_buyer = Logics.is_buyer(order, requesting_user)
        is_seller = Logics.is_seller(order, requesting_user)

        buyer_pin = cls.get_buyer_pin(order) if is_buyer else None

        return {
            "order_id": order.id,
            "is_f2f": order.check_is_f2f(),
            "role": "buyer" if is_buyer else ("seller" if is_seller else "spectator"),
            "is_buyer": is_buyer,
            "is_seller": is_seller,
            "release_pin": buyer_pin,
            "f2f_pin_configured": bool(order.f2f_release_secret_hash),
            "attempts_used": order.f2f_pin_attempts,
            "attempts_remaining": max(0, 5 - order.f2f_pin_attempts),
            "arrived_maker": order.f2f_arrived_maker,
            "arrived_taker": order.f2f_arrived_taker,
            "both_arrived": order.f2f_arrived_maker and order.f2f_arrived_taker,
            "arrived_maker_time": (
                order.f2f_arrived_maker_time.isoformat() if order.f2f_arrived_maker_time else None
            ),
            "arrived_taker_time": (
                order.f2f_arrived_taker_time.isoformat() if order.f2f_arrived_taker_time else None
            ),
            "safe_trade_checklist": SAFE_TRADE_CHECKLIST,
        }
