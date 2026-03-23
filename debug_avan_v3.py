
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
        
        await page.goto("https://avan.market/en/market/cs?name=Karambit+Doppler&float_min=0.01&float_max=0.07")
        try:
            print("Waiting for any item...")
            await page.wait_for_selector('text=Doppler', timeout=30000)
            print("FOUND Doppler text!")
            
            # Find the element and its parent chain
            info = await page.evaluate('''() => {
                const results = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.includes('Doppler')) {
                        let parent = node.parentElement;
                        results.push({
                            text: node.textContent,
                            parentClass: parent.className,
                            grandParentClass: parent.parentElement ? parent.parentElement.className : '',
                            tag: parent.tagName
                        });
                    }
                }
                return results;
            }''')
            print(f"Details of elements with 'Doppler': {info}")
            
        except Exception as e:
            print(f"Error: {e}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
