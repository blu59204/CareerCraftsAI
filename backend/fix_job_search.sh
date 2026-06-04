#!/bin/bash
# Fix job search dependencies and test

echo "=========================================="
echo "CareerCraft AI - Job Search Fix Script"
echo "=========================================="

cd "$(dirname "$0")"

# Check Python version
python_version=$(python --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "Python version: $python_version"

if [[ "$python_version" == "3.13" ]]; then
    echo "⚠️  WARNING: Python 3.13 has dependency conflicts"
    echo "   Recommended: Use Python 3.12 or 3.11"
    echo "   Continuing anyway..."
fi

echo ""
echo "Step 1: Installing core dependencies..."
pip install --no-deps numpy==1.26.3

echo ""
echo "Step 2: Installing job scraping libraries..."
pip install --no-deps python-jobspy==1.1.82
pip install --no-deps browser-use==0.8.0
pip install --no-deps playwright==1.60.0
pip install --no-deps agentql==1.19.0

echo ""
echo "Step 3: Installing LangChain (may show numpy warnings - safe to ignore)..."
pip install langchain langchain-core langchain-anthropic langchain-openai langchain-ollama langgraph

echo ""
echo "Step 4: Installing other dependencies..."
pip install fastapi uvicorn sqlalchemy asyncpg redis httpx cryptography PyJWT pydantic pydantic-settings

echo ""
echo "Step 5: Installing Playwright browsers..."
playwright install chromium

echo ""
echo "=========================================="
echo "Testing job scraping..."
echo "=========================================="

python test_job_scraping.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Job scraping is working!"
    echo ""
    echo "Next steps:"
    echo "1. Start the backend: uvicorn app.main:app --reload --port 8000"
    echo "2. Test job search in the UI"
    echo "3. Check logs if users report issues"
else
    echo ""
    echo "❌ Job scraping tests failed"
    echo "See docs/JOB_SEARCH_FIX.md for troubleshooting"
fi
