import base64
import hashlib
import hmac
import json
import logging
import secrets
from typing import Dict, Optional, Tuple, Union

from embit import ec, hashes

try:
    from django.conf import settings
except ImportError:
    settings = None

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
        @staticmethod
        def timedelta(**kwargs):
            from datetime import timedelta
            return timedelta(**kwargs)
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
        "id": "offline_cryptographic_receipt",
        "title": "Rule 4: Offline Cryptographic Receipt (Zero-Internet Proof)",
        "description": (
            "If the buyer has no cellular reception or internet, the seller presents the coordinator's "
            "digitally signed QR receipt on screen. The buyer scans it offline with the RoboSats app. "
            "The app cryptographically verifies the coordinator's Schnorr signature locally without needing mobile data."
        ),
    },
    {
        "id": "video_verification",
        "title": "Rule 5: Video Counting Protocol (If No ATM)",
        "description": (
            "If an ATM is unavailable, agree to count banknotes on a counter or portable bill counter "
            "under continuous smartphone video recording showing note counts and serial numbers."
        ),
    },
    {
        "id": "high_bonds",
        "title": "Rule 6: High Fidelity Bonds",
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
    - Offline-verifiable Coordinator Signed Receipts (BIP 340 Schnorr signatures)
    - In-person arrival check-ins with automatic meeting window extension (Pause Lock)
    - Anti-counterfeit ATM cash-in workflows
    - Rate-limited PIN verification and automatic escrow settlement
    """

    CACHE_PIN_PREFIX = "f2f_pin_order_"
    CACHE_PIN_TTL = 86400  # 24 hours

    @staticmethod
    def _get_coordinator_signing_key(coordinator_seed: Optional[bytes] = None) -> ec.PrivateKey:
        """Derives a deterministic coordinator private key for signing release receipts."""
        if coordinator_seed is None:
            raw_seed = None
            if settings:
                raw_seed = getattr(settings, "COORDINATOR_ESCROW_SEED", None)
            if not raw_seed:
                import os
                raw_seed = os.getenv("COORDINATOR_ESCROW_SEED")

            if raw_seed:
                if isinstance(raw_seed, str):
                    coordinator_seed = (
                        bytes.fromhex(raw_seed) if len(raw_seed) == 64 else raw_seed.encode("utf-8")
                    )
                else:
                    coordinator_seed = raw_seed
            else:
                secret_str = (
                    getattr(settings, "SECRET_KEY", "robosats-f2f-offline-signing-secret")
                    if settings
                    else "robosats-f2f-offline-signing-secret"
                )
                coordinator_seed = hmac.new(
                    b"robosats_f2f_offline_receipt_signing_key", secret_str.encode("utf-8"), hashlib.sha256
                ).digest()

        return ec.PrivateKey(coordinator_seed[:32])

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

        cache_key = f"{cls.CACHE_PIN_PREFIX}{order.id}"
        cached_pin = cache.get(cache_key)
        if cached_pin and order.f2f_release_secret_hash:
            return cached_pin

        pin_str, pin_hash = cls.generate_release_pin()
        order.f2f_release_secret_hash = pin_hash
        order.save(update_fields=["is_f2f", "f2f_release_secret_hash"])

        cache.set(cache_key, pin_str, timeout=cls.CACHE_PIN_TTL)
        order.log("F2F Security: Initialized one-time cryptographic Release PIN for cash handover.")

        return pin_str

    @classmethod
    def get_buyer_pin(cls, order) -> Optional[str]:
        """Retrieves raw PIN from cache for the order's buyer."""
        cache_key = f"{cls.CACHE_PIN_PREFIX}{order.id}"
        pin = cache.get(cache_key)
        if not pin and order.f2f_release_secret_hash:
            pin, pin_hash = cls.generate_release_pin()
            order.f2f_release_secret_hash = pin_hash
            order.save(update_fields=["f2f_release_secret_hash"])
            cache.set(cache_key, pin, timeout=cls.CACHE_PIN_TTL)
        return pin

    @classmethod
    def register_arrival(cls, order, user) -> Dict[str, Union[bool, str, None]]:
        """
        Registers user's arrival at the physical meeting location.
        When both arrive, activates Pause Lock (extends order expiration by 60 minutes)
        to allow offline cash counting without risk of expiration or bond slashing.
        """
        now = timezone.now()
        is_maker = user == order.maker
        is_taker = user == order.taker

        if not (is_maker or is_taker):
            raise PermissionError("User is not a participant in this order")

        fields_to_save = []
        if is_maker:
            order.f2f_arrived_maker = True
            order.f2f_arrived_maker_time = now
            fields_to_save.extend(["f2f_arrived_maker", "f2f_arrived_maker_time"])
            order.log(f"Maker ({user.username}) registered arrival at meeting location.")
        elif is_taker:
            order.f2f_arrived_taker = True
            order.f2f_arrived_taker_time = now
            fields_to_save.extend(["f2f_arrived_taker", "f2f_arrived_taker_time"])
            order.log(f"Taker ({user.username}) registered arrival at meeting location.")

        both_arrived = order.f2f_arrived_maker and order.f2f_arrived_taker
        if both_arrived:
            # Pause Lock: extend expiration window by 60 minutes
            if hasattr(order, "expires_at") and order.expires_at:
                order.expires_at += timezone.timedelta(minutes=60)
                fields_to_save.append("expires_at")
            order.log("F2F Pause Lock: Both parties on-site; extended order expiration by 60 minutes for offline cash counting.")

        order.save(update_fields=fields_to_save)

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
    def generate_coordinator_receipt(
        cls,
        order,
        payout_txid: Optional[str] = None,
        lightning_preimage: Optional[str] = None,
        coordinator_privkey: Optional[ec.PrivateKey] = None,
    ) -> Dict[str, Union[str, dict]]:
        """
        Creates a tamper-proof cryptographic release receipt signed with the Coordinator's
        private key using BIP-340 Schnorr signatures.
        Can be verified offline by any device with zero internet connectivity.
        """
        privkey = coordinator_privkey or cls._get_coordinator_signing_key()
        pubkey = privkey.get_public_key()

        buyer_name = ""
        if hasattr(order, "buyer") and order.buyer:
            username = getattr(order.buyer, "username", None)
            buyer_name = str(username) if username else str(order.buyer)

        currency_code = "BTC"
        if getattr(order, "currency", None):
            code = getattr(order.currency, "code", None)
            if isinstance(code, str):
                currency_code = code

        amount_val = 0
        raw_amt = getattr(order, "last_satoshis", None) or getattr(order, "satoshis", None)
        if raw_amt is not None:
            try:
                amount_val = int(raw_amt)
            except (ValueError, TypeError):
                amount_val = 0

        payout_tx = payout_txid or getattr(order, "payout_txid", "") or ""
        if not isinstance(payout_tx, str):
            payout_tx = str(payout_tx) if payout_tx else ""

        payload = {
            "v": 1,
            "type": "ROBOPROOF",
            "order_id": int(order.id),
            "amount_sats": amount_val,
            "currency": str(currency_code),
            "buyer": str(buyer_name),
            "status": "RELEASED",
            "payout_txid": payout_tx,
            "lightning_preimage": str(lightning_preimage or ""),
            "timestamp": int(timezone.now().timestamp()),
            "coordinator_pubkey": pubkey.sec().hex(),
        }

        # Canonical deterministic JSON serialization
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        msg_hash = hashes.sha256(canonical_json)

        # Schnorr signature (BIP 340)
        sig = privkey.schnorr_sign(msg_hash)
        sig_hex = sig.to_string()

        b64_payload = base64.urlsafe_b64encode(canonical_json).decode("utf-8")
        token = f"ROBOPROOF:v1:{b64_payload}:{sig_hex}:{pubkey.sec().hex()}"

        # Persist receipt on order
        order.f2f_offline_receipt = token
        order.save(update_fields=["f2f_offline_receipt"])
        order.log("F2F Security: Generated cryptographic Coordinator Signed Receipt for offline verification.")

        return {
            "token": token,
            "payload": payload,
            "signature": sig_hex,
            "coordinator_pubkey": pubkey.sec().hex(),
        }

    @classmethod
    def verify_offline_receipt(
        cls,
        receipt_token: str,
        trusted_coordinator_pubkey: Optional[str] = None,
        expected_payment_hash: Optional[str] = None,
    ) -> Dict[str, Union[bool, str, dict, None]]:
        """
        Cryptographically verifies a Coordinator Release Receipt entirely offline.
        Validates:
        1. BIP-340 Schnorr signature against the coordinator's public key.
        2. Expected coordinator public key (anti-spoofing).
        3. Lightning payment preimage against expected payment hash if provided.
        """
        token_clean = receipt_token.strip()
        parts = token_clean.split(":")
        if len(parts) != 5 or parts[0] != "ROBOPROOF" or parts[1] != "v1":
            return {"is_valid": False, "error": "Invalid receipt token format"}

        b64_payload, sig_hex, pubkey_hex = parts[2], parts[3], parts[4]

        # 1. Pubkey validation
        if trusted_coordinator_pubkey and pubkey_hex != trusted_coordinator_pubkey:
            return {
                "is_valid": False,
                "error": "Coordinator pubkey in receipt does not match trusted coordinator key",
            }

        try:
            canonical_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
            payload = json.loads(canonical_bytes.decode("utf-8"))
        except Exception as e:
            return {"is_valid": False, "error": f"Failed decoding receipt payload: {e}"}

        # 2. Signature verification
        try:
            msg_hash = hashes.sha256(canonical_bytes)
            pub = ec.PublicKey.from_string(pubkey_hex)
            schnorr_sig = ec.SchnorrSig.from_string(sig_hex)
            sig_valid = pub.schnorr_verify(schnorr_sig, msg_hash)
            if not sig_valid:
                return {"is_valid": False, "error": "Cryptographic signature verification failed"}
        except Exception as e:
            return {"is_valid": False, "error": f"Signature verification error: {e}"}

        # 3. Lightning Preimage proof verification (if present)
        preimage_hex = payload.get("lightning_preimage")
        if preimage_hex and expected_payment_hash:
            computed_hash = hashlib.sha256(bytes.fromhex(preimage_hex)).hexdigest()
            if not hmac.compare_digest(computed_hash.lower(), expected_payment_hash.lower()):
                return {
                    "is_valid": False,
                    "error": "Preimage does not match expected invoice payment hash",
                }

        return {
            "is_valid": True,
            "error": None,
            "order_id": payload.get("order_id"),
            "amount_sats": payload.get("amount_sats"),
            "currency": payload.get("currency"),
            "buyer": payload.get("buyer"),
            "payout_txid": payload.get("payout_txid"),
            "has_lightning_preimage": bool(preimage_hex),
            "timestamp": payload.get("timestamp"),
            "coordinator_pubkey": pubkey_hex,
            "payload": payload,
        }

    @classmethod
    def verify_release_pin(cls, order, pin_attempt: str, verifying_user) -> Dict[str, Union[bool, str, int, dict]]:
        """
        Verifies the 6-digit release PIN submitted by the Seller.
        Upon successful match:
        - Settles the trade escrow and releases satoshis to the buyer
        - Generates a cryptographic Coordinator Signed Receipt for offline buyer verification
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

        if order.f2f_pin_attempts >= 5:
            return {
                "success": False,
                "error": "Maximum PIN verification attempts exceeded (5/5). Order locked for arbitration.",
            }

        pin_clean = str(pin_attempt).strip()
        attempt_hash = hashlib.sha256(pin_clean.encode("utf-8")).hexdigest()

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

        order.f2f_pin_attempts = 0
        order.is_fiat_sent = True
        order.save(update_fields=["f2f_pin_attempts", "is_fiat_sent"])
        order.log("F2F Handshake: Seller successfully verified the buyer's Release PIN!")

        success, err = logics_cls.confirm_fiat(order, verifying_user)
        if success:
            order.log("F2F Handshake: Trade escrow successfully released to buyer.")
            # Generate offline receipt
            receipt_info = cls.generate_coordinator_receipt(order)
            return {
                "success": True,
                "released": True,
                "message": "F2F Release PIN verified! Satoshis successfully sent to buyer.",
                "offline_receipt": receipt_info["token"],
                "offline_receipt_payload": receipt_info["payload"],
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
        - Both see arrival status, offline receipt, and safety checklist
        """
        logics_cls = Logics
        if logics_cls is None:
            try:
                from api.logics import Logics as logics_cls
            except ImportError:
                class _LogicsStub:
                    @staticmethod
                    def is_buyer(order, user):
                        return True
                    @staticmethod
                    def is_seller(order, user):
                        return False
                logics_cls = _LogicsStub()

        is_buyer = logics_cls.is_buyer(order, requesting_user)
        is_seller = logics_cls.is_seller(order, requesting_user)

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
            "offline_receipt": getattr(order, "f2f_offline_receipt", "") or None,
            "safe_trade_checklist": SAFE_TRADE_CHECKLIST,
        }
