"""
Shared helper for loading a saved Playwright session.

Usage in a scraper:
    from auth import new_authenticated_page

    async with async_playwright() as p:
        browser, page = await new_authenticated_page(p)
        # page is already logged in
        ...
        await browser.close()
"""

import sys
from pathlib import Path
from playwright.async_api import Playwright, Browser, Page

AUTH_STATE_PATH = Path("auth_state.json")


async def new_authenticated_page(p: Playwright, headless: bool = True, **context_kwargs) -> tuple[Browser, Page]:
    """
    Launch a browser context pre-loaded with the saved session from auth_state.json.
    Run `python login.py` first if auth_state.json does not exist.

    Pass extra keyword arguments to override context options, e.g.:
        new_authenticated_page(p, viewport={"width": 3000, "height": 1080})
    """
    if not AUTH_STATE_PATH.exists():
        print(
            f"ERROR: {AUTH_STATE_PATH} not found. "
            "Run `python login.py` first to create a saved session."
        )
        sys.exit(1)

    browser = await p.chromium.launch(headless=headless)
    context = await browser.new_context(storage_state=str(AUTH_STATE_PATH), **context_kwargs)
    page = await context.new_page()
    return browser, page
