#!/usr/bin/env python3
"""
Comprehensive Test Runner for RoboSats Fork Security Suite:
- Encrypted Preimages (Fernet) & Anti-Triangle protections
- Automated Bank DKIM Receipt Verification
- Face-to-Face (F2F) Cash Protocol & Offline BIP-340 Schnorr Receipts
- Hybrid On-chain 2-of-3 Taproot Multisig Escrow
- Federation Coordinator Monitoring Service
"""

import sys
import unittest

def main():
    test_modules = [
        "api.tests.test_preimage_encryption",
        "api.tests.test_dkim_verifier",
        "api.tests.test_f2f_security",
        "api.tests.test_taproot_escrow",
        "api.tests.test_coordinator_monitor",
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
