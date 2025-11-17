@echo off
REM Oracle Session Monitoring Script - Run every minute for 30 minutes
REM Usage: monitor_oracle_sessions.bat [username] [password] [tns_name]
REM Example: monitor_oracle_sessions.bat scott tiger ORCL

setlocal enabledelayedexpansion

if "%1"=="" (
    echo Usage: monitor_oracle_sessions.bat [username] [password] [tns_name]
    echo Example: monitor_oracle_sessions.bat scott tiger ORCL
    exit /b 1
)

set USERNAME=%1
set PASSWORD=%2
set TNS_NAME=%3
set OUTPUT_FILE=oracle_session_log_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.txt
set /a COUNTER=0
set /a MAX_ITERATIONS=30

echo ========================================
echo Oracle Session Monitoring Started
echo Monitoring for 30 minutes (30 iterations)
echo Output file: %OUTPUT_FILE%
echo ========================================
echo.

:LOOP
set /a COUNTER+=1
echo [%date% %time%] Iteration !COUNTER! of %MAX_ITERATIONS% >> %OUTPUT_FILE%
echo ======================================== >> %OUTPUT_FILE%

REM Run the monitoring query
sqlplus -s %USERNAME%/%PASSWORD%@%TNS_NAME% @monitor_query.sql >> %OUTPUT_FILE%

echo [%date% %time%] Iteration !COUNTER! completed
echo.

if !COUNTER! GEQ %MAX_ITERATIONS% (
    echo Monitoring completed. Check %OUTPUT_FILE% for results.
    goto :END
)

REM Wait 60 seconds before next iteration
timeout /t 60 /nobreak >nul
goto :LOOP

:END
endlocal

