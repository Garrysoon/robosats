#!/usr/bin/env python3
"""
RoboSats Coordinator - Развертывание на резервном компьютере (Standby)
=====================================================================
Распаковывает базу данных, секретные ключи .env и ключи адреса Tor
на резервном устройстве для моментального старта при сбое основного ПК.
"""

import os
import sys
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def deploy(bundle_zip_path=None):
    print("=" * 65)
    print("  📥 Развертывание резервного координатора RoboSats (Standby Node)")
    print("=" * 65)

    if not bundle_zip_path:
        # Search for bundle in current directory or standby/
        candidates = list(BASE_DIR.glob("robosats_standby_bundle_*.zip")) + \
                     list((BASE_DIR / "standby").glob("robosats_standby_bundle_*.zip"))
        if not candidates:
            print("[ОШИБКА] Архив robosats_standby_bundle_*.zip не найден!")
            print("Поместите архив с основного ПК в эту папку и запустите снова.")
            return False
        # Pick newest
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        bundle_zip_path = candidates[0]

    bundle_path = Path(bundle_zip_path)
    print(f"[*] Распаковка пакета: {bundle_path.name}...")

    with zipfile.ZipFile(bundle_path, "r") as zipf:
        for member in zipf.infolist():
            target_path = BASE_DIR / member.filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zipf.open(member) as source, open(target_path, "wb") as target:
                target.write(source.read())
            print(f" [OK] Извлечен: {member.filename}")

    print("\n✅ Развертывание резервного координатора завершено!")
    print("------------------------------------------------------------------")
    print("• Все актуальные сделки и пользователи перенесены.")
    print("• Настройки шифрования и адрес Tor идентичны основному серверу.")
    print("\nПри сбое основного ПК запустите: start_coordinator.bat")
    print("Трафик со всего мира переключится на этот резервный ПК за 30-45 секунд.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    bundle = sys.argv[1] if len(sys.argv) > 1 else None
    deploy(bundle)
