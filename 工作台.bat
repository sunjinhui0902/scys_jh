@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo scys_jh 私人视频工作台
echo 1. 检查环境
echo 2. 恢复创作素材与软件
echo 3. 恢复全部大文件
echo 4. 渲染六秒示例
echo 5. 阅读使用说明
set /p scys_choice=请选择 1-5:
if "%scys_choice%"=="5" start "" "docs\换电脑与日常使用.md"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 新电脑初始化.bat
  pause
  exit /b 1
)
if "%scys_choice%"=="1" ".venv\Scripts\python.exe" scripts\doctor.py
if "%scys_choice%"=="2" ".venv\Scripts\python.exe" scripts\bundle.py restore --group core --group software
if "%scys_choice%"=="3" ".venv\Scripts\python.exe" scripts\bundle.py restore --group all
if "%scys_choice%"=="4" ".venv\Scripts\python.exe" scripts\render.py config\storyboard.example.json --output .local\示例预览.mp4
pause
