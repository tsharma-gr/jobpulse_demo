import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.cv-library.co.uk/")
        
        selects = await page.locator("select").all()
        for i, s in enumerate(selects):
            name = await s.get_attribute("name")
            print(f"Select {i}: name={name}")
            options = await s.locator("option").all()
            for opt in options:
                val = await opt.get_attribute("value")
                text = await opt.inner_text()
                print(f"  val='{val}', text='{text}'")
            
        await browser.close()

asyncio.run(main())
