import asyncio
from typing import Optional
from crawl4ai import AsyncWebCrawler
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class Crawl4AIManager:
    """
    Manages job page extraction using Crawl4AI.
    """
    def __init__(self):
        self.crawler = AsyncWebCrawler()
        self.started = False

    async def start(self):
        if not self.started:
            await self.crawler.start()
            self.started = True

    async def extract_page(self, url: str) -> Optional[str]:
        """
        Extracts the main content of the URL and returns it as Markdown.
        """
        if not self.started:
            await self.start()
            
        try:
            logger.info(f"Extracting {url} via Crawl4AI")
            result = await self.crawler.arun(url=url, magic=True)
            return result.markdown
        except Exception as e:
            logger.error(f"Failed to extract {url}: {e}")
            return None

    async def close(self):
        if self.started:
            await self.crawler.close()
            self.started = False

crawler_manager = Crawl4AIManager()
