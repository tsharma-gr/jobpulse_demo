import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')
        
        await page.goto('https://www.cv-library.co.uk/search-jobs?q=Estimator&geo=United+Kingdom', wait_until='domcontentloaded')
        await asyncio.sleep(4)
        
        # Try to find the Next button
        next_btn = await page.locator("a:has-text('Next'), a.pagination__next, a[rel='next'], a.next").all()
        print(f"Found {len(next_btn)} Next buttons.")
        for btn in next_btn:
            try:
                print("Next URL:", await btn.get_attribute("href"))
                print("Next text:", await btn.inner_text())
                print("Next class:", await btn.get_attribute("class"))
            except:
                pass
                
        await browser.close()

asyncio.run(main())
