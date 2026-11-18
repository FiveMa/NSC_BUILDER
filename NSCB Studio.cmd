@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo NSCB Studio : environnement Python local introuvable.
    echo Consultez studio\README.md pour installer les dependances.
    pause
    exit /b 1
)
start "NSCB Studio" ".venv\Scripts\pythonw.exe" -m studio.app
