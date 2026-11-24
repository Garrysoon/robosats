#!/usr/bin/env python3
"""
RoboSats Coordinator - Экспорт пакета горячего резерва (Вариант А)
================================================================
Формирует автономный переносимый архив для мгновенного развертывания
координатора на резервном ноутбуке, втором ПК или Umbrel.
"""

import os
import sys
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STANDBY_DIR = BASE_DIR / "standby"
STANDBY_DIR.mkdir(parents=True, exist_ok=True)


def export_bundle():
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_name = f"robosats_standby_bundle_{now_str}.zip"
    bundle_path = STANDBY_DIR / bundle_name
    latest_bundle = STANDBY_DIR / "robosats_standby_bundle_latest.zip"

    temp_db = STANDBY_DIR / f"temp_db_{now_str}.sqlite3"

    print("=" * 65)
    print("  🚀 Экспорт пакета горячего резерва RoboSats (Active -> Standby)")
    print("=" * 65)

    files_to_pack = []

    # 1. Hot snapshot of SQLite DB
    main_db = BASE_DIR / "db.sqlite3"
    if main_db.exists():
        print(f"[*] Создание горячего снимка базы данных {main_db.name}...")
        src = sqlite3.connect(str(main_db))
        dst = sqlite3.connect(str(temp_db))
        with dst:
            src.backup(dst, pages=100)
        dst.close()
        src.close()
        files_to_pack.append((temp_db, "db.sqlite3"))
        print("[OK] База данных сохранена без блокировки активных сделок.")

    # 2. Environment config
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        files_to_pack.append((env_file, ".env"))
        print("[+] Добавлен конфигурационный файл и ключи шифрования (.env)")

    # 3. Tor keys
    tor_dirs = [
        BASE_DIR / "node" / "tor" / "data",
        BASE_DIR / "node" / "tor" / "data" / "hidden_service",
        BASE_DIR / "tor_keys",
    ]
    for tdir in tor_dirs:
        if tdir.exists():
            for item in tdir.rglob("*"):
                if item.is_file() and ("secret" in item.name or "hostname" in item.name or "pub" in item.name):
                    rel = item.relative_to(BASE_DIR)
                    files_to_pack.append((item, str(rel)))
                    print(f"[+] Добавлен ключ адреса Tor: {item.name}")

    # 4. Deployment scripts
    deploy_script = BASE_DIR / "deploy_standby.py"
    if deploy_script.exists():
        files_to_pack.append((deploy_script, "deploy_standby.py"))

    deploy_bat = BASE_DIR / "deploy_standby.bat"
    if deploy_bat.exists():
        files_to_pack.append((deploy_bat, "deploy_standby.bat"))

    # Write zip
    print(f"[*] Сжатие пакета резерва в {bundle_path.name}...")
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fpath, arcname in files_to_pack:
            zipf.write(fpath, arcname)

    # Copy to latest
    import shutil
    shutil.copyfile(bundle_path, latest_bundle)

    if temp_db.exists():
        temp_db.unlink()

    size_kb = bundle_path.stat().st_size / 1024
    print("=" * 65)
    print(f"✅ ПАКЕТ ГОРЯЧЕГО РЕЗЕРВА УСПЕШНО СОЗДАН ({size_kb:.1f} КБ)")
    print(f"   Файл: {bundle_path}")
    print(f"   Ссылка для синхронизации: {latest_bundle}")
    print("\nИнструкция для резервного ПК:")
    print("1. Скопируйте этот zip-архив на резервный ноутбук или ПК.")
    print("2. Запустите в нем 'deploy_standby.bat'.")
    print("3. В случае сбоя основного ПК кликните 'Старт Резервного Координатора'!")
    print("=" * 65)


if __name__ == "__main__":
    export_bundle()
