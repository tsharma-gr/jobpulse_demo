import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import List, Optional
from backend.config.settings import settings

class BrowserPool:
    """
    Manages a pool of Playwright browsers and contexts to minimize startup overhead.
    The lock is created lazily inside the running event loop, not at import time.
    """
    def __init__(self):
        self._playwright = None
        self._browsers: List[Browser] = []
        self._contexts: List[BrowserContext] = []
        self._lock: Optional[asyncio.Lock] = None
        self._initialized = False

    def _get_lock(self) -> asyncio.Lock:
        """Create lock lazily in the running event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def initialize(self):
        if self._initialized:
            return

        print("BrowserPool: launching Playwright + Chromium...")
        self._playwright = await async_playwright().start()

        for _ in range(settings.MAX_BROWSERS):
            browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--start-maximized"]
            )
            self._browsers.append(browser)

            # Pre-warm contexts
            per_browser = max(1, settings.MAX_CONTEXTS // settings.MAX_BROWSERS)
            for _ in range(per_browser):
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    )
                )
                # Block unnecessary assets to speed up scraping
                await context.route("**/*", lambda route: route.abort() 
                    if route.request.resource_type in ["image", "stylesheet", "font", "media"] 
                    else route.continue_())
                
                self._contexts.append(context)

        self._initialized = True
        print(f"BrowserPool: ready with {len(self._browsers)} browser(s), {len(self._contexts)} context(s).")

    async def get_context(self) -> BrowserContext:
        """
        Retrieves an available browser context from the pool.
        Pool must already be initialized via initialize().
        """
        lock = self._get_lock()
        async with lock:
            if self._contexts:
                ctx = self._contexts.pop()
                print(f"BrowserPool: handed out context. Remaining: {len(self._contexts)}")
                return ctx

            # Pool exhausted — create a new context on the first browser
            print("BrowserPool: pool exhausted, creating new context on-demand.")
            browser = self._browsers[0]
            context = await browser.new_context()
            return context

    async def return_context(self, context: BrowserContext):
        """
        Returns a context to the pool after clearing cookies.
        """
        lock = self._get_lock()
        async with lock:
            try:
                await context.clear_cookies()
            except Exception:
                pass

            if len(self._contexts) < settings.MAX_CONTEXTS:
                self._contexts.append(context)
                print(f"BrowserPool: context returned. Pool size: {len(self._contexts)}")
            else:
                await context.close()
                print("BrowserPool: pool full, context closed.")

    async def close(self):
        for ctx in self._contexts:
            try:
                await ctx.close()
            except Exception:
                pass
        for browser in self._browsers:
            try:
                await browser.close()
            except Exception:
                pass
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False
        self._lock = None
        print("BrowserPool: fully closed.")

browser_pool = BrowserPool()
