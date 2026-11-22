# Локализация и интернационализация (i18n) RoboSats

В RoboSats включена встроенная поддержка интернационализации (`USE_I18N = True`, `LocaleMiddleware`, `gettext_lazy as _`) с русским языком по умолчанию (`LANGUAGE_CODE = "ru"`).

---

## Архитектура локализации

1. **Настройки ([robosats/settings.py](file:///c:/Users/Garrysan/Documents/robosats/robosats/settings.py))**:
   - `LANGUAGE_CODE = config("LANGUAGE_CODE", default="ru")`
   - `LANGUAGES = [("ru", "Russian"), ("en", "English"), ("es", "Spanish"), ("de", "German"), ("fr", "French")]`
   - `MIDDLEWARE`: подключен `django.middleware.locale.LocaleMiddleware`.
   - `LOCALE_PATHS`: директория `locale/`.

2. **Каталоги переводов**:
   - `locale/<lang_code>/LC_MESSAGES/django.po` — исходный файл переводов в формате Gettext.
   - `locale/<lang_code>/LC_MESSAGES/django.mo` — скомпилированный бинарный каталог.

3. **Переключатель языков ([robosats/urls.py](file:///c:/Users/Garrysan/Documents/robosats/robosats/urls.py))**:
   - Роут `path("i18n/", include("django.conf.urls.i18n"))` позволяет переключать язык на лету через `POST /i18n/setlang/`.

---

## Как добавить новый язык (например, Испанский `es`)

### Шаг 1: Создать директорию локали
```bash
mkdir -p locale/es/LC_MESSAGES
```

### Шаг 2: Скопировать шаблон и перевести фразы
Скопируйте `locale/ru/LC_MESSAGES/django.po` в `locale/es/LC_MESSAGES/django.po` и укажите переводы:
```po
msgid "Email Receipt Inbox"
msgstr "Buzón de recibos bancarios"

msgid "IMAP Host"
msgstr "Servidor IMAP"
```

### Шаг 3: Скомпилировать бинарный каталог .mo
С помощью скрипта `compile_translations.py` или утилиты `polib`:
```bash
python compile_translations.py
```
или стандартной командой Django:
```bash
python manage.py compilemessages
```

### Шаг 4: Переключение языка
- Установить язык по умолчанию в `.env`:
  ```env
  LANGUAGE_CODE=es
  ```
- Либо переключить язык динамически через cookie `django_language=es`.
