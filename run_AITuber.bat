@echo off
rem Set console to UTF-8 for this window
chcp 65001

rem echo Launching Style-Bert-VITS2 Server in a new window...
rem start "Style-Bert-VITS2" cmd /c "c:\Users\drmdr\Documents\Surfwind\AITuber\sbv2\Style-Bert-VITS2\start_sbv2.bat"

rem echo Waiting for Style-Bert-VITS2 server to initialize (15 seconds)...
rem timeout /t 15 /nobreak

echo Starting AITuber in this window...
set PYTHONIOENCODING=utf-8
rem Add Style-Bert-VITS2 package parent to PYTHONPATH
rem set PYTHONPATH=%PYTHONPATH%;c:\Users\drmdr\Documents\Surfwind\AITuber\sbv2\Style-Bert-VITS2
python "c:\Users\drmdr\Documents\Surfwind\AITuber\AITuber.py"

pause
