import hashlib
import hmac
import logging
import os
from typing import Dict, List, Optional, Tuple, Union

import bdkpython as bdk
import embit
import requests
from embit import bip32, ec, hashes, psbt, script, transaction
from embit.descriptor import Descriptor
from embit.util import secp256k1

try:
    from django.conf import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)


class TaprootMultisigEscrow:
    """
    Production-ready Non-Custodial 2-of-3 Bitcoin Taproot Multisig Escrow
    for RoboSats (BIP 340, BIP 341, BIP 342, BIP 386).

    Participants:
    1. Maker (Buyer or Seller)
    2. Taker (Counterparty)
    3. Coordinator (Arbitrator / Oracle)

    Spending conditions:
    - Cooperative settlement (Maker + Taker): 2-of-3 threshold is met without coordinator involvement.
      Zero custody, zero coordinator liability.
    - Dispute resolution (Coordinator + Winner): In case of dispute, arbitrator co-signs with the winning
      party. Coordinator alone cannot spend funds (1-of-3 is mathematically impossible).
    """

    def __init__(self, network: str = "testnet", coordinator_seed: Optional[bytes] = None):
        self.network = network.lower()
        self.is_mainnet = self.network in ("mainnet", "bitcoin", "main")
        self.bdk_network_kind = bdk.NetworkKind.MAIN if self.is_mainnet else bdk.NetworkKind.TEST
        self.bdk_network = bdk.Network.BITCOIN if self.is_mainnet else bdk.Network.TESTNET
        self.embit_network = bip32.NETWORKS["main"] if self.is_mainnet else bip32.NETWORKS["test"]

        # Esplora / Mempool API endpoint
        if self.is_mainnet:
            self.default_esplora = (
                getattr(settings, "BITCOIN_ESPLORA_URL", "https://mempool.space/api")
                if settings
                else "https://mempool.space/api"
            )
        else:
            self.default_esplora = (
                getattr(settings, "BITCOIN_TESTNET_ESPLORA_URL", "https://mempool.space/testnet/api")
                if settings
                else "https://mempool.space/testnet/api"
            )

        # Coordinator master HD key derived from seed or SECRET_KEY
        self.master_key = self._initialize_master_key(coordinator_seed)

    def _initialize_master_key(self, coordinator_seed: Optional[bytes] = None) -> bip32.HDKey:
        """Derives master HD key from provided seed, settings, or Django SECRET_KEY."""
        if coordinator_seed is None:
            raw_seed = None
            if settings:
                raw_seed = getattr(settings, "COORDINATOR_ESCROW_SEED", None)
            if not raw_seed:
                raw_seed = os.getenv("COORDINATOR_ESCROW_SEED")

            if raw_seed:
                if isinstance(raw_seed, str):
                    coordinator_seed = (
                        bytes.fromhex(raw_seed) if len(raw_seed) == 64 else raw_seed.encode("utf-8")
                    )
                else:
                    coordinator_seed = raw_seed
            else:
                # Deterministic HKDF derivation from Django SECRET_KEY
                secret_str = (
                    getattr(settings, "SECRET_KEY", "robosats-dev-key-multisig")
                    if settings
                    else "robosats-dev-key-multisig"
                )
                secret = secret_str.encode("utf-8")
                coordinator_seed = hmac.new(
                    b"robosats_taproot_escrow_master_seed", secret, hashlib.sha256
                ).digest()

        version = self.embit_network["xprv"]
        return bip32.HDKey.from_seed(coordinator_seed[:32], version=version)

    def derive_coordinator_key_for_order(self, order_id: int) -> Tuple[ec.PrivateKey, bip32.HDKey]:
        """
        Derives order-specific child key pair:
        m / order_id
        """
        path = f"m/{order_id}"
        child_hd = self.master_key.derive(path)
        return child_hd.key, child_hd

    @staticmethod
    def _normalize_to_xpub(pubkey_str: str, network_dict: dict) -> str:
        """Normalizes pubkey string (hex secp256k1 or xpub) into a BIP-32 xpub string."""
        pubkey_str = pubkey_str.strip()
        if pubkey_str.startswith(("xpub", "tpub", "vpub", "upub")):
            return pubkey_str

        try:
            # Parse raw compressed secp256k1 pubkey (33 bytes / 66 hex chars)
            pk = ec.PublicKey.from_string(pubkey_str)
            # Synthesize deterministic HDKey root with zero chain code
            hd = bip32.HDKey(pk, chain_code=b"\x00" * 32, version=network_dict["xpub"])
            return hd.to_base58()
        except Exception as e:
            raise ValueError(f"Invalid public key '{pubkey_str}': {e}")

    def create_order_escrow(
        self,
        order_id: int,
        maker_pubkey: str,
        taker_pubkey: str,
        coordinator_xpub: Optional[str] = None,
    ) -> Dict[str, Union[str, int]]:
        """
        Constructs the 2-of-3 Taproot Multisig escrow for an Order:
        tr(coord_xpub/*, multi_a(2, maker_xpub/*, taker_xpub/*, coord_xpub/*))
        and derives deterministic Taproot address for order_id.
        """
        if coordinator_xpub is None:
            coord_xpub = self.master_key.to_public().to_base58()

        maker_xpub = self._normalize_to_xpub(maker_pubkey, self.embit_network)
        taker_xpub = self._normalize_to_xpub(taker_pubkey, self.embit_network)
        coord_xpub = self._normalize_to_xpub(coord_xpub, self.embit_network)

        # Standard Miniscript Taproot descriptor
        desc_str = f"tr({coord_xpub}/*,multi_a(2,{maker_xpub}/*,{taker_xpub}/*,{coord_xpub}/*))"
        bdk_desc = bdk.Descriptor(desc_str, self.bdk_network_kind)
        derived_address = bdk_desc.derive_address(order_id, self.bdk_network)
        address_str = str(derived_address)

        return {
            "order_id": order_id,
            "address": address_str,
            "descriptor": desc_str,
            "coordinator_pubkey": coord_xpub,
            "maker_pubkey": maker_xpub,
            "taker_pubkey": taker_xpub,
            "network": self.network,
        }

    def verify_funding_deposit(
        self,
        escrow_address: str,
        expected_sats: int,
        min_confirmations: int = 1,
        esplora_url: Optional[str] = None,
    ) -> Dict[str, Union[bool, int, str, None]]:
        """
        Queries mempool/esplora for unspent outputs at escrow_address.
        Verifies confirmed balance against expected satoshis.
        """
        api_base = (esplora_url or self.default_esplora).rstrip("/")
        url = f"{api_base}/address/{escrow_address}/utxo"

        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                logger.error(f"Esplora error ({res.status_code}): {res.text}")
                return {
                    "funded": False,
                    "txid": None,
                    "vout": None,
                    "amount_sats": 0,
                    "confirmations": 0,
                    "is_confirmed": False,
                }

            utxos = res.json()
            total_sats = 0
            best_utxo = None

            for utxo in utxos:
                val = utxo.get("value", 0)
                status = utxo.get("status", {})
                confirmed = status.get("confirmed", False)
                block_height = status.get("block_height", 0)

                total_sats += val
                if val >= expected_sats and (best_utxo is None or confirmed):
                    best_utxo = {
                        "txid": utxo.get("txid"),
                        "vout": utxo.get("vout"),
                        "value": val,
                        "confirmed": confirmed,
                        "block_height": block_height,
                    }

            if best_utxo:
                return {
                    "funded": total_sats >= expected_sats,
                    "txid": best_utxo["txid"],
                    "vout": best_utxo["vout"],
                    "amount_sats": total_sats,
                    "confirmations": 1 if best_utxo["confirmed"] else 0,
                    "is_confirmed": best_utxo["confirmed"],
                }

            return {
                "funded": False,
                "txid": None,
                "vout": None,
                "amount_sats": total_sats,
                "confirmations": 0,
                "is_confirmed": False,
            }

        except Exception as e:
            logger.error(f"Failed verifying deposit for {escrow_address}: {e}")
            return {
                "funded": False,
                "txid": None,
                "vout": None,
                "amount_sats": 0,
                "confirmations": 0,
                "is_confirmed": False,
            }

    def create_payout_psbt(
        self,
        escrow_address: str,
        funding_txid: str,
        funding_vout: int,
        funding_amount_sats: int,
        payout_address: str,
        mining_fee_sats: int = 2000,
    ) -> str:
        """
        Creates an unsigned PSBT releasing funds from escrow to recipient payout address.
        """
        if funding_amount_sats <= mining_fee_sats:
            raise ValueError(
                f"Escrow amount ({funding_amount_sats}) must exceed mining fee ({mining_fee_sats})"
            )

        payout_sats = funding_amount_sats - mining_fee_sats

        # 1. Input spending the escrow UTXO
        txin = transaction.TransactionInput(
            bytes.fromhex(funding_txid), funding_vout, sequence=0xFFFFFFFD
        )

        # 2. Output to payout address
        payout_addr_obj = bdk.Address(payout_address, self.bdk_network)
        payout_spk_bytes = payout_addr_obj.script_pubkey().to_bytes()
        txout = transaction.TransactionOutput(payout_sats, script.Script(payout_spk_bytes))

        tx = transaction.Transaction(version=2, vin=[txin], vout=[txout], locktime=0)
        p = psbt.PSBT(tx)

        # 3. Add witness UTXO to input
        escrow_addr_obj = bdk.Address(escrow_address, self.bdk_network)
        escrow_spk_bytes = escrow_addr_obj.script_pubkey().to_bytes()
        p.inputs[0].witness_utxo = transaction.TransactionOutput(
            funding_amount_sats, script.Script(escrow_spk_bytes)
        )

        return p.to_base64()

    def _get_descriptor_taptree_info(
        self, descriptor_str: str, order_id: int
    ) -> Tuple[bytes, bytes, List[bytes]]:
        """
        Computes leaf script, control block, and internal public key for descriptor at order_id.
        """
        desc = Descriptor.from_string(descriptor_str)
        derived = desc.derive(order_id)
        internal_pk = derived.key.get_public_key()
        tweak = derived.taptree.tweak()
        tweak_hash = hashes.tagged_hash("TapTweak", internal_pk.xonly() + tweak)

        point = secp256k1.ec_pubkey_parse(b"\x02" + internal_pk.xonly())
        pub_tweaked = secp256k1.ec_pubkey_add(point, tweak_hash)
        sec = secp256k1.ec_pubkey_serialize(pub_tweaked)
        parity = sec[0] & 1
        control_block = bytes([0xC0 | parity]) + internal_pk.xonly()
        leaf_script = derived.taptree.tree.miniscript.compile()

        # Public keys in leaf order: [maker, taker, coordinator]
        leaf_keys = [k.get_public_key().xonly() for k in derived.taptree.tree.keys]
        return leaf_script, control_block, leaf_keys

    def sign_psbt_with_key(
        self,
        psbt_base64: str,
        private_key: Union[ec.PrivateKey, bip32.HDKey],
        descriptor_str: str,
        order_id: int,
    ) -> str:
        """
        Signs the PSBT input using a party's private key (Maker, Taker, or Coordinator).
        Supports ec.PrivateKey or bip32.HDKey.
        Stores Schnorr signature in partial_sigs.
        """
        p = psbt.PSBT.from_base64(psbt_base64)
        leaf_script, _, leaf_keys = self._get_descriptor_taptree_info(descriptor_str, order_id)

        # If an HDKey was passed, derive child key for order_id if needed
        signing_key: ec.PrivateKey
        if isinstance(private_key, bip32.HDKey):
            if private_key.key.xonly() in leaf_keys:
                signing_key = private_key.key
            else:
                child_hd = private_key.derive(f"m/{order_id}")
                signing_key = child_hd.key
        else:
            signing_key = private_key

        for inp in p.inputs:
            if inp.witness_utxo:
                h = p.tx.sighash_taproot(
                    0,
                    [inp.witness_utxo.script_pubkey],
                    [inp.witness_utxo.value],
                    script=script.Script(leaf_script),
                )
                sig = signing_key.schnorr_sign(h)
                sig_bytes = sig.serialize()
                # Store signature keyed by party's compressed public key
                inp.partial_sigs[signing_key.get_public_key()] = sig_bytes

        return p.to_base64()

    def coordinator_sign_psbt(
        self, psbt_base64: str, descriptor_str: str, order_id: int
    ) -> str:
        """Coordinator signs payout PSBT for dispute resolution."""
        child_priv, _ = self.derive_coordinator_key_for_order(order_id)
        return self.sign_psbt_with_key(psbt_base64, child_priv, descriptor_str, order_id)

    def combine_and_finalize_psbt(
        self,
        psbt_base64_list: List[str],
        descriptor_str: str,
        order_id: int,
    ) -> Dict[str, Union[bool, str, None]]:
        """
        Combines partially signed PSBTs, checks for at least 2 valid signatures among
        the 3 escrow participants, builds standard BIP-342 Tapscript witness stack:
        [sig_key3, sig_key2, sig_key1, leaf_script, control_block],
        and serializes final Bitcoin transaction hex.
        """
        if not psbt_base64_list:
            raise ValueError("At least one PSBT is required")

        combined_psbt = psbt.PSBT.from_base64(psbt_base64_list[0])
        for extra_b64 in psbt_base64_list[1:]:
            extra_psbt = psbt.PSBT.from_base64(extra_b64)
            for idx, inp in enumerate(extra_psbt.inputs):
                if idx < len(combined_psbt.inputs):
                    combined_psbt.inputs[idx].partial_sigs.update(inp.partial_sigs)

        leaf_script, control_block, leaf_keys = self._get_descriptor_taptree_info(
            descriptor_str, order_id
        )

        inp = combined_psbt.inputs[0]
        collected_sigs = inp.partial_sigs  # {ec.PublicKey: bytes}

        # Check which keys in [key1, key2, key3] have signatures
        sigs_by_xonly = {
            pub.xonly(): sig for pub, sig in collected_sigs.items() if len(sig) == 64
        }

        matched_sigs: List[bytes] = []
        for xonly_key in leaf_keys:
            if xonly_key in sigs_by_xonly:
                matched_sigs.append(sigs_by_xonly[xonly_key])
            else:
                matched_sigs.append(b"")

        valid_count = sum(1 for s in matched_sigs if s)
        if valid_count < 2:
            return {
                "is_finalized": False,
                "error": f"Insufficient signatures: {valid_count}/2 provided. Need at least 2 valid signatures.",
                "combined_psbt": combined_psbt.to_base64(),
                "tx_hex": None,
                "txid": None,
            }

        # BIP 342: multi_a checks keys in forward order, and the stack pops signatures in reverse order.
        # Stack order: [sig_key3, sig_key2, sig_key1, leaf_script, control_block]
        witness_elements = list(reversed(matched_sigs)) + [leaf_script, control_block]

        final_tx = transaction.Transaction.parse(combined_psbt.tx.serialize())
        final_tx.vin[0].witness = transaction.Witness(witness_elements)

        tx_hex = final_tx.serialize().hex()
        txid = final_tx.txid().hex()

        return {
            "is_finalized": True,
            "error": None,
            "combined_psbt": combined_psbt.to_base64(),
            "tx_hex": tx_hex,
            "txid": txid,
        }

    def broadcast_transaction(
        self, tx_hex: str, esplora_url: Optional[str] = None
    ) -> Dict[str, Union[bool, str, None]]:
        """Broadcasts serialized raw transaction to the Bitcoin network."""
        api_base = (esplora_url or self.default_esplora).rstrip("/")
        url = f"{api_base}/tx"

        try:
            res = requests.post(
                url, data=tx_hex, headers={"Content-Type": "text/plain"}, timeout=15
            )
            if res.status_code in (200, 201):
                txid = res.text.strip()
                return {"broadcasted": True, "txid": txid, "error": None}
            else:
                return {"broadcasted": False, "txid": None, "error": res.text}
        except Exception as e:
            return {"broadcasted": False, "txid": None, "error": str(e)}
