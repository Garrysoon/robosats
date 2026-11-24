@echo off
chcp 65001 > nul
title Настройка автобэкапа RoboSats в Windows

echo ======================================================================
echo   ⚙️ Настройка автоматического резервного копирования RoboSats
echo ======================================================================
echo.

cd /d "%~dp0"
set SCRIPT_PATH=%~dp0backup_coordinator.py

echo Будет создано задание в Планировщике Windows:
echo - Расписание: Каждый день в 03:00 ночи и каждые 6 часов
echo - Скрипт: %SCRIPT_PATH%
echo - Сохранение: Папка backups/ (хранение 14 дней)
echo.

schtasks /create /tn "RoboSats_AutoBackup" /tr "python \"%SCRIPT_PATH%\"" /sc daily /st 03:00 /ri 360 /du 24:00 /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Автоматическое задание "RoboSats_AutoBackup" успешно зарегистрировано!
    echo Бэкапы будут создаваться каждые 6 часов автоматически в фоновом режиме.
) else (
    echo.
    echo [!] Не удалось создать системное задание через schtasks.
    echo Если требуется запуск от администратора, нажмите правой кнопкой мыши
    echo по этому файлу и выберите 'Запуск от имени администратора'.
)

echo.
pause
