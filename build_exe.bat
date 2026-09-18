@echo off
title Build FinOps Standalone Windows Executable
cd /d "%~dp0"
echo ======================================================================
echo   Building Standalone Executable for FinOps Waste Hunter
echo ======================================================================
echo Checking PyInstaller installation...
python -m pip install pyinstaller
echo Compiling FinOps-Waste-Hunter.exe...
pyinstaller --noconfirm --onedir --windowed --name "FinOps-Waste-Hunter" ^
  --add-data "app/static;app/static" ^
  --add-data "sample_infrastructure;sample_infrastructure" ^
  --add-data "data;data" ^
  run_app.py
echo.
echo ======================================================================
echo Build finished! Executable is located in: dist\FinOps-Waste-Hunter\
echo ======================================================================
pause
