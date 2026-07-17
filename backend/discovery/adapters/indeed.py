import asyncio
from typing import List, Optional
import urllib.parse
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from backend.discovery.adapters.base import DiscoveryAdapter, DiscoveredURL
from backend.discovery.models import DiscoveredJob
from backend.browser.pool import browser_pool

logger = logging.getLogger(__name__)

class IndeedAdapter(DiscoveryAdapter):
    def __init__(self):
        super().__init__(source_name="indeed")
        self.p = None
        self.browser = None
        self.context = None
        self.page = None
        self.seen_job_urls = set()

    async def close(self):
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
        if self.context:
            await browser_pool.return_context(self.context)
        
        self.page = None
        self.context = None

    async def _safe_text(self, element, selector: str) -> Optional[str]:
        try:
            loc = element.locator(selector).first
            if await loc.count() > 0:
                text = await loc.text_content()
                return text.strip() if text else None
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
        
        # Append Sector/Industry to the search query just like CV-Library
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
        start_offset = (page_num - 1) * 10
        location = search_criteria.get("location", "London")

        print(f"[IndeedAdapter] Query: '{title_query}' | Location: '{location}' | Page: {page_num}")

        jobs: List[DiscoveredJob] = []

        try:
            # For Indeed, we MUST use a brand new incognito context for every single page.
            # If we reuse the context, Indeed tracks that we viewed page 1 and throws a hard login wall on page 2.
            # By getting a fresh context, Indeed thinks we are a brand new user landing directly on page 2 from Google!
            if self.context:
                await self.page.close()
                await browser_pool.return_context(self.context)
                self.context = None
                self.page = None

            print(f"[IndeedAdapter] Retrieving fresh context from BrowserPool for page {page_num}...")
            self.context = await browser_pool.get_context()
            self.page = await self.context.new_page()
            await Stealth().apply_stealth_async(self.page)

            query_encoded = urllib.parse.quote(title_query)
            location_encoded = urllib.parse.quote(location)
            
            # Extract posted date from frontend criteria
            posted_date = search_criteria.get("posted_dates", {}).get("Indeed", search_criteria.get("posted_date", "All Dates"))
            pd_lower = posted_date.lower()
            fromage = ""
            if "24" in pd_lower or "1" in pd_lower:
                fromage = "1"
            elif "2" in pd_lower or "3" in pd_lower:
                fromage = "3"
            elif "7" in pd_lower:
                fromage = "7"
            elif "14" in pd_lower:
                fromage = "14"
            
            # Build search URL with Permanent job type (&jt=permanent) and Date Posted (&fromage=X)
            search_url = f"https://uk.indeed.com/jobs?q={query_encoded}&l={location_encoded}&sort=date&jt=permanent"
            if fromage:
                search_url += f"&fromage={fromage}"
            search_url += f"&start={start_offset}"
            
            print(f"[IndeedAdapter] Navigating to page {page_num}: {search_url}")
            
            # Since we have a fresh context, we just use standard goto
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

            # Dismiss Cloudflare / Modals if they exist (Human-like behavior)
            try:
                await self.page.mouse.move(300, 400)
                await asyncio.sleep(1)
                await self.page.mouse.move(450, 200)
                
                cookie_btn = self.page.locator("#onetrust-accept-btn-handler").first
                if await cookie_btn.is_visible(timeout=2000):
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Dismiss Login walls/popups
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                
                # Check for Google Sign-in iframe
                frames = self.page.frames
                for frame in frames:
                    if "smartlock" in frame.url or "google" in frame.url:
                        close_btn = frame.locator('div[role="button"][aria-label="Close"], button[aria-label="Close"]').first
                        if await close_btn.count() > 0:
                            await close_btn.click(force=True)
                            await asyncio.sleep(0.5)
                            
                # Check for Indeed's own login walls
                close_btn = self.page.locator('button[aria-label="Close"], button[aria-label="close"], button.css-15h2e6k, #mosaic-modal-close-button').first
                if await close_btn.is_visible(timeout=1000):
                    await close_btn.click(force=True)
                    await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[IndeedAdapter] Error closing modal: {e}")

            # Scroll to load job cards slowly
            for _ in range(5):
                await self.page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1.5)

            # Extract Indeed job cards
            cards = await self.page.locator(".job_seen_beacon").all()
            print(f"[IndeedAdapter] Found {len(cards)} job cards on page {page_num}")
            
            if len(cards) == 0:
                self.has_more_pages = False
                screenshot_path = f"indeed_debug_page_{page_num}.png"
                print(f"[IndeedAdapter] Saving debug screenshot to {screenshot_path}")
                await self.page.screenshot(path=screenshot_path)
                return jobs
            else:
                self.has_more_pages = True

            source_counts = search_criteria.get("source_counts", {})
            new_jobs_on_page = 0
            
            for card in cards:
                try:
                    title = await self._safe_text(card, ".jobTitle span[title]") or await self._safe_text(card, ".jobTitle") or await self._safe_text(card, "h2") or await self._safe_text(card, "h3")
                    
                    link_el = card.locator("a.jcs-JobTitle").first
                    if await link_el.count() == 0:
                        link_el = card.locator("a").first
                        
                    job_url = ""
                    jk = None
                    if await link_el.count() > 0:
                        href = await link_el.get_attribute("href")
                        jk = await link_el.get_attribute("data-jk")
                        if jk:
                            job_url = f"https://uk.indeed.com/viewjob?jk={jk}"
                        elif href and "jk=" in href:
                            import urllib.parse as urlparse
                            parsed = urlparse.urlparse(href)
                            qs = urlparse.parse_qs(parsed.query)
                            if "jk" in qs:
                                jk = qs['jk'][0]
                                job_url = f"https://uk.indeed.com/viewjob?jk={jk}"
                            else:
                                job_url = "https://uk.indeed.com" + href if href.startswith("/") else href
                        elif href:
                            job_url = "https://uk.indeed.com" + href if href.startswith("/") else href

                    # Check for duplicates
                    if job_url in self.seen_job_urls:
                        print(f"[IndeedAdapter] Skipping duplicate job on this page: {title}")
                        continue

                    # Skip honeypot fake jobs designed to trap bots
                    if jk == "fedcba9876543210" or "fedcba" in job_url:
                        print(f"[IndeedAdapter] Skipping anti-bot honeypot job: {title}")
                        continue

                    if not title or not job_url:
                        continue
                        
                    self.seen_job_urls.add(job_url)
                    new_jobs_on_page += 1

                    company = await self._safe_text(card, "[data-testid='company-name']") or await self._safe_text(card, ".companyName") or "Company"
                    loc = await self._safe_text(card, "[data-testid='text-location']") or await self._safe_text(card, ".companyLocation") or location
                    date_posted = await self._safe_text(card, "[data-testid='myJobsStateDate']") or await self._safe_text(card, ".date")
                    clean_url = job_url.split("&vjs=")[0]
                    
                    # PRE-CLASSIFICATION: Agency/Recruitment Check to save AI credits
                    card_text = await card.text_content() or await card.inner_text()
                    card_text_lower = card_text.lower()
                    agency_keywords = ["recruitment", "resourcing", "staffing", "agency"]
                    is_agency = any(kw in card_text_lower for kw in agency_keywords)
                    
                    if is_agency or any(kw in company.lower() for kw in agency_keywords):
                        print(f"[IndeedAdapter] PRE-CLASSIFIED UNFIT: Skipping '{title.strip()}' - Detected agency/recruitment keywords in card or company name!")
                        continue
                    
                    print(f"[IndeedAdapter] Extracting details for: {title.strip()}")
                    
                    full_text = None
                    try:
                        # Click the title text to trigger the right pane without causing a full page navigation
                        title_loc = card.locator(".jobTitle").first
                        if await title_loc.count() > 0:
                            await title_loc.click()
                        else:
                            await card.click()
                        
                        desc_loc = self.page.locator("#jobDescriptionText").first
                        await desc_loc.wait_for(state="visible", timeout=4000)
                        
                        import random
                        delay = random.uniform(2.0, 3.0)
                        print(f"[IndeedAdapter] Waiting {delay:.1f}s for text rendering...")
                        await asyncio.sleep(delay)
                        
                        if await desc_loc.count() > 0:
                            full_text = await desc_loc.text_content()
                    except Exception as e:
                        print(f"[IndeedAdapter] Could not extract full text for {title}: {e}")
                        # If a navigation happened accidentally, try to go back
                        if "viewjob" in self.page.url:
                            print("[IndeedAdapter] Accidentally navigated away. Going back to search results...")
                            await self.page.go_back(wait_until="domcontentloaded")
                            await asyncio.sleep(2)

                    matched_titles = [t for t in job_titles if t.lower() in (title or "").lower()]
                    reason = f"Title matches '{matched_titles[0]}'" if matched_titles else f"Relevant to search terms"
                    if industry_label != "General":
                        reason += f" in {industry_label} sector"

                    job_obj = DiscoveredJob(
                        job_title=title or "Unknown",
                        company_name=company or "Unknown",
                        location=loc or location,
                        job_site="Indeed",
                        job_url=clean_url,
                        date_posted=date_posted or "Recently",
                        job_type=None,
                        industry_match=industry_label,
                        reason_for_match=reason,
                        match_score=85,
                        full_text=full_text
                    )
                    
                    if job_queue:
                        await job_queue.put(job_obj)
                        
                    jobs.append(job_obj)
                    
                except Exception as e:
                    print(f"[IndeedAdapter] Error parsing Indeed card: {e}")

                await asyncio.sleep(2)

            if new_jobs_on_page == 0 and len(cards) > 0:
                print("[IndeedAdapter] All jobs on this page have already been seen. Reached true end of results.")
                self.has_more_pages = False
                return jobs

        except Exception as e:
            print(f"[IndeedAdapter] Critical Error: {e}")
            
        print(f"[IndeedAdapter] Finished scraping page.")

        print(f"[IndeedAdapter] Returning {len(jobs)} jobs")
        return jobs

    async def discover(self, search_criteria: dict) -> List[DiscoveredURL]:
        """Legacy URL-only method."""
        jobs = await self.discover_jobs(search_criteria)
        from datetime import datetime, timezone
        from backend.discovery.adapters.base import DiscoveredURL
        return [
            DiscoveredURL(
                url=j.job_url,
                source="indeed",
                discovered_at=datetime.now(timezone.utc),
                search_query=str(search_criteria.get("job_titles", [])),
                title_hint=j.job_title
            )
            for j in jobs
        ]
