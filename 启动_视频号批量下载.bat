@echo off
chcp 65001 >nul
cd /d "%~dp000_对标与采集工具\wx_channel"
if not exist "wx_channel.exe" (
  echo 请先在项目根目录运行 新电脑初始化.bat 恢复软件。
  pause
  exit /b 1
)
"wx_channel.exe"
pause
