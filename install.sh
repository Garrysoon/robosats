#!/usr/bin/env bash
set -e

echo "======================================================================"
echo "  RoboSats Coordinator - Установщик Командного Центра (Linux / macOS)"
echo "======================================================================"
echo ""

# Check python3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 не найден! Установите Python 3.10+ (sudo apt install python3 python3-pip python3-venv)."
    exit 1
fi

# Check virtual environment or install dependencies
if [ ! -d "venv" ]; then
    echo "[*] Создание изолированного виртуального окружения (venv)..."
    python3 -m venv venv || true
fi

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "[*] Проверка и установка зависимостей из requirements.txt..."
python3 -m pip install -q -r requirements.txt || echo "[WARNING] Пропуск pip install, продолжаем..."

echo "[*] Запуск интерактивного мастера настройки..."
python3 setup_coordinator.py "$@"
