@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AyurMitra - configure Hindi and Kannada translation

echo ============================================================
echo AyurMitra IndicTrans2 translation setup
echo ============================================================
echo This installs CPU PyTorch and IndicTrans2 dependencies into the project .venv.
echo It may use several GB of disk space. Model weights are downloaded on first translation.
echo A stable internet connection is required.
echo.
if not exist .venv\Scripts\python.exe (
  echo Project virtual environment not found.
  echo First run setup_and_run_windows.bat once, then run this helper again.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
python -m pip install -r requirements\optional_translation.txt
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env'; $c=@(); if (Test-Path $p) { $c=@(Get-Content $p | Where-Object { $_ -notmatch '^AYURMITRA_TRANSLATION=' }) }; $c += 'AYURMITRA_TRANSLATION=indictrans2'; Set-Content -Path $p -Value $c -Encoding ascii"
if errorlevel 1 goto failed
echo.
echo SUCCESS: Hindi and Kannada native-script translation is enabled in .env.
echo Restart the website. First translation downloads AI4Bharat model weights and may take time.
echo Test Hindi: अग्नि क्या है?
echo Test Kannada: ಅಗ್ನಿ ಎಂದರೇನು?
pause
exit /b 0
:failed
echo.
echo Translation setup failed. The main website can still run in English.
echo Check Python 3.11/3.12, internet access, disk space, and docs\MULTILINGUAL_SETUP.md.
pause
exit /b 1
