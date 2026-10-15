@echo off
chcp 65001 >nul
cd /d "%~dp0DouK-Downloader"
if not exist "DouK-Downloader.exe" (
  echo 请先在项目根目录运行 新电脑初始化.bat 恢复软件。
  pause
  exit /b 1
)
"DouK-Downloader.exe"
pause
