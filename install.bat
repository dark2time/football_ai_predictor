@echo off
echo ============================================
echo  Football AI Predictor Pro - Setup
echo ============================================
echo.

:: Check Python version
python --version 2>NUL
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+ from python.org
    pause
    exit /b 1
)

echo.
echo [1/4] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/4] Installing PyQt6...
python -m pip install PyQt6

echo.
echo [3/4] Installing core dependencies...
python -m pip install pandas numpy scikit-learn scipy requests

echo.
echo [4/4] Installing optional dependencies...
python -m pip install selenium webdriver-manager beautifulsoup4 lxml

echo.
echo ============================================
echo  Installation complete!
echo  Run: python main.py
echo ============================================
pause
