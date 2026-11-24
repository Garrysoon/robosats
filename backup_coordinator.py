#!/usr/bin/env python3
"""
RoboSats Coordinator - Automated Safe Backup System
===================================================
1. Выполняет консистентный (online backup) снимок базы данных SQLite
   без остановки сервера и без риска повреждения файла.
2. Архивирует критические файлы: .env, db.sqlite3, Tor hidden_service ключи.
3. Сохраняет архив в папку backups/ и (опционально) на внешнюю флешку/облако.
4. Выполняет автоматическую ротацию (удаляет архивы старше N дней).
"""

import os
import sys
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Количество дней хранения резервных копий
RETENTION_DAYS = 14


def perform_safe_sqlite_backup(source_db: Path, target_db: Path):
    """
    Создает атомарную горячую копию SQLite базы данных
    через официальный SQLite Online Backup API.
    Гарантирует 100% целостность данных даже при активных сделках.
    """
    if not source_db.exists():
        print(f"[!] Исходная база данных {source_db} не найдена, пропускаем.")
        return False

    print(f"[*] Создание горячего снимка базы данных SQLite: {source_db.name}...")
    src_conn = sqlite3.connect(str(source_db))
    dst_conn = sqlite3.connect(str(target_db))
    with dst_conn:
        src_conn.backup(dst_conn, pages=100)
    dst_conn.close()
    src_conn.close()
    print("[OK] Снимок базы данных успешно создан без блокировки сервера.")
    return True


def create_backup_archive(external_target: Path = None):
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"robosats_backup_{now_str}.zip"
    archive_path = BACKUP_DIR / archive_name

    temp_db_snapshot = BACKUP_DIR / f"temp_snapshot_{now_str}.sqlite3"

    print("=" * 65)
    print(f"  📦 RoboSats Coordinator Backup: {now_str}")
    print("=" * 65)

    files_to_pack = []

    # 1. Hot snapshot of SQLite DB
    main_db = BASE_DIR / "db.sqlite3"
    if main_db.exists():
        if perform_safe_sqlite_backup(main_db, temp_db_snapshot):
            files_to_pack.append((temp_db_snapshot, "db.sqlite3"))

    # 2. Critical Configuration (.env)
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        files_to_pack.append((env_file, ".env"))
        print(f"[+] Добавлен файл конфигурации и ключей шифрования: .env")

    # 3. Tor Hidden Service keys (if present)
    tor_keys_dirs = [
        BASE_DIR / "node" / "tor" / "data",
        BASE_DIR / "node" / "tor" / "data" / "hidden_service",
        BASE_DIR / "tor_keys",
    ]
    for kdir in tor_keys_dirs:
        if kdir.exists():
            for item in kdir.rglob("*"):
                if item.is_file() and ("secret_key" in item.name or "hostname" in item.name or "pub" in item.name):
                    rel = item.relative_to(BASE_DIR)
                    files_to_pack.append((item, str(rel)))
                    print(f"[+] Добавлен ключ Tor скрытого сервиса: {item.name}")

    # Create ZIP
    print(f"[*] Сжатие в архив: {archive_path.name}...")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path, arcname in files_to_pack:
            zipf.write(file_path, arcname)

    # Clean up temp snapshot
    if temp_db_snapshot.exists():
        temp_db_snapshot.unlink()

    size_kb = archive_path.stat().st_size / 1024
    print(f"[OK] Архив успешно создан! Размер: {size_kb:.1f} КБ")
    print(f"     Путь: {archive_path}")

    # Copy to external destination if specified (USB stick, cloud folder, etc.)
    if external_target and Path(external_target).exists():
        ext_dest = Path(external_target) / archive_name
        shutil.copyfile(archive_path, ext_dest)
        print(f"[OK] Копия успешно отправлена на внешнее хранилище: {ext_dest}")

    # 4. Retention & Rotation
    rotate_old_backups()

    print("=" * 65)
    print("✅ РЕЗЕРВНОЕ КОПИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО")
    print("=" * 65)
    return archive_path


def rotate_old_backups():
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    print(f"[*] Проверка ротации архивов старше {RETENTION_DAYS} дней...")
    deleted_count = 0
    for p in BACKUP_DIR.glob("robosats_backup_*.zip"):
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        if mtime < cutoff:
            p.unlink()
            deleted_count += 1
            print(f"[-] Удален устаревший архив: {p.name}")
    if deleted_count == 0:
        print("[OK] Устаревших архивов не обнаружено.")


if __name__ == "__main__":
    ext_path = sys.argv[1] if len(sys.argv) > 1 else None
    create_backup_archive(ext_path)
