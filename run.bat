@echo off
cd /d "%~dp0"

echo ============================================
echo  Customer Service Coach Agent  -  Launcher
echo ============================================
echo.

REM --- try current python first (may be an activated venv) ---
where python >nul 2>nul
if errorlevel 1 goto USE_SYSTEM

python -c "import streamlit" >nul 2>&1
if errorlevel 1 goto USE_SYSTEM

echo [OK] Using current python.
python -m streamlit run app.py
goto DONE

:USE_SYSTEM
if exist "C:\Python312\python.exe" (
    echo [OK] Current python has no streamlit. Using system Python 3.12.
    "C:\Python312\python.exe" -m streamlit run app.py
    goto DONE
)

echo [ERROR] No Python with streamlit found.
echo         Run:  C:\Python312\python.exe -m pip install -r requirements.txt

:DONE
echo.
echo Server stopped.
pause
