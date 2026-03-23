
import sys
import os
sys.path.append(os.getcwd())
from playwright.sync_api import sync_playwright
from src.scrapers.pirateswap import PirateSwapScraper

def test_pirateswap():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        scraper = PirateSwapScraper(page)
        
        # Test 1: Search for "Karambit Doppler" with strict filtering
        print("--- Test 1: Searching for 'Karambit Doppler' ---")
        items = scraper.scrape("Karambit Doppler", search_skin="Doppler")
        
        if items:
            print(f"Found {len(items)} items.")
            for item in items:
                print(f"Name: {item.name}")
                print(f"Price: {item.price}")
                print(f"Float: {item.float_value}")
                # Condition removed from SkinItem
                # print(f"Condition: {item.condition}")
                print("-" * 20)
        else:
            print("No items found.")
            
        print("\n--- Verification ---")
        if len(items) > 0:
            first = items[0]
            if "Doppler" in first.name and first.price > 0:
                print("SUCCESS: Items found and parsed correctly.")
            else:
                print("FAILURE: Items found but parsing might be incorrect.")
        else:
            print("FAILURE: No items found.")

        browser.close()

if __name__ == "__main__":
    test_pirateswap()
