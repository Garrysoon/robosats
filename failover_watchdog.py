#!/usr/bin/env python3
"""
RoboSats Coordinator - Автоматический сторож горячей замены (Вариант Б)
=====================================================================
Работает в фоновом режиме на резервном компьютере/сервере.
Постоянно проверяет жизнеспособность основного координатора.
При падении основного сервера автоматически активирует резервный координатор
без необходимости ручного вмешательства человека.
"""

import os
import sys
import time
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:
    import requests
except ImportError:
    print("[!] Библиотека 'requests' не установлена. Устанавливаем...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "💓", "WARN": "⚠️", "ALERT": "🚨", "OK": "✅"}
    print(f"[{ts}] {icons.get(level, '•')} {msg}", flush=True)


def activate_standby(port, settings_module):
    print("\n" + "=" * 70)
    log("КРИТИЧЕСКИЙ СБОЙ ОСНОВНОГО СЕРВЕРА!", level="ALERT")
    log("АВТОМАТИЧЕСКАЯ АКТИВАЦИЯ РЕЗЕРВНОГО КООРДИНАТОРА ROBOSATS...", level="ALERT")
    print("=" * 70 + "\n")

    cmd = [
        sys.executable,
        "manage.py",
        "runserver",
        f"0.0.0.0:{port}",
        f"--settings={settings_module}",
    ]

    log(f"Запуск резервного сервера на порту {port}...", level="INFO")
    
    # Open browser on local machine
    try:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}/coordinator/")
    except Exception:
        pass

    # Run the server
    subprocess.run(cmd, cwd=str(BASE_DIR))


def run_watchdog(primary_url, interval, max_fails, port, settings_module):
    if not primary_url.startswith("http://") and not primary_url.startswith("https://"):
        primary_url = f"http://{primary_url}"

    health_url = f"{primary_url.rstrip('/')}/api/v1/health/"

    print("=" * 70)
    print("  🛡️  RoboSats Coordinator Failover Watchdog (Авто-сторож)")
    print("=" * 70)
    print(f"  Основной сервер:      {primary_url}")
    print(f"  Проверка health:      {health_url}")
    print(f"  Интервал опроса:      {interval} сек")
    print(f"  Порог срабатывания:   {max_fails} последовательных ошибок")
    print(f"  Режим резерва:        Ожидание (Standby - CPU ~0%)")
    print("=" * 70 + "\n")

    fail_count = 0

    while True:
        try:
            resp = requests.get(health_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if fail_count > 0:
                    log(f"Связь с основным сервером восстановлена! Статус: {data.get('status')}", level="OK")
                    fail_count = 0
                else:
                    log(f"Основной сервер активен: {data.get('alias')} (v{data.get('version')}) | Резерв: ОЖИДАНИЕ", level="INFO")
            else:
                fail_count += 1
                log(f"Основной сервер вернул код {resp.status_code} ({fail_count}/{max_fails})", level="WARN")
        except Exception as e:
            fail_count += 1
            log(f"Основной сервер не отвечает ({fail_count}/{max_fails}): {e}", level="WARN")

        if fail_count >= max_fails:
            activate_standby(port, settings_module)
            break

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Авто-сторож горячей замены RoboSats (Failover Watchdog)")
    parser.add_argument("--primary", default="http://127.0.0.1:8000", help="URL или IP адрес основного сервера (например, http://192.168.1.50:8000)")
    parser.add_argument("--interval", type=int, default=15, help="Интервал проверки в секундах (по умолчанию 15)")
    parser.add_argument("--fails", type=int, default=3, help="Количество ошибок до активации резерва (по умолчанию 3)")
    parser.add_argument("--port", type=int, default=8000, help="Порт для резервного сервера (по умолчанию 8000)")
    parser.add_argument("--settings", default="robosats.settings_dev_lite", help="Модуль настроек Django")

    args = parser.parse_args()
    run_watchdog(args.primary, args.interval, args.fails, args.port, args.settings)


if __name__ == "__main__":
    main()
