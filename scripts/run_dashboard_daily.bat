@echo off
REM Arco Capital daily dashboard runner (scheduled task wrapper)
REM Triggered by schtasks at 23:55 JST daily.
REM Japanese comments removed to avoid cmd.exe codepage issues.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\17t14\Desktop\Claude\.claude\worktrees\funny-visvesvaraya-9cf663"

python -m operations.dashboard_report --date today
set RC=%ERRORLEVEL%

echo [%date% %time%] dashboard_report exit=%RC% >> operations\dashboard_cron.log

endlocal & exit /b %RC%
