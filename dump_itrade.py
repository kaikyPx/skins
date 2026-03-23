
from playwright.sync_api import sync_playwright
import time

def dump_itrade():
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            # Try to find the itrade page
            page = None
            for p_obj in context.pages:
                if "itrade.gg" in p_obj.url:
                    page = p_obj
                    break
            
            if not page:
                print("iTrade page not found. Opening it...")
                page = context.new_page()
                page.goto("https://itrade.gg/trade/csgo")
                time.sleep(5)
            
            print(f"Current URL: {page.url}")
            
            # Dump one card HTML
            card = page.query_selector('button:has(img)')
            if card:
                print("--- CARD HTML ---")
                print(card.outer_html())
            else:
                print("No card found with 'button:has(img)'")
                # Try a more generic selector
                all_buttons = page.query_selector_all('button')
                print(f"Found {len(all_buttons)} buttons. Testing one...")
                if all_buttons:
                    print(all_buttons[0].outer_html())
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    dump_itrade()
