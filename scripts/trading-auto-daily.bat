@echo off
chcp 65001 > nul
:: ============================================================
:: trading-auto-daily.bat
:: Arco Capital Investment Division - Daily Auto Trading
::
:: Called from Windows Task Scheduler at:
::   - Weekdays 22:20 JST (EDT period: 9:20 ET)
::   - Weekdays 23:20 JST (EST period: 9:20 ET)
:: check_market_timing.py decides if market opens in 10-45 min window
:: and only runs the CrewAI auto pipeline when it does.
::
:: Mode: --live uses paper account (no real money risk)
:: ============================================================

set PROJECT_DIR=C:\Users\17t14\Desktop\Claude
set LOG_DIR=%PROJECT_DIR%\outputs\auto-daily
set PYTHONIOENCODING=utf-8

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: Today's date (YYYYMMDD) for log filename
for /f "tokens=2 delims==" %%a in ('wmic os get LocalDateTime /value') do set dt=%%a
set TODAY=%dt:~0,8%
set LOGFILE=%LOG_DIR%\%TODAY%.log

cd /d "%PROJECT_DIR%"

echo. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"
echo [%date% %time%] trading-auto-daily.bat START >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

:: STEP 1: check market timing
echo [%date% %time%] STEP 1: checking market timing... >> "%LOGFILE%"
python "%PROJECT_DIR%\scripts\check_market_timing.py" >> "%LOGFILE%" 2>&1
if errorlevel 2 (
    echo [%date% %time%] ERROR: timing check failed -- abort >> "%LOGFILE%"
    exit /b 2
)
if errorlevel 1 (
    echo [%date% %time%] SKIP: outside 10-45min window >> "%LOGFILE%"
    exit /b 0
)

:: STEP 2: run AutoCrew auto pipeline (LIVE mode on paper account)
echo [%date% %time%] STEP 2: running AutoCrew --mode auto --live >> "%LOGFILE%"
python "%PROJECT_DIR%\investment_main.py" --mode auto --live >> "%LOGFILE%" 2>&1
set AUTO_RC=%errorlevel%

echo [%date% %time%] AutoCrew exit code=%AUTO_RC% >> "%LOGFILE%"

if %AUTO_RC% equ 0 (
    echo [%date% %time%] SUCCESS >> "%LOGFILE%"
) else (
    echo [%date% %time%] FAILED -- see log above for details >> "%LOGFILE%"
)

echo ============================================================ >> "%LOGFILE%"
exit /b %AUTO_RC%
