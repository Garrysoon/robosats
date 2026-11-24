@echo off
chcp 65001 > nul
title Резервное копирование RoboSats Coordinator

cd /d "%~dp0"
python backup_coordinator.py %1

if "%~1"=="" (
    echo.
    echo Нажмите любую клавишу для закрытия...
    pause > nul
)
