import asyncio
from typing import List
import logging
from backend.discovery.adapters.linkedin import LinkedInAdapter
from backend.discovery.adapters.indeed import IndeedAdapter
from backend.discovery.models import DiscoveredJob

logger = logging.getLogger(__name__)

from backend.discovery.adapters.cvlibrary import CVLibraryAdapter

class DiscoveryOrchestrator:
    def __init__(self, platforms: List[str] = None):
        self.adapters = []
        platforms = platforms or ["CV-Library"]
        
        if "CV-Library" in platforms:
            self.adapters.append(CVLibraryAdapter())
        if "Indeed" in platforms:
            self.adapters.append(IndeedAdapter())
        if "LinkedIn" in platforms:
            self.adapters.append(LinkedInAdapter())

    async def execute_discovery(self, search_criteria: dict, job_queue: asyncio.Queue = None) -> List[DiscoveredJob]:
        """
        Executes discovery across all configured adapters concurrently.
        Returns a deduplicated list of DiscoveredJob objects.
        Pushes jobs to job_queue as they are found.
        """
        logger.info(f"Starting discovery across {len(self.adapters)} sources.")
        
        tasks = []
        for adapter in self.adapters:
            if getattr(adapter, 'has_more_pages', True):
                tasks.append(adapter.discover_jobs(search_criteria, job_queue))
                
        if not tasks:
            return []
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_jobs: List[DiscoveredJob] = []
        seen_urls = set()
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"An adapter failed: {result}")
            else:
                for job in result:
                    if job.job_url not in seen_urls:
                        seen_urls.add(job.job_url)
                        all_jobs.append(job)
                        
        logger.info(f"Discovery completed. Found {len(all_jobs)} unique jobs.")
        return all_jobs

discovery_orchestrator = DiscoveryOrchestrator()
