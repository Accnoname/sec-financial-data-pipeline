@echo off
rem ==============================================================================
rem DANG KY PIPELINE CHAY NGAM TU DONG VOI WINDOWS TASK SCHEDULER
rem Chay file nay voi quyen Run as Administrator de dang ky task
rem ==============================================================================

echo [1/2] Dang kiem tra duong dan Python...
for /f "tokens=*" %%i in ('where pythonw 2^>nul') do set PYTHONW_PATH=%%i

if "%PYTHONW_PATH%"=="" (
    echo Khong tim thay pythonw.exe tu dong. Su dung mac dinh C:\Program Files\Python310\pythonw.exe
    set PYTHONW_PATH=C:\Program Files\Python310\pythonw.exe
)

echo Duong dan Python ngam: %PYTHONW_PATH%
echo Duong dan thu muc du an: %~dp0

echo.
echo [2/2] Dang dang ky tac vu vao Windows Task Scheduler (Chay luc 02:00 AM hang ngay)...

schtasks /create /tn "SEC_Daily_Data_Pipeline" /tr "\"%PYTHONW_PATH%\" \"%~dp0run.py\" dag" /sc daily /st 02:00 /f /ru "%USERNAME%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================================
    echo [OK] DA DANG KY THANH CONG!
    echo Tac vu 'SEC_Daily_Data_Pipeline' se tu dong chay ngam luc 02:00 AM moi ngay.
    echo Khong can mo terminal, khong can mo code, may tinh se tu dong xu ly.
    echo.
    echo De xem hoac xoa: Mo Start Menu, go 'Task Scheduler' de kiem tra.
    echo ==============================================================================
) else (
    echo [FAIL] Khong the dang ky. Vui long chuot phai vao file nay va chon 'Run as administrator'.
)

pause
