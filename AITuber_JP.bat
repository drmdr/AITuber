@echo off
rem 日本語版AITuber起動スクリプト
chcp 65001
echo AITuber日本語版を起動しています...
set PYTHONIOENCODING=utf-8

rem Pythonの絶対パスを使用
"C:\Users\drmdr\AppData\Local\Programs\Python\Python310\python.exe" "c:\Users\drmdr\Documents\Surfwind\AITuber\AITuber.py" --language ja

pause
