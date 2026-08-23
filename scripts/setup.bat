@echo off
REM PUNGOLAY SA PANAY - setup for Windows
cd /d "%~dp0.."

echo == Creating virtual environment ==
python -m venv .venv
call .venv\Scripts\activate.bat

echo == Installing dependencies ==
python -m pip install --upgrade pip
pip install -r requirements.txt

echo == Downloading pose model + fonts ==
python tools\setup_assets.py

echo.
echo Setup complete. Run the game with:
echo     .venv\Scripts\activate ^&^& python main.py
pause