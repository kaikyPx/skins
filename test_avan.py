import sys
import os
from playwright.sync_api import sync_playwright

# Add current directory to path to import src
sys.path.append(os.getcwd())

from src.scrapers.avan import AvanScraper

def on_item_found(item):
    print(f"FOUND: {item.name} - {item.price} - {item.float_value}")

def test_avan():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        scraper = AvanScraper()
        # Search for Karambit Doppler between 0.01 and 0.07
        scraper.scrape(
            page, 
            on_item_found, 
            search_item="Karambit", 
            search_skin="Doppler",
            float_min=0.01,
            float_max=0.07
        )
        
        browser.close()

if __name__ == "__main__":
    test_avan()
