
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://avan.market/en/market/cs?name=Karambit+Doppler&float_min=0.01&float_max=0.07")
        try:
            print("Waiting for container...")
            await page.wait_for_selector('[class*="Market_marketArticlesContainer"]', timeout=30000)
            print("Waiting for cards...")
            await page.wait_for_selector('a[class*="marketProductCard_"]', timeout=30000)
            
            cards = await page.query_selector_all('a[class*="marketProductCard_"]')
            if cards:
                print(f"Found {len(cards)} cards.")
                card = cards[0]
                html = await card.inner_html()
                print("--- CARD HTML START ---")
                print(html)
                print("--- CARD HTML END ---")
                
                # Try to find text nodes
                text = await card.inner_text()
                print("--- CARD TEXT START ---")
                print(text)
                print("--- CARD TEXT END ---")
            else:
                print("No cards found.")
        except Exception as e:
            print(f"Error: {e}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
