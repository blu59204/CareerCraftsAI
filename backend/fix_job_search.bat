@echo off
REM Windows fix script for CareerCraft AI job search dependencies

echo ==========================================
echo CareerCraft AI - Job Search Fix (Windows)
echo ==========================================
echo.

cd /d "%~dp0"

echo Checking Python version...
python --version
echo.

echo WARNING: You are using Python 3.13 which has dependency conflicts.
echo This script will try to work around them, but some warnings are expected.
echo.
pause

echo Step 1: Installing numpy (specific version for compatibility)...
pip install numpy==1.26.3
echo.

echo Step 2: Installing job scraping libraries...
pip install python-jobspy==1.1.82
pip install browser-use==0.8.0
pip install playwright==1.60.0
pip install agentql==1.19.0
echo.

echo Step 3: Installing LangChain (will show numpy warnings - safe to ignore)...
pip install langchain langchain-core langchain-anthropic langchain-openai langchain-ollama langgraph
echo.

echo Step 4: Installing other core dependencies...
pip install fastapi uvicorn sqlalchemy asyncpg redis httpx cryptography PyJWT pydantic pydantic-settings python-multipart slowapi
echo.

echo Step 5: Installing Playwright browsers...
playwright install chromium
echo.

echo ==========================================
echo Testing job scraping...
echo ==========================================
python test_job_scraping.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Job scraping is working!
    echo.
    echo Next steps:
    echo 1. Start backend: uvicorn app.main:app --reload --port 8000
    echo 2. Test job search in the UI
) else (
    echo.
    echo ✗ Job scraping tests failed
    echo Check the error messages above
)

pause
