import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test offset pagination
        print("Testing offset=25")
        await page.goto("https://www.cv-library.co.uk/search-jobs?q=Estimator&geo=London&rad=50&offset=25", wait_until="domcontentloaded")
        cards = await page.locator("article.job, li.search-card, li.results__item, .job-search-description, h2 a[href*='/job/']").all()
        print(f"Found {len(cards)} cards on offset=25")
        
        if cards:
            print("First job title:", await cards[0].inner_text())
            
        print("Testing offset=50")
        await page.goto("https://www.cv-library.co.uk/search-jobs?q=Estimator&geo=London&rad=50&offset=50", wait_until="domcontentloaded")
        cards = await page.locator("article.job, li.search-card, li.results__item, .job-search-description, h2 a[href*='/job/']").all()
        print(f"Found {len(cards)} cards on offset=50")
        if cards:
            print("First job title:", await cards[0].inner_text())

        await browser.close()

asyncio.run(main())
