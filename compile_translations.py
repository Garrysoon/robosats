#!/usr/bin/env python3
"""
Generates and compiles the Russian translation catalog for RoboSats.
Allows easily adding more languages (e.g. es, de, fr) by following the same catalog structure.
"""

import os
from pathlib import Path
import polib

BASE_DIR = Path(__file__).resolve().parent
LOCALE_DIR = BASE_DIR / "locale" / "ru" / "LC_MESSAGES"
LOCALE_DIR.mkdir(parents=True, exist_ok=True)

po_file_path = LOCALE_DIR / "django.po"
mo_file_path = LOCALE_DIR / "django.mo"

po = polib.POFile()
po.metadata = {
    'Project-Id-Version': 'RoboSats Coordinator 0.9.3',
    'Report-Msgid-Bugs-To': '',
    'POT-Creation-Date': '2026-11-23 00:00+0000',
    'PO-Revision-Date': '2026-11-23 00:00+0000',
    'Last-Translator': 'Antigravity <admin@robosats.local>',
    'Language-Team': 'Russian <ru@li.org>',
    'Language': 'ru',
    'MIME-Version': '1.0',
    'Content-Type': 'text/plain; charset=UTF-8',
    'Content-Transfer-Encoding': '8bit',
}

TRANSLATIONS = {
    "RoboSats Core API": "Основное API RoboSats",
    "RoboSats Core API administration": "Управление: Основное API RoboSats",
    "%(app_name)s administration": "Управление: %(app_name)s",
    "Основное API RoboSats administration": "Управление: Основное API RoboSats",
    "Order": "Сделка",
    "Orders": "Сделки",
    "order": "Сделка",
    "orders": "Сделки",
    "Robot": "Робот пользователя",
    "Robots": "Роботы пользователей",
    "robot": "Робот пользователя",
    "robots": "Роботы пользователей",
    "Currency": "Валюта",
    "Currencies": "Валюты",
    "currency": "Валюта",
    "currencies": "Валюты",
    "Cached market currency": "Валюта",
    "Lightning payment": "Платеж Lightning",
    "Lightning payments": "Платежи Lightning",
    "Onchain payment": "Ончейн платеж",
    "Onchain payments": "Ончейн платежи",
    "Market tick": "Котировка рынка",
    "Market ticks": "Котировки рынка",
    "Email Receipt Inbox": "Почтовый ящик банковских чеков",
    "Email Receipt Inboxes": "Почтовые ящики банковских чеков",
    "IMAP Host": "Хост IMAP",
    "IMAP Port": "Порт IMAP",
    "Username / Login": "Логин / Email",
    "Password / App Token": "Пароль / Токен приложения",
    "Use SSL/TLS": "Использовать SSL/TLS",
    "Mailbox Folder": "Папка ящика",
    "Public Receipt Email": "Публичный email для чеков",
    "Active": "Активен",
    "Inactive": "Неактивен",
    "Last Checked At": "Последняя проверка",
    "Last Status": "Последний статус",
    "Processed Receipts Count": "Обработано чеков",
    "Never checked": "Никогда не проверялся",
    "IMAP server hostname (e.g., imap.yandex.ru, imap.gmail.com, imap.mail.ru)": "Адрес сервера IMAP (например, imap.yandex.ru, imap.gmail.com, imap.mail.ru)",
    "IMAP server port (usually 993 for SSL)": "Порт сервера IMAP (обычно 993 для SSL)",
    "Email address / login used to authenticate with IMAP server": "Адрес почты или логин для подключения к IMAP-серверу",
    "IMAP App Password or secret key": "Пароль приложения IMAP или секретный ключ",
    "Connect using SSL/TLS encryption": "Подключаться с использованием шифрования SSL/TLS",
    "IMAP mailbox folder to inspect for unread bank receipts": "Папка почтового ящика для поиска непрочитанных банковских чеков",
    "Public email address shown to traders in order view (e.g., pay@coordinator.org)": "Публичный адрес почты, отображаемый трейдерам в сделке (например, pay@coordinator.org)",
    "Enable or disable automated polling for this mailbox": "Включить или отключить автоматический опрос этого ящика",
    "🔌 Test IMAP connection": "🔌 Проверить IMAP-подключение",
    "📥 Poll unread receipts now": "📥 Опросить непрочитанные чеки сейчас",
    "⚡ Apply recommended arbitration verdict (1-Click)": "⚡ Применить рекомендуемый вердикт арбитража (1 клик)",
    "Bank Receipt (DKIM/PDF)": "Банковский чек (DKIM/PDF)",
    "AI Verdict": "Вердикт ИИ/Правил",
    "F2F Cash": "Наличные F2F",
    "Close public order": "Закрыть публичный оффер",
    "Solve dispute: maker wins": "Разрешить спор: победа мейкера",
    "Solve dispute: taker wins": "Разрешить спор: победа тейкера",
    "Solve dispute: return everything": "Разрешить спор: возврат всех залогов",
    "Solve dispute: successful trade": "Разрешить спор: успешная сделка",
    "Compute median trade completion time": "Рассчитать медианное время завершения сделок",
    "Coordinator Node": "Нода координатора",
    "Coordinator Nodes": "Ноды координаторов",
    "Coordinator Check Log": "Лог проверки координатора",
    "Coordinator Check Logs": "Логи проверок координаторов",
    "Taproot Escrow Contract": "Taproot эскроу-контракт",
    "Taproot Escrow Contracts": "Taproot эскроу-контракты",
    "RoboSats Coordinator Administration": "Администрирование координатора RoboSats",
    "Coordinator administration": "Панель управления координатора",
    "RoboSats Coordinator Admin": "Админка координатора RoboSats",
    "24h Uptime": "Аптайм за 24ч",
    "Check health of selected coordinators now": "Проверить статус выбранных координаторов сейчас",
    "Sync coordinators from federation.json": "Синхронизировать координаторов из federation.json",
    "Waiting for maker bond": "Ожидание залога мейкера",
    "Public": "Опубликован",
    "Paused": "Приостановлен",
    "Waiting for taker bond": "Ожидание залога тейкера",
    "Cancelled": "Отменен",
    "Expired": "Истек",
    "Waiting for trade collateral and buyer invoice": "Ожидание обеспечения и инвойса покупателя",
    "Waiting only for seller trade collateral": "Ожидание только обеспечения продавца",
    "Waiting only for buyer invoice": "Ожидание только инвойса покупателя",
    "Sending fiat - In chatroom": "Отправка фиата — в чате",
    "Fiat sent - In chatroom": "Фиат отправлен — в чате",
    "In dispute": "В споре",
    "Collaboratively cancelled": "Отменен по согласию сторон",
    "Sending satoshis to buyer": "Отправка сатоши покупателю",
    "Successful trade": "Успешная сделка",
    "Failed lightning network routing": "Ошибка маршрутизации Lightning",
    "Wait for dispute resolution": "Ожидание вердикта по спору",
    "Maker lost dispute": "Мейкер проиграл спор",
    "Taker lost dispute": "Тейкер проиграл спор",
    "Status": "Статус",
    "Error": "Ошибка",
    "Created": "Создан",
    "Waiting for deposit": "Ожидание депозита",
    "Escrow funded": "Эскроу пополнен",
    "Released to buyer (cooperative)": "Выплачено покупателю (кооперативно)",
    "Arbitrated by coordinator": "Разрешено координатором",
    "Refunded to seller": "Возвращено продавцу",
    "Russian": "Русский",
    "English": "Английский",
    "Spanish": "Испанский",
    "German": "Немецкий",
    "French": "Французский",
}

for msgid, msgstr in TRANSLATIONS.items():
    entry = polib.POEntry(
        msgid=msgid,
        msgstr=msgstr,
    )
    po.append(entry)

po.save(str(po_file_path))
po.save_as_mofile(str(mo_file_path))

print(f"Generated {len(TRANSLATIONS)} Russian translations:")
print(f"PO: {po_file_path}")
print(f"MO: {mo_file_path}")
