@echo off
rem Set console to UTF-8 for this window
chcp 65001

rem echo Launching Style-Bert-VITS2 Server in a new window...
rem start "Style-Bert-VITS2" cmd /c "c:\Users\drmdr\Documents\Surfwind\AITuber\sbv2\Style-Bert-VITS2\start_sbv2.bat"

rem echo Waiting for Style-Bert-VITS2 server to initialize (15 seconds)...
rem timeout /t 15 /nobreak

echo Starting AITuber...
set PYTHONIOENCODING=utf-8

:language_select
echo.
echo Please select a language for AITuber:
echo 1. Japanese (日本語)
echo 2. English
echo 3. Spanish (Español)
echo.

CHOICE /C 123 /N /M "Enter your choice (1, 2, or 3):"

IF ERRORLEVEL 1 SET LANG_CODE=ja
IF ERRORLEVEL 2 SET LANG_CODE=en
IF ERRORLEVEL 3 SET LANG_CODE=es

IF "%LANG_CODE%"=="" (
    echo Invalid choice. Please try again.
    goto language_select
)

echo Selected language: %LANG_CODE%
echo Launching AITuber with %LANG_CODE%...

python "c:\Users\drmdr\Documents\Surfwind\AITuber\AITuber.py" --language %LANG_CODE%

pause
