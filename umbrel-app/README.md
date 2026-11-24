# ⚡ RoboSats Coordinator для Umbrel

Пакет для интеграции и запуска P2P-координатора RoboSats совместно с нодой **Umbrel Lightning Network (LND)**.

---

## Вариант 1: Запуск прямо на Umbrel (В 1 клик через Umbrel App Store)

1. Поместите директорию `umbrel-app` в репозиторий приложений Umbrel:
   ```bash
   cd ~/umbrel/app-stores/
   # или локально: ~/umbrel/apps/robosats-coordinator
   ```
2. Откройте Umbrel Web UI (`http://umbrel.local`).
3. Найдите **RoboSats Coordinator** в магазине приложений и нажмите **«Install»**.
4. Приложение автоматически подключится к системной ноде LND Umbrel, смонтирует `admin.macaroon` и `tls.cert`, и поднимет защищенную базу данных PostgreSQL.
5. Откройте панель управления `http://umbrel.local:8000/coordinator/`.

---

## Вариант 2: Запуск Координатора на ПК (Windows/Linux) с ликвидностью Umbrel

Если вы запускаете веб-панель RoboSats на Windows (например, по ярлыку на рабочем столе), вы можете использовать ликвидность своей ноды Umbrel:

1. На Umbrel ноде файлы авторизации LND находятся по путям:
   - Macaroon: `~/umbrel/app-data/lightning/data/lnd/data/chain/bitcoin/mainnet/admin.macaroon`
   - Сертификат: `~/umbrel/app-data/lightning/data/lnd/tls.cert`
2. Запустите скрипт быстрой связки:
   ```cmd
   python umbrel-app/connect_umbrel_lnd.py
   ```
3. Введите IP адрес вашего Umbrel (например `192.168.1.50` или `umbrel.local`).
4. Скрипт сохранит Base64-ключи в ваш `.env` файл.
5. Перезапустите координатор через ярлык на Рабочем столе — все залоги и молниеносные выплаты теперь идут через каналы вашей ноды!
