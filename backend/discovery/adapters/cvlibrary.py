import asyncio
from typing import List, Optional
import logging
import re
import random
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from backend.discovery.adapters.base import DiscoveryAdapter, DiscoveredURL
from backend.discovery.models import DiscoveredJob
from backend.browser.pool import browser_pool

logger = logging.getLogger(__name__)

class CVLibraryAdapter(DiscoveryAdapter):
    def __init__(self):
        super().__init__(source_name="cvlibrary")
        self.p = None
        self.browser = None
        self.context = None
        self.page = None
        self.base_search_url = None
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
        """Safely extract inner text from a locator."""
        try:
            loc = element.locator(selector).first
            if await loc.count() > 0:
                return (await loc.inner_text()).strip()
        except Exception:
            pass
        return None

    async def discover_jobs(self, search_criteria: dict, job_queue: asyncio.Queue = None) -> List[DiscoveredJob]:
        page_jobs = []
        job_titles = search_criteria.get("job_titles", [])
        industries = search_criteria.get("industries", [])
        
        import string
        
        # Flatten titles
        clean_titles = []
        for t in job_titles:
            parts = re.split(r'\s+or\s+', t, flags=re.IGNORECASE)
            for p in parts:
                p = p.strip().strip('"').strip("'")
                if p:
                    clean_titles.append(string.capwords(p) if p.islower() else p)
            
        title_query = ", ".join(clean_titles)
        
        # Append Sector/Industry
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
                
        location = search_criteria.get("location", "London")
        page_num = search_criteria.get("page", 1)
        posted_date = search_criteria.get("posted_dates", {}).get("CV-Library", search_criteria.get("posted_date", "Last 28 days"))
        
        print(f"[CVLibraryAdapter] Query: '{title_query}' | Location: '{location}' | Date: '{posted_date}' | Page: {page_num}")

        try:
            if page_num == 1:
                self.has_more_pages = True
                print("[CVLibraryAdapter] Retrieving context from BrowserPool...")
                self.context = await browser_pool.get_context()
                self.page = await self.context.new_page()
                await Stealth().apply_stealth_async(self.page)

                print(f"[CVLibraryAdapter] Navigating to homepage to initialize session...")
                await self.page.goto("https://www.cv-library.co.uk/", wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(2)
                
                try:
                    cookie_btn = self.page.locator("button:has-text('Accept'), button#save, iframe").locator("button").first
                    if await cookie_btn.count() > 0:
                        await cookie_btn.click(timeout=2000)
                        await asyncio.sleep(1)
                except Exception:
                    pass

                print(f"[CVLibraryAdapter] Filling search form...")
                what_input = self.page.get_by_placeholder("What", exact=False).first
                if await what_input.count() > 0:
                    await what_input.fill(title_query)
                else:
                    await self.page.locator("input[name='q'], input#keywords").first.fill(title_query)

                where_input = self.page.get_by_placeholder("Where", exact=False).first
                if await where_input.count() > 0:
                    await where_input.fill(location)
                else:
                    await self.page.locator("input[name='geo'], input#location").first.fill(location)

                radius = search_criteria.get("radius", 15)
                try:
                    dist_select = self.page.locator("select[name='distance']").first
                    if await dist_select.count() > 0:
                        valid_radiuses = [1, 2, 5, 7, 10, 15, 20, 25, 35, 50, 75, 100, 250, 500, 750]
                        try:
                            user_radius = int(radius)
                            closest_radius = min(valid_radiuses, key=lambda x: abs(x - user_radius))
                        except:
                            closest_radius = 15
                            
                        print(f"[CVLibraryAdapter] Mapping radius {radius} to closest valid option: {closest_radius} miles")
                        try:
                            await dist_select.select_option(value=str(closest_radius), timeout=2000)
                        except:
                            pass
                except Exception as e:
                    print(f"[CVLibraryAdapter] Could not set distance: {e}")

                find_btn = self.page.locator("button:has-text('Find Jobs'), input[type='submit']").first
                await find_btn.click()

                print(f"[CVLibraryAdapter] Submitted search. Waiting for results...")
                await self.page.wait_for_load_state("domcontentloaded", timeout=45000)
                await asyncio.sleep(5)
                
                print("[CVLibraryAdapter] Applying advanced filters safely via query parameters...")
                
                posted_val = ""
                pd_lower = posted_date.lower()
                if "24" in pd_lower or "1 day" in pd_lower:
                    posted_val = "1"
                elif "2" in pd_lower:
                    posted_val = "2"
                elif "3" in pd_lower:
                    posted_val = "3"
                elif "7" in pd_lower:
                    posted_val = "7"
                elif "14" in pd_lower:
                    posted_val = "14"
                elif "30" in pd_lower or "28" in pd_lower:
                    posted_val = "28"
                    
                current_url = self.page.url
                separator = "&" if "?" in current_url else "?"
                # Safely append query parameters without rewriting the path!
                filtered_url = f"{current_url}{separator}tempperm%5B%5D=Permanent"
                if posted_val:
                    filtered_url += f"&posted={posted_val}"
                    
                print(f"[CVLibraryAdapter] Navigating to filtered URL: {filtered_url}")
                await self.page.goto(filtered_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(5)
                
                self.base_search_url = self.page.url
                print(f"[CVLibraryAdapter] Final URL: {self.base_search_url}")
            else:
                print(f"[CVLibraryAdapter] Navigating to page {page_num} via Next button...")
                try:
                    # Human-like delay and scrolling before next page
                    delay = random.uniform(3.5, 6.5)
                    print(f"[CVLibraryAdapter] Bypassing anti-bot: Waiting {delay:.1f}s before page {page_num}...")
                    await self.page.evaluate("window.scrollBy(0, document.body.scrollHeight/2)")
                    await asyncio.sleep(delay)
                    
                    # Look for the Next button using Native JavaScript (Bypasses Playwright's CSS/Visibility checks)
                    try:
                        # Proactively close the cookie banner if it reappeared
                        try:
                            await self.page.evaluate("""
                                const btn = Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes('Accept all') || el.textContent.includes('Accept'));
                                if (btn) btn.click();
                            """)
                        except: pass
                        
                        await self.page.evaluate(f"""
                            let nextBtn = document.querySelector('a[rel="next"], a.pagination__next, #nav-next');
                            if (!nextBtn) {{
                                nextBtn = document.querySelector('a[href*="offset={(page_num - 1) * 20}"], a[href*="page={page_num}"]');
                            }}
                            if (!nextBtn) {{
                                const allLinks = Array.from(document.querySelectorAll('a, button'));
                                nextBtn = allLinks.find(el => el.textContent && el.textContent.toLowerCase().includes('next'));
                            }}
                            if (nextBtn) {{
                                nextBtn.click();
                            }} else {{
                                throw new Error('Next button not found in DOM');
                            }}
                        """)
                        await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                        await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                        await asyncio.sleep(4)
                    except Exception as click_err:
                        print("[CVLibraryAdapter] Next button not found natively, navigating via window.location.href to preserve session context...")
                        if not self.base_search_url:
                            self.base_search_url = self.page.url
                        paginated_url = re.sub(r'&page=\d+', '', self.base_search_url)
                        paginated_url = re.sub(r'&offset=\d+', '', paginated_url)
                        separator = "&" if "?" in paginated_url else "?"
                        offset = (page_num - 1) * 20
                        paginated_url = f"{paginated_url}{separator}offset={offset}"
                        
                        # Use Javascript location.href instead of playwright goto to prevent Cloudflare from detecting an automated navigation
                        await self.page.evaluate(f"window.location.href = '{paginated_url}';")
                        await self.page.wait_for_load_state("domcontentloaded", timeout=45000)
                        await asyncio.sleep(4)
                except Exception as e:
                    print(f"[CVLibraryAdapter] Pagination error: {e}")
                    return []

            # Find all job cards. CV-Library typically uses <li class="search-card"> or <article class="job">
            cards = await self.page.locator("article.job, li.search-card, li.results__item").all()
            
            # Anti-bot Retry Mechanism
            if not cards and page_num > 1:
                print(f"[CVLibraryAdapter] Found 0 cards on page {page_num}! Potential anti-bot wall. Retrying with delay...")
                await asyncio.sleep(8)
                await self.page.reload(wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(5)
                cards = await self.page.locator("article.job, li.search-card, li.results__item").all()
            if not cards:
                print("[CVLibraryAdapter] Fallback card selector...")
                link_cards = await self.page.locator("h2 a[href*='/job/']").all()
                cards = []
                for link in link_cards:
                    parent = link.locator("xpath=./ancestor::article | ./ancestor::li | ./ancestor::div[contains(@class, 'job')]").first
                    if await parent.count() > 0:
                        cards.append(parent)
                    else:
                        cards.append(link)
            
            print(f"[CVLibraryAdapter] Found {len(cards)} job cards on page {page_num}")
            
            if len(cards) == 0:
                print("[CVLibraryAdapter] Saving debug screenshot to cvlibrary_debug.png...")
                await self.page.screenshot(path="cvlibrary_debug.png")
                self.has_more_pages = False

            source_counts = search_criteria.get("source_counts", {})
            processed_count = 0
            new_jobs_on_page = 0
            for card in cards:
                try:
                    title_el = card.locator("h2, .job__title, .job-title").first
                    if await title_el.count() > 0:
                        title = await title_el.inner_text()
                    else:
                        title = await card.inner_text()
                        
                    if not title or not title.strip():
                        continue
                        
                    link_el = card.locator("a").first
                    if await link_el.count() == 0:
                        link_el = card
                        
                    job_url = await link_el.get_attribute("href")
                    if job_url and not job_url.startswith("http"):
                        job_url = "https://www.cv-library.co.uk" + job_url
                        
                    if job_url in self.seen_job_urls:
                        print(f"[CVLibraryAdapter] Skipping duplicate job on this page: {job_url}")
                        continue
                    
                    self.seen_job_urls.add(job_url)
                    new_jobs_on_page += 1
                        
                    location = await self._safe_text(card, ".job__location, .location, dd.location") or location
                    
                    # PRE-CLASSIFICATION: Check the card text before wasting a page load!
                    card_text = await card.text_content() or await card.inner_text()
                    card_text_lower = card_text.lower()
                    
                    # Safely grab image alt texts without grabbing raw HTML class names
                    try:
                        imgs = await card.locator("img").all()
                        for img in imgs:
                            alt = await img.get_attribute("alt")
                            if alt:
                                card_text_lower += f" {alt.lower()}"
                    except Exception:
                        pass
                    
                    # Extract company name from card (e.g., "Posted today by Company Name")
                    company_name = "Unknown Company"
                    match = re.search(r'by\s+([^\n]+)', card_text, re.IGNORECASE)
                    if match:
                        company_name = match.group(1).strip()
                        
                    # PRE-CLASSIFICATION 1: Agency/Recruitment Check
                    agency_keywords = ["recruitment", "resourcing", "staffing", "agency"]
                    is_agency = any(kw in card_text_lower for kw in agency_keywords)
                    
                    if is_agency:
                        print(f"[CVLibraryAdapter] PRE-CLASSIFIED UNFIT: Skipping '{title.strip()}' - Detected agency/recruitment keywords in card!")
                        continue
                        
                    # PRE-CLASSIFICATION 2: Job Title Match
                    if clean_titles:
                        title_lower = title.lower()
                        title_matched = any(ct.lower() in title_lower for ct in clean_titles)
                        if not title_matched:
                            print(f"[CVLibraryAdapter] PRE-CLASSIFIED UNFIT: Skipping '{title.strip()}' - Title does not match requirements.")
                            continue
                        
                    print(f"[CVLibraryAdapter] Extracting details for: {title.strip()} at {company_name}")
                    
                    full_text = ""
                    if job_url and job_url != "Unknown":
                        new_page = await self.context.new_page()
                        try:
                            await asyncio.sleep(random.uniform(1.0, 2.0))
                            await new_page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                            desc_loc = new_page.locator(".job-description, .job__description, article")
                            if await desc_loc.count() > 0:
                                full_text = await desc_loc.inner_text()
                            else:
                                full_text = await new_page.locator("body").inner_text()
                        except Exception as e:
                            logger.warning(f"Error extracting {job_url}: {e}")
                        finally:
                            await new_page.close()
                        if not full_text:
                            continue

                    # Generate job object
                    job_obj = DiscoveredJob(
                        job_title=title.strip() or "Unknown",
                        company_name=company_name,
                        location=location,
                        job_site="CV-Library",
                        job_url=job_url,
                        source="cvlibrary",
                        date_posted=datetime.now(timezone.utc).isoformat(),
                        match_score=0,
                        reason_for_match="Direct match from CV-Library search",
                        industry_match="Construction",
                        full_text=full_text
                    )
                    
                    if job_queue:
                        await job_queue.put(job_obj)
                    
                    page_jobs.append(job_obj)
                        
                    processed_count += 1
                    
                    delay = random.uniform(2.0, 3.0)
                    print(f"[CVLibraryAdapter] Waiting {delay:.1f}s before next job...")
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    print(f"[CVLibraryAdapter] Error processing card: {e}")
                    
            if new_jobs_on_page == 0 and len(cards) > 0:
                print("[CVLibraryAdapter] All jobs on this page have already been seen. Reached true end of results.")
                return []
                    
        except Exception as e:
            print(f"[CVLibraryAdapter] Critical Error: {e}")
            
        print(f"[CVLibraryAdapter] Finished scraping page. Found {len(page_jobs)} valid jobs.")
        return page_jobs

    async def discover(self, search_criteria: dict) -> List[DiscoveredURL]:
        """Legacy URL-only method, delegates to discover_jobs."""
        jobs = await self.discover_jobs(search_criteria)
        return [
            DiscoveredURL(
                url=j.job_url,
                source="cvlibrary",
                discovered_at=datetime.now(timezone.utc),
                search_query=str(search_criteria.get("job_titles", [])),
                title_hint=j.job_title
            )
            for j in jobs
        ]
