# Job Search Agent Issues - Diagnosis & Fix

## Problem Summary

The job search agents are **NOT working properly** because:

1. ❌ **Missing dependencies** - JobSpy, browser-use, Playwright not installed
2. ❌ **Dependency conflicts** - numpy version conflicts between packages
3. ❌ **Playwright browsers not installed** - Chromium needed for browser automation
4. ⚠️ **Some job sources blocked** - ZipRecruiter (403), Glassdoor (API error)

## What's Working

✅ **JobSpy** - Successfully scraping Indeed and LinkedIn (found 20 jobs in test)
✅ **RemoteOK API** - Working (found 5 jobs)
✅ **Greenhouse API** - Working (found 474 jobs at Stripe)
✅ **browser-use library** - Imported successfully
✅ **Playwright** - Imported successfully

## What's Broken

❌ **Python environment** - Dependencies not installed in your current Python environment
❌ **Numpy conflict** - python-jobspy requires numpy==1.26.3, but langchain-community requires numpy>=2.1.0 (Python 3.13)
❌ **Google Jobs scraping** - No job cards found (likely CAPTCHA/blocked)
❌ **Lever API** - No jobs returned

## Root Cause

You're using **Python 3.13**, which has stricter numpy requirements. The packages have conflicting dependencies:

```
python-jobspy==1.1.82 → requires numpy==1.26.3
langchain-community==0.4.2 → requires numpy>=2.1.0 (Python 3.13)
```

This is a known issue with Python 3.13 and older packages.

## Solutions

### Option 1: Use Python 3.11 or 3.12 (Recommended)

Python 3.13 is very new and many packages haven't updated yet.

```bash
# Install Python 3.12
conda create -n careercraft python=3.12
conda activate careercraft

# Install dependencies
cd backend
pip install -r requirements.txt
playwright install chromium
```

### Option 2: Fix numpy conflict manually

```bash
cd backend

# Install packages in specific order to avoid conflicts
pip install numpy==1.26.3
pip install python-jobspy==1.1.82
pip install browser-use==0.8.0
pip install playwright==1.60.0
pip install agentql==1.19.0

# Install LangChain (will warn about numpy but works)
pip install langchain langchain-core langchain-anthropic langchain-openai
pip install langgraph

# Install other requirements
pip install fastapi uvicorn sqlalchemy asyncpg redis httpx cryptography PyJWT

# Install Playwright browsers
playwright install chromium
```

### Option 3: Use Docker (Best for production)

The Docker setup handles all dependencies correctly:

```bash
cd /mnt/d/CareerCraft\ AI
docker compose up --build
```

## Verification Steps

After fixing dependencies, run these tests:

```bash
cd backend

# Test 1: Job scraping sources
python test_job_scraping.py

# Test 2: Job search agent
python test_job_agent.py

# Test 3: Start backend server
uvicorn app.main:app --reload --port 8000
```

## Expected Results

When working correctly:

```
✓ JOBSPY: WORKING (Indeed, LinkedIn)
✓ REMOTEOK: WORKING
✓ ATS: WORKING (Greenhouse)
✓ BROWSER_USE: WORKING
✓ CONFIG: WORKING
⚠️ GOOGLE_JOBS: May be blocked (CAPTCHA)
```

## Configuration Needed

Check your `.env` file has these set:

```bash
# Optional but recommended for better scraping
AGENTQL_API_KEY=your-key-here  # Get from https://dev.agentql.com
SEARXNG_URL=http://localhost:8888  # Self-hosted meta-search

```

## Why Job Search Might Fail for Users

Even after fixing dependencies, users might see no results if:

1. **No API keys configured** - User needs to add their LLM API key in settings
2. **Rate limiting** - Job sites block too many requests
3. **Invalid search query** - Query too specific or location not recognized
4. **Network issues** - Firewall blocking job sites
5. **Browser automation blocked** - LinkedIn/Naukri detect automation

## Recommended Architecture Changes

### Short-term (Fix now):

1. ✅ Install dependencies in Python 3.12 environment
2. ✅ Run `playwright install chromium`
3. ✅ Test with `python test_job_scraping.py`
4. ✅ Deploy via Docker for production

### Long-term (Improve reliability):

1. **Add fallback sources** - If JobSpy fails, try RemoteOK → Greenhouse → Google Jobs
2. **Better error messages** - Tell users which sources failed and why
3. **Retry logic** - Retry failed sources with exponential backoff
4. **Cache results** - Cache job listings for 1 hour to reduce API calls
5. **User feedback** - Let users report "no results" to track issues

## Quick Fix Script

```bash
#!/bin/bash
# quick_fix.sh - Fix job search dependencies

cd /mnt/d/CareerCraft\ AI/backend

# Check Python version
python_version=$(python --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ "$python_version" = "3.13" ]; then
    echo "⚠️  Python 3.13 detected - recommend using 3.12"
    echo "Attempting to install anyway..."
fi

# Install in specific order
pip install numpy==1.26.3
pip install python-jobspy browser-use playwright agentql
pip install langchain langchain-core langchain-anthropic langchain-openai langgraph
pip install fastapi uvicorn sqlalchemy asyncpg redis httpx cryptography PyJWT

# Install Playwright browsers
playwright install chromium

# Test
python test_job_scraping.py
```

## Next Steps

1. **Choose a solution** (Python 3.12 recommended)
2. **Install dependencies** properly
3. **Run tests** to verify everything works
4. **Update frontend** to show better error messages when job search fails
5. **Add monitoring** to track which sources are working/failing

## Contact

If issues persist after following these steps, check:
- Backend logs: `docker compose logs -f backend`
- Frontend console: Browser DevTools → Console
- Agent runs: Check `/agents/runs` API endpoint
