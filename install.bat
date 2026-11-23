@echo off
chcp 65001 >nul
echo ======================================================================
echo   RoboSats Coordinator - Установщик Командного Центра (Windows)
echo ======================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден! Установите Python 3.10+ с сайта https://python.org и добавьте его в PATH.
    pause
    exit /b 1
)

echo [*] Проверка и установка зависимостей...
python -m pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Некоторые зависимости не удалось установить автоматически. Продолжаем установку...
)

echo [*] Запуск мастера первичной настройки...
python setup_coordinator.py %*

echo.
pause
