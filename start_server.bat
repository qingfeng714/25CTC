@echo off
echo ========================================
echo   Medical Privacy Protection System - Start Server
echo ========================================
echo.
echo [INFO] Press Ctrl+C to stop the service
echo.
python app.py --port 5000
pause

