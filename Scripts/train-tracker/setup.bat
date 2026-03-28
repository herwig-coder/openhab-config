@echo off
echo ========================================
echo OpenHAB Train Tracker - Setup
echo ========================================
echo.

echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    echo Make sure Python is installed and in your PATH
    pause
    exit /b 1
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Creating .env file from template...
if not exist .env (
    copy .env.example .env
    echo Created .env file - Please edit it with your OpenHAB credentials
) else (
    echo .env file already exists, skipping
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file with your OpenHAB credentials and train route
echo 2. Run: venv\Scripts\activate
echo 3. Run: python train_tracker.py --verbose
echo.
echo Or open this folder in VS Code and press F5 to debug
echo.
pause
