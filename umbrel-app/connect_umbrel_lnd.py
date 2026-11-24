#!/usr/bin/env python3
"""
Инструмент быстрого подключения RoboSats Coordinator к ноде Umbrel (LND)
=======================================================================
Автоматически настраивает файл .env для работы координатора с Lightning-ликвидностью
вашей домашней ноды Umbrel.
"""

import os
import sys
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def prompt(text, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"{text}{suffix}: ").strip()
    return val if val else default

def main():
    print("=" * 65)
    print("  ⚡ RoboSats <-> Umbrel LND Node Connection Wizard")
    print("=" * 65)
    print("Этот мастер настроит подключение координатора к вашей ноде Umbrel.\n")

    print("Выберите способ подключения к Umbrel LND:")
    print("  1) Указать пути к файлам admin.macaroon и tls.cert с Umbrel")
    print("  2) Вставить Base64/Hex строки macaroon и сертификата")
    print("  3) Подключение к LND REST API ноды по IP")
    
    choice = prompt("Ваш выбор [1/2/3]", "1")

    umbrel_host = prompt("IP-адрес или хост Umbrel ноды (например, 192.168.1.50 или umbrel.local)", "umbrel.local")
    grpc_port = prompt("gRPC порт LND", "10009")
    network = prompt("Сеть Bitcoin (mainnet или testnet)", "mainnet")

    macaroon_b64 = ""
    cert_b64 = ""

    if choice == "1":
        macaroon_path = prompt("Путь к admin.macaroon (скопированному с Umbrel)")
        cert_path = prompt("Путь к tls.cert (скопированному с Umbrel)")

        if macaroon_path and os.path.exists(macaroon_path):
            with open(macaroon_path, "rb") as f:
                macaroon_b64 = base64.b64encode(f.read()).decode()
        else:
            print(f"[!] Файл macaroon не найден по пути {macaroon_path}")

        if cert_path and os.path.exists(cert_path):
            with open(cert_path, "rb") as f:
                cert_b64 = base64.b64encode(f.read()).decode()
        else:
            print(f"[!] Файл сертификата не найден по пути {cert_path}")

    elif choice == "2":
        raw_mac = prompt("Вставьте admin.macaroon (Base64 или HEX)")
        raw_cert = prompt("Вставьте tls.cert (Base64 или PEM)")
        
        # Check if HEX
        try:
            if all(c in "0123456789abcdefABCDEF" for c in raw_mac) and len(raw_mac) % 2 == 0:
                macaroon_b64 = base64.b64encode(bytes.fromhex(raw_mac)).decode()
            else:
                macaroon_b64 = raw_mac
        except Exception:
            macaroon_b64 = raw_mac

        cert_b64 = raw_cert

    env_path = BASE_DIR / ".env"
    print(f"\n[*] Обновление конфигурации в {env_path}...")

    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_to_update = {
        "LNVENDOR": "LND",
        "NETWORK": network,
        "LND_GRPC_HOST": f"{umbrel_host}:{grpc_port}",
    }
    if macaroon_b64:
        keys_to_update["LND_MACAROON_BASE64"] = macaroon_b64
    if cert_b64:
        keys_to_update["LND_CERT_BASE64"] = cert_b64

    updated_keys = set()
    new_lines = []
    for line in lines:
        matched = False
        for k, v in keys_to_update.items():
            if line.startswith(f"{k}=") or line.startswith(f"{k} ="):
                new_lines.append(f'{k}="{v}"\n')
                updated_keys.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in keys_to_update.items():
        if k not in updated_keys:
            new_lines.append(f'{k}="{v}"\n')

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("\n✅ Подключение успешно настроено в файле .env!")
    print(f"   LND Хост: {umbrel_host}:{grpc_port}")
    print(f"   Сеть:     {network}")
    print("   Теперь залоги и выплаты RoboSats будут обрабатываться вашей нодой Umbrel.")
    print("=" * 65)

if __name__ == "__main__":
    main()
