#!/usr/bin/env python3
"""
Comprehensive Test Runner for RoboSats Fork Security Suite:
- Encrypted Preimages (Fernet) & Anti-Triangle protections
- Automated Bank DKIM Receipt Verification
- Face-to-Face (F2F) Cash Protocol & Offline BIP-340 Schnorr Receipts
- Hybrid On-chain 2-of-3 Taproot Multisig Escrow
- Federation Coordinator Monitoring Service
- Dispute Automation & AI 1-Click Pre-flight Recommendation Engine
"""

import os
import sys
from unittest.mock import MagicMock

# Stub any missing grpc proto modules if running outside full Docker LND build
for mod in [
    "api.lightning.invoices_pb2", "api.lightning.invoices_pb2_grpc",
    "api.lightning.lightning_pb2", "api.lightning.lightning_pb2_grpc",
    "api.lightning.router_pb2", "api.lightning.router_pb2_grpc",
    "api.lightning.signer_pb2", "api.lightning.signer_pb2_grpc",
    "api.lightning.verrpc_pb2", "api.lightning.verrpc_pb2_grpc",
    "api.lightning.node_pb2", "api.lightning.node_pb2_grpc",
    "api.lightning.hold_pb2", "api.lightning.hold_pb2_grpc",
    "api.lightning.primitives_pb2", "api.lightning.primitives_pb2_grpc",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

os.environ.setdefault("FEE", "0.002")
os.environ.setdefault("MAX_TRADE", "5000000")
os.environ.setdefault("MIN_TRADE", "10000")
os.environ.setdefault("LND_CERT_BASE64", "ZHVtbXk=")
os.environ.setdefault("LND_MACAROON_BASE64", "ZHVtbXk=")
os.environ.setdefault("LND_GRPC_HOST", "127.0.0.1:10009")

import unittest

def main():
    test_modules = [
        "api.tests.test_preimage_encryption",
        "api.tests.test_dkim_verifier",
        "api.tests.test_f2f_security",
        "api.tests.test_taproot_escrow",
        "api.tests.test_coordinator_monitor",
        "api.tests.test_dispute_automation",
        "api.tests.test_email_ingestion",
    ]

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    for module_name in test_modules:
        mod_suite = loader.loadTestsFromName(module_name)
        suite.addTests(mod_suite)

    print("=" * 70)
    print("🚀 RUNNING ROBOSATS FORK COMPLETE SECURITY & INNOVATION TEST SUITE")
    print("=" * 70)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f"✅ ALL {result.testsRun} TESTS PASSED SUCCESSFULLY! ZERO FAILURES / ZERO ERRORS.")
        print("=" * 70)
        sys.exit(0)
    else:
        print(f"❌ TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors.")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
