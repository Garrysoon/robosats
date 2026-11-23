#!/usr/bin/env bash
set -e

echo "======================================================================"
echo "  🚀 Запуск контейнера RoboSats Coordinator (Self-Bootstrapping)"
echo "======================================================================"

# 1. Применение миграций базы данных
echo "[*] Автоматическое применение миграций..."
python3 manage.py migrate --noinput

# 2. Компиляция локализации
echo "[*] Компиляция русской локализации..."
python3 compile_translations.py || echo "[!] Пропуск компиляции переводов"

# 3. Автоматическое создание учетной записи администратора (если не существует)
echo "[*] Проверка учетной записи администратора..."
python3 - <<EOF
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "robosats.settings")
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get("ESCROW_USERNAME", "admin")
password = os.environ.get("ADMIN_PASSWORD", "admin12345")
email = os.environ.get("ADMIN_EMAIL", "admin@robosats.local")

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"[OK] Суперпользователь '{username}' успешно создан.")
else:
    print(f"[OK] Суперпользователь '{username}' уже существует.")
EOF

echo "======================================================================"
echo "  ✅ Командный центр готов: http://0.0.0.0:8000/coordinator/"
echo "======================================================================"

# Запуск переданной команды (или Daphne по умолчанию)
if [ $# -eq 0 ]; then
    exec daphne -b 0.0.0.0 -p 8000 robosats.asgi:application
else
    exec "$@"
fi
