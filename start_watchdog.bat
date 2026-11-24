@echo off
chcp 65001 > nul
title RoboSats Failover Watchdog - Авто-сторож горячей замены

echo ======================================================================
echo    🛡️  RoboSats Coordinator Failover Watchdog (Авто-сторож)
echo ======================================================================
echo.

cd /d "%~dp0"

set PRIMARY_HOST=127.0.0.1
set /p USER_INPUT="Введите IP-адрес или URL основного сервера [%PRIMARY_HOST%]: "
if not "%USER_INPUT%"=="" set PRIMARY_HOST=%USER_INPUT%

echo.
echo [*] Запуск мониторинга основного сервера: http://%PRIMARY_HOST%:8000
echo [*] Если основной сервер упадет - этот ПК автоматически возьмет управление на себя!
echo.

python failover_watchdog.py --primary "http://%PRIMARY_HOST%:8000" --interval 10 --fails 3

pause
