#!/usr/bin/env python3
"""
RoboSats P2P Coordinator - Automated Setup & Installation Wizard
=================================================================
Automates the full deployment and configuration of the RoboSats Coordinator
Command Center (Ops Cockpit) in 1 click / 1 command.
"""

import os
import sys
import argparse
import secrets
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ANSI Color codes for friendly CLI output
class Style:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

def print_banner():
    banner = f"""
{Style.CYAN}{Style.BOLD}======================================================================
  🤖 RoboSats Coordinator Ops Cockpit - 1-Click Setup Wizard
======================================================================{Style.RESET}
  Быстрая автоматическая инсталляция командного центра координатора
  Автоматический арбитраж | DKIM/PDF чеки | Taproot эскроу | F2F
----------------------------------------------------------------------
"""
    print(banner)


def check_python_version():
    if sys.version_info < (3, 10):
        print(f"{Style.RED}[ERROR] Требуется Python 3.10 или новее. Текущая версия: {sys.version}{Style.RESET}")
        sys.exit(1)
    print(f"{Style.GREEN}[OK] Python {sys.version.split()[0]} обнаружен.{Style.RESET}")


def generate_cryptographic_keys():
    django_secret = secrets.token_urlsafe(50)
    try:
        from cryptography.fernet import Fernet
        fernet_key = Fernet.generate_key().decode()
    except ImportError:
        # Fallback to standard base64 random 32 bytes
        fernet_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    return django_secret, fernet_key


def create_env_file(mode, alias, admin_user, port, force=False):
    env_path = BASE_DIR / ".env"
    if env_path.exists() and not force:
        print(f"{Style.YELLOW}[i] Файл .env уже существует. Сохраняем текущие настройки.{Style.RESET}")
        return

    secret_key, fernet_key = generate_cryptographic_keys()
    
    if mode == "lite":
        content = f"""# RoboSats Coordinator Environment Configuration (Lite / Evaluation Mode)
COORDINATOR_ALIAS="{alias}"
DEVELOPMENT=True
SECRET_KEY="{secret_key}"
FERNET_PREIMAGE_KEY="{fernet_key}"
ESCROW_USERNAME="{admin_user}"
LANGUAGE_CODE="ru"
NETWORK="testnet"
LNVENDOR="LND"
MIN_TRADE=20000
MAX_TRADE=5000000
FEE=0.002
DEFAULT_BOND_SIZE=3.0
FIAT_EXCHANGE_DURATION=24
USE_TOR=False
DJANGO_SETTINGS_MODULE="robosats.settings_dev_lite"
CSRF_TRUSTED_ORIGINS="http://127.0.0.1:{port},http://localhost:{port}"
"""
    else:
        content = f"""# RoboSats Coordinator Environment Configuration (Production Mode)
COORDINATOR_ALIAS="{alias}"
DEVELOPMENT=False
SECRET_KEY="{secret_key}"
FERNET_PREIMAGE_KEY="{fernet_key}"
ESCROW_USERNAME="{admin_user}"
LANGUAGE_CODE="ru"
NETWORK="mainnet"

# Database Configuration (PostgreSQL)
POSTGRES_DB="robosats"
POSTGRES_USER="robosats"
POSTGRES_PASSWORD="{secrets.token_urlsafe(16)}"
POSTGRES_HOST="127.0.0.1"
POSTGRES_PORT=5432

# Redis Cache & WebSockets
REDIS_URL="redis://127.0.0.1:6379/1"

# Lightning Node (LND)
LNVENDOR="LND"
LND_GRPC_HOST="127.0.0.1:10009"
LND_DIR="/lnd"
MACAROON_PATH="data/chain/bitcoin/mainnet/admin.macaroon"

# Tor Privacy
USE_TOR=True
TOR_PROXY="127.0.0.1:9050"

# Trading Limits & Fees
MIN_TRADE=20000
MAX_TRADE=5000000
FEE=0.002
DEFAULT_BOND_SIZE=3.0
FIAT_EXCHANGE_DURATION=24

CSRF_TRUSTED_ORIGINS="http://127.0.0.1:{port},http://localhost:{port}"
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{Style.GREEN}[OK] Конфигурационный файл .env успешно создан.{Style.RESET}")


def run_migrations(settings_module):
    print(f"{Style.CYAN}[*] Применение миграций базы данных ({settings_module})...{Style.RESET}")
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", interactive=False)
    print(f"{Style.GREEN}[OK] Все миграции успешно применены.{Style.RESET}")


def compile_localization():
    print(f"{Style.CYAN}[*] Компиляция каталога русской локализации...{Style.RESET}")
    compile_script = BASE_DIR / "compile_translations.py"
    if compile_script.exists():
        import subprocess
        result = subprocess.run([sys.executable, str(compile_script)], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{Style.GREEN}[OK] Локализация скомпилирована (django.mo).{Style.RESET}")
        else:
            print(f"{Style.YELLOW}[!] Предупреждение компиляции: {result.stderr.strip()}{Style.RESET}")
    else:
        print(f"{Style.YELLOW}[!] Скрипт compile_translations.py не найден, пропускаем.{Style.RESET}")


def create_or_update_superuser(username, password, email="admin@robosats.local"):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"{Style.GREEN}[OK] Суперпользователь '{username}' успешно создан.{Style.RESET}")
    else:
        u = User.objects.get(username=username)
        u.set_password(password)
        u.is_staff = True
        u.is_superuser = True
        u.save()
        print(f"{Style.GREEN}[OK] Пароль существующего администратора '{username}' обновлен.{Style.RESET}")


def seed_evaluation_data():
    print(f"{Style.CYAN}[*] Заполнение демонстрационными данными для оценки Cockpit...{Style.RESET}")
    try:
        import json
        import uuid
        from django.utils import timezone
        from django.contrib.auth.models import User
        from api.models import EmailInboxConfig, Currency, Order, Robot, TaprootEscrowContract

        # 1. IMAP Box
        if not EmailInboxConfig.objects.exists():
            EmailInboxConfig.objects.create(
                host="imap.yandex.ru",
                port=993,
                use_ssl=True,
                username="receipts@robosats-coordinator.ru",
                password="app-password-example",
                folder="INBOX",
                public_receipt_email="receipts@robosats-coordinator.ru",
                is_active=True,
            )

        # 2. Currency RUB
        curr_file = BASE_DIR / "frontend/static/assets/currencies.json"
        if curr_file.exists():
            with open(curr_file) as f:
                currencies_data = json.load(f)
            rub_id = None
            for cid, code in currencies_data.items():
                if code == "RUB":
                    rub_id = int(cid)
                    break
            if rub_id and not Currency.objects.filter(currency=rub_id).exists():
                Currency.objects.create(currency=rub_id, exchange_rate=95.50)

        # 3. Demo Users & Disputed Orders
        u1, _ = User.objects.get_or_create(username="alice_buyer")
        u2, _ = User.objects.get_or_create(username="bob_seller")
        r1, _ = Robot.objects.get_or_create(user=u1, defaults={"hash_id": "alice123", "avatar": "Robo1"})
        r2, _ = Robot.objects.get_or_create(user=u2, defaults={"hash_id": "bob456", "avatar": "Robo2"})

        rub_curr = Currency.objects.filter(currency=rub_id).first() if rub_id else None

        if not Order.objects.filter(is_disputed=True).exists() and rub_curr:
            Order.objects.create(
                amount=5000.0,
                satoshis=52000,
                fee_satoshis=104,
                currency=rub_curr,
                payment_method="T-Bank (SBP)",
                maker=r1,
                taker=r2,
                order_type=1,
                status=Order.Status.IN_DISPUTE,
                is_disputed=True,
                is_fiat_sent=True,
                expires_at=timezone.now() + timezone.timedelta(days=1),
                payment_reference="ROBO-TEST-SBP",
                auto_resolution_verdict="✅ РЕКОМЕНДАЦИЯ: Подтвердить сделку (DKIM банка валиден)",
                auto_resolution_confidence=0.98,
                offline_verified_by_dkim=True,
                buyer_receipt_verified=True,
            )

        # 4. Demo Taproot Escrow
        if not TaprootEscrowContract.objects.exists():
            demo_order = Order.objects.filter(is_disputed=True).first()
            if demo_order:
                TaprootEscrowContract.objects.create(
                    order=demo_order,
                    maker_pubkey="02" + "11" * 32,
                    taker_pubkey="03" + "22" * 32,
                    coordinator_pubkey="02" + "33" * 32,
                    address="tb1p8q3demo4escrow5address6taproot7robosats8coordinator9test",
                    descriptor="tr(c00rd,multi_a(2,maker,taker,coord))",
                    network="testnet",
                    required_sats=52000,
                    funded_sats=52000,
                    funding_confirmed=True,
                    status=TaprootEscrowContract.Status.FUNDED,
                )

        print(f"{Style.GREEN}[OK] Демонстрационные данные созданы (Споры, DKIM-чек, Taproot-эскроу).{Style.RESET}")
    except Exception as e:
        print(f"{Style.YELLOW}[!] Предупреждение при заполнении демо-данными: {e}{Style.RESET}")


def main():
    print_banner()
    check_python_version()

    parser = argparse.ArgumentParser(description="Автоматический мастер установки Координатора RoboSats")
    parser.add_argument("--mode", choices=["lite", "production"], default=None, help="Режим запуска (lite или production)")
    parser.add_argument("--alias", default=None, help="Псевдоним координатора")
    parser.add_argument("--admin-user", default="admin", help="Имя учетной записи суперпользователя")
    parser.add_argument("--admin-pass", default=None, help="Пароль суперпользователя")
    parser.add_argument("--port", type=int, default=8000, help="Порт веб-сервера")
    parser.add_argument("--seed", action="store_true", help="Заполнить демо-данными для тестирования арбитража")
    parser.add_argument("--quick", "-y", action="store_true", help="Быстрый запуск со всеми настройками по умолчанию")
    parser.add_argument("--start", action="store_true", help="Сразу запустить сервер после установки")

    args = parser.parse_args()

    # Mode selection
    if args.quick:
        mode = args.mode or "lite"
        alias = args.alias or "RoboSats Master Coordinator"
        admin_pass = args.admin_pass or "admin12345"
        seed_data = True
    else:
        # Interactive prompts
        if not args.mode:
            print(f"\n{Style.BOLD}Выберите режим развертывания:{Style.RESET}")
            print("  1) [Рекомендуется для оценки] Lite Standalone (SQLite, быстрый запуск без внешних нод)")
            print("  2) Production (PostgreSQL, Tor, LND, Celery)")
            choice = input("Ваш выбор [1/2] (по умолчанию 1): ").strip()
            mode = "production" if choice == "2" else "lite"
        else:
            mode = args.mode

        if not args.alias:
            alias = input(f"Псевдоним координатора (по умолчанию 'RoboSats Master Coordinator'): ").strip()
            if not alias:
                alias = "RoboSats Master Coordinator"
        else:
            alias = args.alias

        if not args.admin_pass:
            admin_pass = input("Пароль администратора (по умолчанию 'admin12345'): ").strip()
            if not admin_pass:
                admin_pass = "admin12345"
        else:
            admin_pass = args.admin_pass

        seed_data = args.seed or (mode == "lite")

    settings_module = "robosats.settings_dev_lite" if mode == "lite" else "robosats.settings"

    print(f"\n{Style.CYAN}{Style.BOLD}--- Запуск конфигурации ---{Style.RESET}")
    create_env_file(mode, alias, args.admin_user, args.port)
    run_migrations(settings_module)
    compile_localization()
    create_or_update_superuser(args.admin_user, admin_pass)

    if seed_data:
        seed_evaluation_data()

    print(f"""
{Style.GREEN}{Style.BOLD}======================================================================
  🎉 УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА! КОМАНДНЫЙ ЦЕНТР ГОТОВ К РАБОТЕ
======================================================================{Style.RESET}

  Панель управления (Ops Cockpit): {Style.BOLD}{Style.CYAN}http://127.0.0.1:{args.port}/coordinator/{Style.RESET}
  База знаний и документация:       {Style.BOLD}{Style.CYAN}http://127.0.0.1:{args.port}/coordinator/docs/{Style.RESET}
  Кабинет арбитража споров:        {Style.BOLD}{Style.CYAN}http://127.0.0.1:{args.port}/coordinator/api/order/{Style.RESET}

  Логин администратора:            {Style.BOLD}{args.admin_user}{Style.RESET}
  Пароль администратора:           {Style.BOLD}{admin_pass}{Style.RESET}

----------------------------------------------------------------------
Команда для запуска сервера:
  {Style.YELLOW}python manage.py runserver 127.0.0.1:{args.port} --settings={settings_module}{Style.RESET}
======================================================================
""")

    if args.start:
        print(f"{Style.CYAN}[*] Запуск сервера на порту {args.port}...{Style.RESET}")
        import subprocess
        subprocess.run([sys.executable, "manage.py", "runserver", f"127.0.0.1:{args.port}", f"--settings={settings_module}"])


if __name__ == "__main__":
    main()
