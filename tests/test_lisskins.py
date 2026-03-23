import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.sync_api import sync_playwright
from src.scrapers.lisskins import LisSkinsScraper

def test_lisskins():
    scraper = LisSkinsScraper()
    item_name = "Karambit"
    skin_name = "Doppler"
    style = "Phase 1"
    
    print(f"Testing LisSkins Scraper with: {item_name} | {skin_name} ({style})")
    
    with sync_playwright() as p:
        items = scraper.scrape(
            playwright=p,
            search_item=item_name,
            search_skin=skin_name,
            search_style=style,
            float_min=0.0,
            float_max=0.07,
            stattrak_allowed=False
        )
        
        print(f"\nFound {len(items)} items:")
        for item in items:
            print(item)

if __name__ == "__main__":
    test_lisskins()
