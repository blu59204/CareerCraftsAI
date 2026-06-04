#!/usr/bin/env python3
"""
Comprehensive job scraping diagnostic script.
Tests all job search sources and identifies what's working/broken.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault("APP_SECRET_KEY", "test-key-32-chars-minimum-test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")


def test_jobspy():
    """Test JobSpy scraping (LinkedIn, Indeed, Glassdoor, etc.)"""
    print("\n" + "="*60)
    print("TEST 1: JobSpy (LinkedIn, Indeed, Glassdoor)")
    print("="*60)

    try:
        from jobspy import scrape_jobs

        print("Testing Indeed...")
        df = scrape_jobs(
            site_name=['indeed'],
            search_term='software engineer',
            location='Remote',
            results_wanted=5,
            hours_old=72,
        )

        if df is not None and not df.empty:
            print(f"✓ Indeed: Found {len(df)} jobs")
            for i, row in df.head(3).iterrows():
                print(f"  • {row['title']} at {row['company']}")
        else:
            print("✗ Indeed: No results")

        print("\nTesting LinkedIn...")
        df = scrape_jobs(
            site_name=['linkedin'],
            search_term='python developer',
            location='United States',
            results_wanted=5,
            hours_old=72,
        )

        if df is not None and not df.empty:
            print(f"✓ LinkedIn: Found {len(df)} jobs")
            for i, row in df.head(3).iterrows():
                print(f"  • {row['title']} at {row['company']}")
        else:
            print("✗ LinkedIn: No results (may be rate-limited)")

        return True

    except Exception as e:
        print(f"✗ JobSpy FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_remoteok():
    """Test RemoteOK API"""
    print("\n" + "="*60)
    print("TEST 2: RemoteOK API")
    print("="*60)

    try:
        import httpx

        response = httpx.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "CareerCraftAI/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        jobs = response.json()

        # Filter for software jobs
        software_jobs = [
            j for j in jobs
            if isinstance(j, dict) and j.get('position') and
            'software' in str(j.get('position', '')).lower()
        ][:5]

        if software_jobs:
            print(f"✓ RemoteOK: Found {len(software_jobs)} software jobs")
            for job in software_jobs[:3]:
                print(f"  • {job.get('position')} at {job.get('company')}")
            return True
        else:
            print("✗ RemoteOK: No software jobs found")
            return False

    except Exception as e:
        print(f"✗ RemoteOK FAILED: {e}")
        return False


def test_greenhouse_lever():
    """Test public ATS APIs (Greenhouse, Lever)"""
    print("\n" + "="*60)
    print("TEST 3: Public ATS (Greenhouse, Lever)")
    print("="*60)

    try:
        import httpx

        # Test Greenhouse
        print("Testing Greenhouse (Stripe)...")
        response = httpx.get(
            "https://boards-api.greenhouse.io/v1/boards/stripe/jobs",
            params={"content": "true"},
            timeout=10,
        )
        response.raise_for_status()
        jobs = response.json().get('jobs', [])

        if jobs:
            print(f"✓ Greenhouse: Found {len(jobs)} jobs at Stripe")
            for job in jobs[:3]:
                print(f"  • {job.get('title')}")
        else:
            print("✗ Greenhouse: No jobs found")

        # Test Lever
        print("\nTesting Lever (Netflix)...")
        response = httpx.get(
            "https://api.lever.co/v0/postings/netflix",
            params={"mode": "json"},
            timeout=10,
        )
        response.raise_for_status()
        jobs = response.json()

        if jobs:
            print(f"✓ Lever: Found {len(jobs)} jobs at Netflix")
            for job in jobs[:3]:
                print(f"  • {job.get('text')}")
            return True
        else:
            print("✗ Lever: No jobs found")
            return False

    except Exception as e:
        print(f"✗ Public ATS FAILED: {e}")
        return False


async def test_browser_use():
    """Test browser-use with Playwright"""
    print("\n" + "="*60)
    print("TEST 4: browser-use + Playwright")
    print("="*60)

    try:
        from browser_use import Browser
        from playwright.async_api import async_playwright

        print("Testing Playwright browser launch...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://example.com")
            title = await page.title()
            await browser.close()

            if title:
                print(f"✓ Playwright: Browser launched successfully (title: {title})")
            else:
                print("✗ Playwright: Browser launched but no title")

        print("\nTesting browser-use...")
        # Just test import and basic setup
        browser = Browser(headless=True)
        print("✓ browser-use: Initialized successfully")

        return True

    except Exception as e:
        print(f"✗ browser-use/Playwright FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_google_jobs_scraping():
    """Test Google Jobs scraping via Playwright"""
    print("\n" + "="*60)
    print("TEST 5: Google Jobs Scraping")
    print("="*60)

    try:
        from playwright.async_api import async_playwright
        from urllib.parse import quote_plus

        query = quote_plus("python developer jobs in Remote")
        url = f"https://www.google.com/search?q={query}&ibp=htl;jobs"

        print(f"Navigating to: {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # Try to find job cards
                cards = page.locator('div[role="treeitem"]')
                count = await cards.count()

                if count > 0:
                    print(f"✓ Google Jobs: Found {count} job cards")

                    # Extract first 3 jobs
                    for i in range(min(3, count)):
                        try:
                            text = await cards.nth(i).inner_text(timeout=2000)
                            lines = [l.strip() for l in text.split('\n') if l.strip()]
                            if lines:
                                print(f"  • {lines[0]}")
                        except:
                            pass

                    await browser.close()
                    return True
                else:
                    print("✗ Google Jobs: No job cards found (may be blocked/CAPTCHA)")
                    await browser.close()
                    return False

            except Exception as e:
                print(f"✗ Google Jobs navigation failed: {e}")
                await browser.close()
                return False

    except Exception as e:
        print(f"✗ Google Jobs FAILED: {e}")
        return False


def test_config():
    """Test configuration and environment"""
    print("\n" + "="*60)
    print("TEST 6: Configuration Check")
    print("="*60)

    try:
        from app.core.config import settings

        print(f"AGENTQL_API_KEY: {'✓ Set' if settings.AGENTQL_API_KEY else '✗ Not set'}")
        print(f"SEARXNG_URL: {'✓ Set' if settings.SEARXNG_URL else '✗ Not set'}")
        print(f"PINCHTAB_URL: {settings.PINCHTAB_URL}")
        print(f"PINCHTAB_TOKEN: {'✓ Set' if settings.PINCHTAB_TOKEN else '✗ Not set'}")

        if not settings.AGENTQL_API_KEY:
            print("\n⚠️  AgentQL not configured - live browser scraping disabled")
        if not settings.SEARXNG_URL:
            print("⚠️  SearXNG not configured - meta-search disabled")

        return True

    except Exception as e:
        print(f"✗ Config check FAILED: {e}")
        return False


async def main():
    """Run all diagnostic tests"""
    print("\n" + "="*60)
    print("JOB SCRAPING DIAGNOSTIC TOOL")
    print("="*60)

    results = {}

    # Sync tests
    results['jobspy'] = test_jobspy()
    results['remoteok'] = test_remoteok()
    results['ats'] = test_greenhouse_lever()
    results['config'] = test_config()

    # Async tests
    results['browser_use'] = await test_browser_use()
    results['google_jobs'] = await test_google_jobs_scraping()

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    working = sum(1 for v in results.values() if v)
    total = len(results)

    for test, status in results.items():
        icon = "✓" if status else "✗"
        print(f"{icon} {test.upper()}: {'WORKING' if status else 'FAILED'}")

    print(f"\n{working}/{total} sources working")

    if working == 0:
        print("\n❌ CRITICAL: No job sources are working!")
        print("\nPossible issues:")
        print("1. Missing dependencies (run: pip install -r requirements.txt)")
        print("2. Playwright browsers not installed (run: playwright install chromium)")
        print("3. Network/firewall blocking job sites")
        print("4. Rate limiting from job sites")
    elif working < total:
        print("\n⚠️  Some sources failing - job search will work but with reduced coverage")
    else:
        print("\n✅ All sources working!")

    return working > 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
