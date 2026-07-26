@echo off
chcp 936 >nul
title 华为巡检平台 - 停止

echo.
echo   正在查找占用 8080 端口的服务
echo.

set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"TCP.*:8080 .*LISTENING"') do (
    echo   停止进程 PID %%p
    taskkill /f /pid %%p >nul 2>&1
    set FOUND=1
)

if "%FOUND%"=="0" (
    echo   没有服务在运行。
) else (
    echo.
    echo   已停止。
)

echo.
timeout /t 3 /nobreak >nul
