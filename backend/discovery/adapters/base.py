from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
import uuid

class DiscoveredURL(BaseModel):
    url: str
    source: str
    discovered_at: datetime
    search_query: str
    title_hint: str
    
class DiscoveryAdapter(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.has_more_pages = True

    @abstractmethod
    async def discover(self, search_criteria: dict) -> List[DiscoveredURL]:
        """
        Executes a source-specific search and returns a list of standardized DiscoveredURL objects.
        The caller is responsible for deduplication across the overall session, 
        but the adapter should remove duplicates within its own result set.
        """
        pass
