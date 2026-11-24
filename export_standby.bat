@echo off
chcp 65001 > nul
title Экспорт пакета горячего резерва RoboSats

cd /d "%~dp0"
python export_standby.py

echo.
pause
