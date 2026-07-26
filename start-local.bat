@echo off
chcp 936 >nul
cd /d "%~dp0"
title 华为巡检平台 - 本地模式

echo.
echo   华为巡检平台 · 本地模式
echo   ----------------------------------------
echo.

if not exist "web\dist\index.html" (
    echo   [!] 找不到前端产物 web\dist
    echo.
    echo   首次使用请先在 web 目录执行一次：
    echo       npm ci
    echo       npm run build
    echo.
    pause
    exit /b 1
)

py -3 -c "import fastapi" 2>nul
if errorlevel 1 (
    echo   [!] Python 依赖未安装
    echo.
    echo   请先执行： pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

netstat -ano | findstr /r /c:"TCP.*:8080 .*LISTENING" >nul
if not errorlevel 1 (
    echo   [!] 8080 端口已被占用，可能已经启动过一次了
    echo.
    echo       直接打开 http://localhost:8080/app/ 即可
    echo       要重启请先运行 stop-local.bat
    echo.
    pause
    exit /b 1
)

set LOCAL_MODE=true
set PYTHONUTF8=1

echo   启动中，稍候会自动打开浏览器
echo   关闭本窗口或按 Ctrl+C 即可停止服务
echo.

start "" /b cmd /c "timeout /t 4 /nobreak >nul && start "" http://localhost:8080/app/"

py -3 server.py

echo.
echo   服务已停止。
pause
