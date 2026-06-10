"""
Run this script once to log in to fencingtimelive.com via Google.
It opens a real browser window — complete the Google sign-in manually,
then press Enter in this terminal. Your session is saved to auth_state.json
and reused by all scraper scripts automatically.

Usage:
    python login.py
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

AUTH_STATE_PATH = Path("auth_state.json")
LOGIN_URL = "https://www.fencingtimelive.com"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(LOGIN_URL)
        print("Browser opened. Please sign in with your Google account.")
        print("Once you are fully logged in, come back here and press Enter.")
        input("Press Enter to save session and exit...")

        await context.storage_state(path=str(AUTH_STATE_PATH))
        print(f"Session saved to {AUTH_STATE_PATH}.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
