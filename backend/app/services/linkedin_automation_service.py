"""
linkedin_automation_service.py — LinkedIn browser automation via PinchTab.

Handles: login, connection requests, message sending.
Uses human-like delays to avoid detection.
"""
import logging
import time
import random

from app.services.pinchtab_service import PinchTabClient, new_session

logger = logging.getLogger(__name__)

# Human-like delay range (seconds)
MIN_DELAY = 2.0
MAX_DELAY = 5.0


def _human_delay():
    """Random delay to mimic human behavior."""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def linkedin_login(user_id: str, email: str, password: str) -> PinchTabClient:
    """Login to LinkedIn via PinchTab browser automation.

    Returns authenticated PinchTabClient session.
    """
    session = new_session(user_id)
    try:
        session.navigate("https://www.linkedin.com/login")
        _human_delay()
        session.fill('input[name="session_key"]', email)
        _human_delay()
        session.fill('input[name="session_password"]', password)
        _human_delay()
        session.click('button[type="submit"]')
        time.sleep(4)  # Wait for login redirect
        logger.info("LinkedIn login initiated for user %s", user_id)
        return session
    except Exception as exc:
        logger.error("LinkedIn login failed for user %s: %s", user_id, exc)
        session.close()
        raise


def send_connection_request(
    session: PinchTabClient,
    profile_url: str,
    note: str = "",
) -> bool:
    """Send a LinkedIn connection request with optional note.

    Args:
        session: Authenticated PinchTabClient
        profile_url: LinkedIn profile URL of the target
        note: Personalized connection note (max 300 chars)

    Returns: True if request was sent successfully
    """
    try:
        session.navigate(profile_url)
        _human_delay()

        # Click "Connect" button
        session.click('button[aria-label*="Connect"], button[aria-label*="connect"]')
        _human_delay()

        if note:
            # Click "Add a note"
            session.click('button[aria-label*="Add a note"]')
            _human_delay()
            # Fill note (max 300 chars)
            session.fill('textarea[name="message"]', note[:300])
            _human_delay()

        # Click "Send"
        session.click('button[aria-label*="Send"], button[aria-label*="send"]')
        _human_delay()

        logger.info("Connection request sent to %s", profile_url)
        return True
    except Exception as exc:
        logger.warning("Connection request failed for %s: %s", profile_url, exc)
        return False


def send_linkedin_message(
    session: PinchTabClient,
    profile_url: str,
    message: str,
) -> bool:
    """Send a LinkedIn message to a 1st-degree connection.

    Args:
        session: Authenticated PinchTabClient
        profile_url: LinkedIn profile URL
        message: Message text to send

    Returns: True if message was sent
    """
    try:
        session.navigate(profile_url)
        _human_delay()

        # Click "Message" button
        session.click('button[aria-label*="Message"], button[aria-label*="message"]')
        _human_delay()

        # Type message in the message box
        session.fill('div[role="textbox"], textarea[name="message"]', message)
        _human_delay()

        # Click send
        session.click('button[type="submit"], button[aria-label*="Send"]')
        _human_delay()

        logger.info("Message sent to %s", profile_url)
        return True
    except Exception as exc:
        logger.warning("Message send failed for %s: %s", profile_url, exc)
        return False
