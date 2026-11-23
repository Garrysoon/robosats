import os
import sys
import json
import uuid
import django
from django.utils import timezone

os.environ["DJANGO_SETTINGS_MODULE"] = "robosats.settings_dev_lite"
django.setup()

from django.contrib.auth.models import User
from api.models import EmailInboxConfig, Currency, Order, Robot

# 1. Superuser
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@robosats.local", "admin12345")
    print("Superuser 'admin' created with password 'admin12345'.")
else:
    print("Superuser 'admin' already exists.")

# 2. EmailInboxConfig
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
    print("Demo EmailInboxConfig created.")

# 3. Currency
with open("frontend/static/assets/currencies.json") as f:
    currencies_data = json.load(f)

rub_id = None
for cid, code in currencies_data.items():
    if code == "RUB":
        rub_id = int(cid)
        break

if rub_id and not Currency.objects.filter(currency=rub_id).exists():
    curr = Currency.objects.create(currency=rub_id, exchange_rate=95.50)
    print("Currency RUB created.")
else:
    curr = Currency.objects.get(currency=rub_id)

# 4. Robots & Disputed Order
user1, _ = User.objects.get_or_create(username="alice_buyer")
user2, _ = User.objects.get_or_create(username="bob_seller")

robot1, _ = Robot.objects.get_or_create(user=user1, defaults={"hash_id": "alice123", "avatar": "Robo1"})
robot2, _ = Robot.objects.get_or_create(user=user2, defaults={"hash_id": "bob456", "avatar": "Robo2"})

if not Order.objects.exists():
    order = Order.objects.create(
        id=1,
        type=0,  # Buy
        status=Order.Status.DIS,
        is_disputed=True,
        is_fiat_sent=True,
        currency=curr,
        amount=15500.0,
        satoshis=185000,
        payment_method="Т-Банк (СБП)",
        maker=user1,
        taker=user2,
        expires_at=timezone.now() + timezone.timedelta(days=1),
        maker_statement="Здравствуйте! Я перевел ровно 15 500 рублей через СБП в Т-Банк. Чек из приложения: From: <noreply@tbank.ru>, Код: ROBO-1. Проверьте зачисление!",
        taker_statement="Я продавец. Денег не вижу, уведомление не пришло. Прошу вернуть залог продавцу.",
    )
    print(f"Created demo disputed order #{order.id}.")

print("Seeding complete.")
