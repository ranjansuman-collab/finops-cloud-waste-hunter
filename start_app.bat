@echo off
title FinOps Cloud Waste Hunter & Auto-Remediator
cd /d "%~dp0"
echo ======================================================================
echo   FinOps Cloud Waste Hunter ^& Auto-Remediator
echo   ISWE309L Cloud Computing - Course Project Review-1
echo   Team: Vivek Pandey (24MIS0216) ^& S. Hemal (24MIS0050)
echo   Vellore Institute of Technology (VIT)
echo ======================================================================
echo Starting local FinOps server and opening dashboard...
python run_app.py
pause
