import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from embit import bip32, ec
from api.multisig.taproot_escrow import TaprootMultisigEscrow


class TaprootEscrowTestCase(unittest.TestCase):
    def setUp(self):
        self.escrow = TaprootMultisigEscrow(network="testnet")
        self.hd_maker = bip32.HDKey.from_seed(
            b"maker_test_seed_multisig_123456"[:32], version=bip32.NETWORKS["test"]["xprv"]
        )
        self.hd_taker = bip32.HDKey.from_seed(
            b"taker_test_seed_multisig_654321"[:32], version=bip32.NETWORKS["test"]["xprv"]
        )
        self.maker_xpub = self.hd_maker.to_public().to_base58()
        self.taker_xpub = self.hd_taker.to_public().to_base58()
        self.order_id = 555

    def test_taproot_escrow_address_derivation(self):
        info = self.escrow.create_order_escrow(
            order_id=self.order_id,
            maker_pubkey=self.maker_xpub,
            taker_pubkey=self.taker_xpub,
        )
        self.assertEqual(info["order_id"], self.order_id)
        self.assertTrue(info["address"].startswith("tb1p"))
        self.assertIn("multi_a(2,", info["descriptor"])
        self.assertIn(self.maker_xpub, info["descriptor"])
        self.assertIn(self.taker_xpub, info["descriptor"])

    def test_payout_psbt_creation(self):
        info = self.escrow.create_order_escrow(
            order_id=self.order_id,
            maker_pubkey=self.maker_xpub,
            taker_pubkey=self.taker_xpub,
        )
        psbt_b64 = self.escrow.create_payout_psbt(
            escrow_address=info["address"],
            funding_txid="77" * 32,
            funding_vout=1,
            funding_amount_sats=100_000,
            payout_address="tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
            mining_fee_sats=1800,
        )
        self.assertIsInstance(psbt_b64, str)
        self.assertTrue(len(psbt_b64) > 50)

    def test_cooperative_spend_maker_and_taker(self):
        info = self.escrow.create_order_escrow(
            order_id=self.order_id,
            maker_pubkey=self.maker_xpub,
            taker_pubkey=self.taker_xpub,
        )
        unsigned_psbt = self.escrow.create_payout_psbt(
            escrow_address=info["address"],
            funding_txid="88" * 32,
            funding_vout=0,
            funding_amount_sats=80_000,
            payout_address="tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
            mining_fee_sats=1500,
        )

        # Maker signs
        psbt_m = self.escrow.sign_psbt_with_key(
            unsigned_psbt, self.hd_maker, info["descriptor"], self.order_id
        )
        # Taker signs
        psbt_t = self.escrow.sign_psbt_with_key(
            unsigned_psbt, self.hd_taker, info["descriptor"], self.order_id
        )

        # Combine & finalize
        res = self.escrow.combine_and_finalize_psbt(
            [psbt_m, psbt_t], info["descriptor"], self.order_id
        )
        self.assertTrue(res["is_finalized"])
        self.assertIsNotNone(res["tx_hex"])
        self.assertIsNotNone(res["txid"])
        self.assertEqual(len(res["txid"]), 64)

    def test_single_signature_fails_finalization(self):
        info = self.escrow.create_order_escrow(
            order_id=self.order_id,
            maker_pubkey=self.maker_xpub,
            taker_pubkey=self.taker_xpub,
        )
        unsigned_psbt = self.escrow.create_payout_psbt(
            escrow_address=info["address"],
            funding_txid="88" * 32,
            funding_vout=0,
            funding_amount_sats=80_000,
            payout_address="tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
            mining_fee_sats=1500,
        )

        # Only Maker signs
        psbt_m = self.escrow.sign_psbt_with_key(
            unsigned_psbt, self.hd_maker, info["descriptor"], self.order_id
        )
        res = self.escrow.combine_and_finalize_psbt(
            [psbt_m], info["descriptor"], self.order_id
        )
        self.assertFalse(res["is_finalized"])
        self.assertIn("Insufficient signatures", res["error"])
        self.assertIsNone(res["tx_hex"])

    def test_dispute_resolution_coordinator_and_party(self):
        info = self.escrow.create_order_escrow(
            order_id=self.order_id,
            maker_pubkey=self.maker_xpub,
            taker_pubkey=self.taker_xpub,
        )
        unsigned_psbt = self.escrow.create_payout_psbt(
            escrow_address=info["address"],
            funding_txid="88" * 32,
            funding_vout=0,
            funding_amount_sats=80_000,
            payout_address="tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
            mining_fee_sats=1500,
        )

        # Coordinator signs (arbitration)
        psbt_coord = self.escrow.coordinator_sign_psbt(
            unsigned_psbt, info["descriptor"], self.order_id
        )
        # Taker signs (winner)
        psbt_taker = self.escrow.sign_psbt_with_key(
            unsigned_psbt, self.hd_taker, info["descriptor"], self.order_id
        )

        res = self.escrow.combine_and_finalize_psbt(
            [psbt_coord, psbt_taker], info["descriptor"], self.order_id
        )
        self.assertTrue(res["is_finalized"])
        self.assertIsNotNone(res["tx_hex"])
        self.assertIsNotNone(res["txid"])


if __name__ == "__main__":
    unittest.main()
