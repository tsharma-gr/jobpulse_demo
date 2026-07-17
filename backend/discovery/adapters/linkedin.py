import asyncio
from typing import List, Optional
from datetime import datetime, timezone
import urllib.parse
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from backend.discovery.adapters.base import DiscoveryAdapter, DiscoveredURL
from backend.discovery.models import DiscoveredJob
from backend.browser.pool import browser_pool

logger = logging.getLogger(__name__)

class LinkedInAdapter(DiscoveryAdapter):
    def __init__(self):
        super().__init__(source_name="linkedin")
        self.seen_job_urls = set()
        self.has_more_pages = True

    async def _safe_text(self, element, selector: str) -> Optional[str]:
        """Safely extract inner text from a locator."""
        try:
            loc = element.locator(selector).first
            if await loc.count() > 0:
                return (await loc.inner_text()).strip()
        except Exception:
            pass
        return None

    async def discover_jobs(self, search_criteria: dict, job_queue: asyncio.Queue = None) -> List[DiscoveredJob]:
        job_titles = search_criteria.get("job_titles", [])
        industries = search_criteria.get("industries", [])
        
        import re
        import string
        
        clean_titles = []
        for t in job_titles:
            parts = re.split(r'\s+or\s+', t, flags=re.IGNORECASE)
            for p in parts:
                p = p.strip().strip('"').strip("'")
                if p:
                    clean_titles.append(string.capwords(p) if p.islower() else p)
            
        title_query = ", ".join(clean_titles)
        
        if industries:
            clean_inds = []
            for i in industries:
                parts = re.split(r'\s+or\s+', i, flags=re.IGNORECASE)
                for p in parts:
                    p = p.strip().strip('"').strip("'")
                    if p:
                        clean_inds.append(string.capwords(p) if p.islower() else p)
            ind_query = ", ".join(clean_inds)
            title_query = f"{title_query} AND {ind_query}"
                
        industry_label = ", ".join(industries) if industries else "General"
        
        page_num = search_criteria.get("page", 1)
        start_offset = (page_num - 1) * 25
        location = search_criteria.get("location", "United Kingdom")

        print(f"[LinkedInAdapter] Query: '{title_query}' | Location: '{location}'")

        jobs: List[DiscoveredJob] = []

        try:
            print(f"[LinkedInAdapter] Retrieving context from BrowserPool...")
            context = await browser_pool.get_context()
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            try:
                query_encoded = urllib.parse.quote(title_query)
                location_encoded = urllib.parse.quote(location)
                
                posted_date = search_criteria.get("posted_dates", {}).get("LinkedIn", search_criteria.get("posted_date", "Any time")).lower()
                f_tpr = ""
                if "24" in posted_date:
                    f_tpr = "&f_TPR=r86400"
                elif "week" in posted_date:
                    f_tpr = "&f_TPR=r604800"
                elif "month" in posted_date:
                    f_tpr = "&f_TPR=r2592000"
                
                search_url = (
                    f"https://www.linkedin.com/jobs/search/"
                    f"?keywords={query_encoded}"
                    f"&location={location_encoded}"
                    f"{f_tpr}"
                    f"&start={start_offset}"
                )
                print(f"[LinkedInAdapter] Navigating to page {page_num}: {search_url}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)

                # Dismiss login modal
                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    modal = page.locator("div.contextual-sign-in-modal").first
                    if await modal.is_visible(timeout=1500):
                        await page.mouse.click(779, 270)
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

                # Scroll to load more cards
                try:
                    for _ in range(4):
                        await page.evaluate("window.scrollBy(0, 600)")
                        await asyncio.sleep(1.2)
                except Exception as e:
                    print(f"[LinkedInAdapter] Scroll interrupted (likely auth wall redirect): {e}")

                # Get all job cards
                cards = await page.locator("ul.jobs-search__results-list > li").all()
                print(f"[LinkedInAdapter] Found {len(cards)} job cards")
                
                if len(cards) == 0:
                    self.has_more_pages = False
                    return jobs
                else:
                    self.has_more_pages = True

                new_jobs_on_page = 0
                for card in cards:
                    try:
                        # Extract fields from the card
                        title = await self._safe_text(card, ".base-search-card__title")
                        company = await self._safe_text(card, ".base-search-card__subtitle")
                        loc = await self._safe_text(card, ".job-search-card__location")
                        date_posted = await self._safe_text(card, "time")
                        
                        # Get the link
                        link_el = card.locator("a.base-card__full-link").first
                        job_url = ""
                        if await link_el.count() > 0:
                            href = await link_el.get_attribute("href")
                            job_url = href.split("?")[0] if href else ""

                        if not title or not job_url:
                            continue

                        # Check for duplicates
                        if job_url in self.seen_job_urls:
                            print(f"[LinkedInAdapter] Skipping duplicate job on this page: {title}")
                            continue
                            
                        self.seen_job_urls.add(job_url)
                        new_jobs_on_page += 1

                        # PRE-CLASSIFICATION: Agency/Recruitment Check
                        company_lower = (company or "").lower()
                        agency_keywords = ["recruitment", "resourcing", "staffing", "agency", "search", "talent"]
                        if any(kw in company_lower for kw in agency_keywords):
                            print(f"[LinkedInAdapter] PRE-CLASSIFIED UNFIT: Skipping '{title}' - Detected agency keywords in company name!")
                            continue
                            
                        print(f"[LinkedInAdapter] Extracting details for: {title.strip()}")
                            
                        # Click the card to load the description in the right pane
                        full_text = None
                        try:
                            if await link_el.count() > 0:
                                await link_el.evaluate("el => el.click()")
                            else:
                                await card.evaluate("el => el.click()")
                                
                            # Wait for the right pane to load
                            pane = page.locator(".show-more-less-html__markup, .description__text, .jobs-description").first
                            await pane.wait_for(state="visible", timeout=3000)
                            await asyncio.sleep(0.5)
                            
                            # Click "Show more" button if it exists
                            show_more_btn = page.locator("button.show-more-less-html__button").first
                            if await show_more_btn.is_visible(timeout=1000):
                                await show_more_btn.evaluate("el => el.click()")
                                await asyncio.sleep(0.5)
                                
                            if await pane.count() > 0:
                                full_text = await pane.text_content()
                        except Exception as e:
                            logger.warning(f"Could not extract full text for {title}: {e}")

                        # Generate reason for match
                        matched_titles = [t for t in job_titles if t.lower() in (title or "").lower()]
                        reason = f"Title matches '{matched_titles[0]}'" if matched_titles else f"Relevant to search terms"
                        if industry_label != "General":
                            reason += f" in {industry_label} sector"

                        job_obj = DiscoveredJob(
                            job_title=title or "Unknown",
                            company_name=company or "Unknown",
                            location=loc or location,
                            job_site="LinkedIn",
                            job_url=job_url,
                            date_posted=date_posted or "Recently",
                            job_type=None,  # LinkedIn doesn't show this on list view
                            industry_match=industry_label,
                            reason_for_match=reason,
                            match_score=85,
                            full_text=full_text
                        )
                        jobs.append(job_obj)
                        if job_queue:
                            await job_queue.put(job_obj)
                            
                    except Exception as e:
                        logger.warning(f"Error parsing card: {e}")

                await asyncio.sleep(3)  # Keep window open briefly
                
                if new_jobs_on_page == 0 and len(cards) > 0:
                    print("[LinkedInAdapter] All jobs on this page have already been seen. Reached true end of results.")
                    self.has_more_pages = False
                    return jobs

            except Exception as e:
                logger.error(f"[LinkedInAdapter] Error: {e}")
                print(f"[LinkedInAdapter] Error: {e}")
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if context:
                    await browser_pool.return_context(context)
        except Exception as e:
            logger.error(f"[LinkedInAdapter] Critical Error: {e}")
            print(f"[LinkedInAdapter] Critical Error: {e}")

        print(f"[LinkedInAdapter] Returning {len(jobs)} jobs")
        return jobs

    async def discover(self, search_criteria: dict) -> List[DiscoveredURL]:
        """Legacy URL-only method, delegates to discover_jobs."""
        jobs = await self.discover_jobs(search_criteria)
        from datetime import datetime, timezone
        from backend.discovery.adapters.base import DiscoveredURL
        return [
            DiscoveredURL(
                url=j.job_url,
                source="linkedin",
                discovered_at=datetime.now(timezone.utc),
                search_query=str(search_criteria.get("job_titles", [])),
                title_hint=j.job_title
            )
            for j in jobs
        ]
