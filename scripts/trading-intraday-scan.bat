@echo off
chcp 65001 > nul
:: ============================================================
:: trading-intraday-scan.bat
:: Arco Capital - Intraday Lightweight Scan
::
:: Called from Windows Task Scheduler at:
::   - Weekdays 02:00 JST (EDT period: 13:00 ET, ~3.5h after open)
::   - Weekdays 03:00 JST (EST period: 13:00 ET, ~3.5h after open)
::
:: Screening is Python-only (no LLM cost).
:: Only analyses new candidates beyond morning's Top10.
:: Cost per run: $0 (no new candidate) to $0.5-1.0 (1-2 new analyses)
:: ============================================================

set PROJECT_DIR=C:\Users\17t14\Desktop\Claude
set LOG_DIR=%PROJECT_DIR%\outputs\intraday-scan
set PYTHONIOENCODING=utf-8

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: Today's date (YYYYMMDD) for log filename
for /f "tokens=2 delims==" %%a in ('wmic os get LocalDateTime /value') do set dt=%%a
set TODAY=%dt:~0,8%
set LOGFILE=%LOG_DIR%\%TODAY%.log

cd /d "%PROJECT_DIR%"

echo. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"
echo [%date% %time%] trading-intraday-scan.bat START >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

:: STEP 1: Verify market is currently OPEN
echo [%date% %time%] STEP 1: checking market status... >> "%LOGFILE%"
python "%PROJECT_DIR%\scripts\check_market_open.py" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] SKIP: market is closed >> "%LOGFILE%"
    exit /b 0
)

:: STEP 2: Run intraday scan (live mode on paper account)
echo [%date% %time%] STEP 2: running intraday-scan --live >> "%LOGFILE%"
python "%PROJECT_DIR%\investment_main.py" --mode intraday-scan --live >> "%LOGFILE%" 2>&1
set SCAN_RC=%errorlevel%

echo [%date% %time%] intraday-scan exit code=%SCAN_RC% >> "%LOGFILE%"
if %SCAN_RC% equ 0 (
    echo [%date% %time%] SUCCESS >> "%LOGFILE%"
) else (
    echo [%date% %time%] FAILED >> "%LOGFILE%"
)

echo ============================================================ >> "%LOGFILE%"
exit /b %SCAN_RC%
