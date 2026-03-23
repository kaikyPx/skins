
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        # Use a user agent to look less like a bot
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
        
        await page.goto("https://avan.market/en/market/cs?name=Karambit+Doppler&float_min=0.01&float_max=0.07")
        try:
            print("Waiting 10s for items...")
            await asyncio.sleep(10)
            
            # Save screenshot
            await page.screenshot(path="d:/projetos/skins/avan_screenshot.png", full_page=True)
            print("Screenshot saved.")
            
            # Save HTML
            html = await page.content()
            with open("d:/projetos/skins/avan_dump.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("HTML dumped.")
            
            # Analyze elements on the fly
            elements = await page.evaluate('''() => {
                const items = Array.from(document.querySelectorAll('a[class*="marketProductCard_"]'));
                return items.map(el => ({
                    className: el.className,
                    text: el.innerText,
                    html: el.innerHTML.substring(0, 100)
                }));
            }''')
            print(f"Found {len(elements)} elements.")
            for i, el in enumerate(elements[:3]):
                print(f"Item {i}: className='{el['className']}', text='{el['text']}', html='{el['html']}'")
                
        except Exception as e:
            print(f"Error: {e}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
