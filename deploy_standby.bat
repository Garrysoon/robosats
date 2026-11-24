@echo off
chcp 65001 > nul
title Развертывание резервного координатора RoboSats

cd /d "%~dp0"
python deploy_standby.py %1

echo.
pause
