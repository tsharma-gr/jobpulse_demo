import asyncio
from typing import Callable, Dict, Any, Awaitable
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Token-bucket style rate limiter per source.
    Ensures we don't exceed max requests per minute.
    """
    def __init__(self, requests_per_minute: int):
        self.rate = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.tokens = requests_per_minute
        self.last_update = asyncio.get_event_loop().time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_update
            
            # Replenish tokens
            self.tokens = min(self.rate, self.tokens + elapsed / self.interval)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return
            else:
                # Wait until a token is available
                wait_time = self.interval - (self.tokens * self.interval)
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = asyncio.get_event_loop().time()

class SourceRateLimiters:
    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {
            "linkedin": RateLimiter(30), # 30 req/min
            "indeed": RateLimiter(20),   # 20 req/min
            "cvlibrary": RateLimiter(50) # 50 req/min
        }

    async def acquire(self, source: str):
        if source in self.limiters:
            await self.limiters[source].acquire()

rate_limiters = SourceRateLimiters()
