@echo off
chcp 65001 >nul
cls
echo ========================================
echo   Cross-Modal Privacy Detection Performance Test
echo ========================================
echo.
echo Test Objectives:
echo   1. Privacy entity detection accuracy ^> 80%%
echo   2. Algorithm processing speed ^< 2s
echo.
echo ========================================
pause
echo.

python test_performance_metrics.py

echo.
echo ========================================
pause

