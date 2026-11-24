@echo off
chcp 65001 > nul
title RoboSats Ops Cockpit - Командный Центр Координатора

echo ======================================================================
echo    🤖 RoboSats Coordinator Ops Cockpit - Запуск Командного Центра
echo ======================================================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден в переменной PATH!
    echo Установите Python 3.10+ с галочкой 'Add Python to PATH'.
    pause
    exit /b 1
)

echo [*] Проверка окружения и базы данных...
python -c "import django; print('Django version:', django.__version__)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Устанавливаем необходимые зависимости...
    pip install -r requirements.txt
    pip install reportlab
)

echo [*] Проверка готовности сервера...
echo.
echo ======================================================================
echo   Командный центр доступен по адресу:
echo   --> http://127.0.0.1:8000/coordinator/
echo.
echo   Логин по умолчанию:  admin
echo   Пароль:              admin12345
echo.
echo   Нажмите Ctrl+C в этом окне, если потребуется остановить сервер.
echo ======================================================================
echo.

:: Автоматически открываем браузер через 2 секунды
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000/coordinator/"

:: Запускаем сервер RoboSats в режиме Lite (или Production при наличии PostgreSQL/LND)
python manage.py runserver 127.0.0.1:8000 --settings=robosats.settings_dev_lite

pause
