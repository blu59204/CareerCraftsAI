"""
form_filler.py — Platform-specific form filling for job applications.

Uses BrowserControlService (Playwright) for browser control with CSS-selector-based automation.
Each platform (LinkedIn Easy Apply, Indeed Apply, Naukri, generic) has its
own fill sequence.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class FormFillerService:
    """Fills job application forms using Playwright browser automation."""

    def __init__(self, browser: Any) -> None:
        self.browser = browser

    async def fill_common_fields(self, profile: dict[str, Any], user_id: str) -> None:
        """Fill common contact/location fields across all platforms."""
        field_map: dict[str, list[str]] = {
            "name": ["input[name*='name']", "input[id*='name']", "input[placeholder*='name']"],
            "email": ["input[name*='email']", "input[type='email']", "input[id*='email']"],
            "phone": ["input[name*='phone']", "input[type='tel']", "input[id*='phone']"],
            "linkedin": ["input[name*='linkedin']", "input[id*='linkedin']"],
            "github": ["input[name*='github']", "input[id*='github']"],
        }

        field_values: dict[str, str | None] = {
            "name": profile.get("full_name"),
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "linkedin": profile.get("linkedin_url"),
            "github": profile.get("github_url"),
        }

        for field, selectors in field_map.items():
            val = field_values.get(field)
            if not val:
                continue
            for sel in selectors:
                try:
                    exists = await self.browser.element_exists(sel, user_id)
                    if exists:
                        await self.browser.type_text(sel, str(val), user_id)
                        break
                except Exception:
                    continue

    async def fill_linkedin_easy_apply(
        self,
        job_url: str,
        user_id: str,
        resume_path: str,
        cover_letter: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        screenshots: list[str] = []
        await self.browser.navigate(job_url, user_id)

        apply_btn = ".jobs-apply-button, button[aria-label*='Easy Apply']"
        exists = await self.browser.element_exists(apply_btn, user_id)
        if not exists:
            return {"status": "failed", "error": "LinkedIn Easy Apply button not found"}

        await self.browser.click(apply_btn, user_id)
        await asyncio.sleep(2.0)

        modal_found = await self.browser.wait_for_element(".jobs-easy-apply-modal", user_id, timeout_ms=8000)
        if not modal_found:
            return {"status": "failed", "error": "Easy Apply modal did not appear"}

        for step in range(10):
            try:
                shot = await self.browser.screenshot(user_id)
                if shot:
                    screenshots.append(shot)
            except Exception:
                pass

            file_input = "input[type='file']"
            if await self.browser.element_exists(file_input, user_id):
                await self.browser.upload_file(file_input, resume_path, user_id)

            for ta_sel in ("textarea[id*='cover'], textarea[name*='message'], textarea"):
                try:
                    if await self.browser.element_exists(ta_sel, user_id):
                        await self.browser.type_text(ta_sel, cover_letter[:2000], user_id)
                        break
                except Exception:
                    continue

            await self.fill_common_fields(profile, user_id)

            next_btn = ".jobs-easy-apply-form-footer__next-button, button[aria-label='Continue to next step']"
            review_btn = "button[aria-label='Review your application']"
            submit_btn = ".jobs-easy-apply-form-footer__submit-button, button[aria-label='Submit application']"

            if await self.browser.element_exists(submit_btn, user_id):
                break
            elif await self.browser.element_exists(review_btn, user_id):
                await self.browser.click(review_btn, user_id)
            elif await self.browser.element_exists(next_btn, user_id):
                await self.browser.click(next_btn, user_id)
                await asyncio.sleep(2.0)
            else:
                break

        return {"status": "filled", "screenshots": screenshots}

    async def fill_indeed_apply(
        self,
        job_url: str,
        user_id: str,
        resume_path: str,
        cover_letter: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        screenshots: list[str] = []
        await self.browser.navigate(job_url, user_id)

        apply_btn = ".jobsearch-IndeedApplyButton-newDesign, button[id*='apply']"
        exists = await self.browser.element_exists(apply_btn, user_id)
        if not exists:
            return {"status": "failed", "error": "Indeed Apply button not found"}

        await self.browser.click(apply_btn, user_id)
        await asyncio.sleep(3.0)

        try:
            shot = await self.browser.screenshot(user_id)
            if shot:
                screenshots.append(shot)
        except Exception:
            pass

        file_input = "input[type='file']"
        if await self.browser.element_exists(file_input, user_id):
            await self.browser.upload_file(file_input, resume_path, user_id)

        for ta_sel in ("textarea[name*='cover']", "textarea[id*='cover']", "textarea"):
            try:
                if await self.browser.element_exists(ta_sel, user_id):
                    await self.browser.type_text(ta_sel, cover_letter[:2000], user_id)
                    break
            except Exception:
                continue

        await self.fill_common_fields(profile, user_id)

        auth_sel = "input[type='radio'][value='Yes'], input[id*='authorized']"
        if await self.browser.element_exists(auth_sel, user_id):
            await self.browser.click(auth_sel, user_id)

        return {"status": "filled", "screenshots": screenshots}

    async def fill_naukri(
        self,
        job_url: str,
        user_id: str,
        resume_path: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        screenshots: list[str] = []
        await self.browser.navigate(job_url, user_id)

        login_present = await self.browser.element_exists(".login-btn", user_id)
        if login_present:
            return {"status": "failed", "error": "Naukri requires login. Connect account in Settings."}

        apply_btn = ".apply-button, button.apply"
        exists = await self.browser.element_exists(apply_btn, user_id)
        if not exists:
            return {"status": "failed", "error": "Naukri apply button not found"}

        await self.browser.click(apply_btn, user_id)
        await asyncio.sleep(2.0)

        try:
            shot = await self.browser.screenshot(user_id)
            if shot:
                screenshots.append(shot)
        except Exception:
            pass

        file_input = "input[type='file'], input[name*='resume']"
        if await self.browser.element_exists(file_input, user_id):
            await self.browser.upload_file(file_input, resume_path, user_id)

        headline_sel = "textarea[name*='headline'], input[name*='headline']"
        if await self.browser.element_exists(headline_sel, user_id):
            await self.browser.type_text(headline_sel, profile.get("headline", "")[:120], user_id)

        return {"status": "filled", "screenshots": screenshots}

    async def fill_generic_form(
        self,
        job_url: str,
        user_id: str,
        resume_path: str,
        cover_letter: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        screenshots: list[str] = []
        await self.browser.navigate(job_url, user_id)
        await asyncio.sleep(2.0)

        try:
            shot = await self.browser.screenshot(user_id)
            if shot:
                screenshots.append(shot)
        except Exception:
            pass

        for btn in (
            "button:has-text('Apply')",
            "button:has-text('Apply Now')",
            "button[type='submit']",
            "a:has-text('Apply')",
        ):
            try:
                if await self.browser.element_exists(btn, user_id):
                    await self.browser.click(btn, user_id)
                    await asyncio.sleep(2.0)
                    break
            except Exception:
                continue

        file_inputs = [
            "input[type='file']",
            "input[accept*='pdf']",
            "input[name*='resume']",
            "input[name*='cv']",
        ]
        for fi in file_inputs:
            try:
                if await self.browser.element_exists(fi, user_id):
                    await self.browser.upload_file(fi, resume_path, user_id)
                    break
            except Exception:
                continue

        textareas = ["textarea", "textarea[name*='cover']", "textarea[name*='message']"]
        for ta in textareas:
            try:
                if await self.browser.element_exists(ta, user_id):
                    await self.browser.type_text(ta, cover_letter[:2000], user_id)
                    break
            except Exception:
                continue

        await self.fill_common_fields(profile, user_id)
        return {"status": "filled", "screenshots": screenshots}

    async def submit_application(self, platform: str, user_id: str) -> dict[str, Any]:
        submit_selectors: dict[str, str] = {
            "linkedin": ".jobs-easy-apply-form-footer__submit-button, button[aria-label='Submit application']",
            "indeed": "[data-testid='submit-button'], button[type='submit']",
            "naukri": ".apply-button.btn-primary, button[type='submit']",
            "generic": "button[type='submit'], input[type='submit']",
        }
        sel = submit_selectors.get(platform, submit_selectors["generic"])
        await self.browser.click(sel, user_id)
        await asyncio.sleep(3.0)

        confirmation = await self.browser.screenshot(user_id)
        return {"status": "submitted", "confirmation_screenshot": confirmation}
