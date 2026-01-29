@echo off
echo ========================================
echo Starting Profiler Agentic Automation
echo ========================================

REM Change to POC directory
cd /d "c:\Users\SaiShravan.V\OneDrive - Ivanti\Desktop\POC"

REM Clear Python cache to avoid stale bytecode
echo Cleaning Python cache...
for /d /r "src" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo Cache cleared.

REM Kill any existing Python processes
echo Stopping existing servers...
taskkill /IM python.exe /F 2>nul
timeout /t 2 /nobreak >nul

REM Start Flask application
echo Starting Flask server...
python app.py

pause
