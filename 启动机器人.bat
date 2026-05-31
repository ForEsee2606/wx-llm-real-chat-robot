@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo ========================================
echo   ΢                 ...
echo        ڼ䲻Ҫ ֶ     ΢ Ŵ   
echo   ֹͣ:    Ctrl+C   ֱ ӹرձ     
echo ========================================
echo.

echo [1/3]         ΢  3.9...
start "" "C:\Program Files\Tencent\WeChat\WeChat.exe"

echo [2/3]  ȴ ΢          ¼(15  )...
echo            û  ¼,        ڼ   ΢ Ŵ  ڵ  ¼
timeout /t 5 /nobreak >nul

echo [3/3]              ...
echo.
"C:\Users\26065\Desktop\aiai2\.venv-bot\Scripts\python.exe" -u "C:\Users\26065\Desktop\aiai2\wechat_bot.py"
echo.
echo ========================================
echo           ֹͣ
echo ========================================
pause
