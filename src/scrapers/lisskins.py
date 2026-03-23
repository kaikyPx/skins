from playwright.sync_api import Playwright, Page
from src.item import SkinItem
import time
import urllib.parse
import re

class LisSkinsScraper:
    def __init__(self):
        self.base_url = "https://lis-skins.com/market/csgo/"

    def scrape(
        self,
        playwright: Playwright,
        search_item: str,
        search_skin: str,
        search_style: str = "",
        float_min: float = 0.0,
        float_max: float = 1.0,
        user_data_dir="chrome_bot_profile",
        executable_path=None,
        on_item_found=None,
        cdp_url=None,
        stattrak_allowed: bool = False
    ):
        items = []
        # Construct Query
        # User requested: query={Item} {Skin}
        full_query = f"{search_item} {search_skin}".strip()
        
        # Lis-Skins parameters:
        # query: search text
        # price_from, price_to: (optional, not requested but good to know)
        # float_from, float_to: float range
        
        params = {
            "query": full_query,
            "float_from": str(float_min),
            "float_to": str(float_max)
        }
        
        query_string = urllib.parse.urlencode(params)
        search_url = f"{self.base_url}?{query_string}"
        
        print(f"[LisSkins] Searching for: {full_query} (Style: {search_style})")
        print(f"[LisSkins] Navigating to: {search_url}")

        context = None
        if cdp_url:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=executable_path,
                headless=False,
                viewport=None,
                args=["--start-maximized"]
            )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            print("[LisSkins] Abrindo site para verificação...")
            page.goto(search_url)
            print("[LisSkins] Aguardando 1:30 minuto para conclusão da verificação...")
            time.sleep(90)
            
            # Re-navega para estabilizar o contexto pós-verificação
            print("[LisSkins] Recarregando página pós-verificação...")
            page.goto(search_url)
            page.wait_for_load_state("load")
            time.sleep(5)
            
            # Wait for items to load
            print("[LisSkins] Buscando resultados...")
            
            try:
                page.wait_for_selector(".skins-market-skins-list .item", timeout=15000)
            except:
                print("[LisSkins] No items found or timeout.")
                return items
            
            time.sleep(3) # Extra buffer for dynamic content

            target_items = []

            while True:
                # Extract items from current page
                card_elements = page.query_selector_all(".skins-market-skins-list .item")
                print(f"[LisSkins] Found {len(card_elements)} items on current page.")

                for card in card_elements:
                    try:
                        # Name
                        name_el = card.query_selector(".name-inner")
                        if not name_el: continue
                        full_name = name_el.inner_text().strip()
                        
                        # Phase/Style Filtering
                        if "Doppler" in search_skin and "Gamma" not in search_skin:
                            if "Gamma Doppler" in full_name:
                                continue

                        if search_style:
                            s_style_norm = search_style.lower().replace(" ", "")
                            f_name_norm = full_name.lower().replace(" ", "")
                            if s_style_norm not in f_name_norm:
                                continue

                        # StatTrak Check
                        is_st = "StatTrak" in full_name
                        if not stattrak_allowed and is_st:
                            continue

                        # Image
                        image_url = ""
                        img_el = card.query_selector("img.image")
                        if img_el:
                            image_url = img_el.get_attribute("src")

                        # Link
                        item_url = ""
                        link_el = card.query_selector("a.name")
                        if link_el:
                            href = link_el.get_attribute("href")
                            if href:
                                if href.startswith("http"):
                                    item_url = href
                                else:
                                    item_url = f"https://lis-skins.com{href}"

                        if item_url and not any(t[0] == item_url for t in target_items):
                            target_items.append((item_url, full_name, image_url))
                            print(f"✅ [LisSkins] Link base identificado: {full_name}")

                    except Exception as e:
                        print(f"[LisSkins] Error parsing card: {e}")
                        continue

                # Pagination on Market Page
                next_btn = page.query_selector("ul.pagination li a[rel='next']")
                if next_btn:
                    print("[LisSkins] Moving to next page...")
                    time.sleep(3)
                    next_btn.click()
                    time.sleep(3)
                    try:
                        page.wait_for_selector(".skins-market-skins-list .item", timeout=10000)
                        time.sleep(3)
                    except:
                        print("[LisSkins] Timeout waiting for next page.")
                        break
                else:
                    print("[LisSkins] No more pages on market.")
                    break

            if not target_items:
                print("❌ [LisSkins] Nenhum card correspondente encontrado no market.")
                return items

            # Now visit detail pages to get actual listings
            for url, base_name, base_image in target_items:
                print(f"🚀 [LisSkins] Navegando para página de detalhes: {url}")
                page.goto(url)
                time.sleep(5)
                
                try:
                    page.wait_for_selector(".market_item", timeout=10000)
                except:
                    print(f"⚠️ [LisSkins] Nenhum item disponível na página de detalhes ou timeout.")
                    continue

                # Scroll to load more items if there are any lazy-loaded
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1)

                market_items = page.query_selector_all(".market_item")
                print(f"👀 [LisSkins] {len(market_items)} listagens totais nesta página de detalhes.")

                for m_item in market_items:
                    try:
                        price_el = m_item.query_selector(".price")
                        if not price_el: continue
                        price_text = price_el.inner_text().replace("$", "").replace(" ", "").strip()
                        price = float(price_text)

                        float_el = m_item.query_selector(".float")
                        if not float_el: continue
                        f_val = float(float_el.inner_text().strip())

                        if f_val < float_min or f_val > float_max:
                            continue

                        new_item = SkinItem(
                            site="LisSkins",
                            name=base_name,
                            float_value=f_val,
                            price=price,
                            url=url,
                            image_url=base_image
                        )
                        
                        items.append(new_item)
                        if on_item_found:
                            on_item_found(new_item)
                            
                        print(f"✅ [LisSkins] Found Details: {base_name} - ${price} (Float: {f_val})")

                    except Exception as e:
                        pass

        except Exception as e:
            print(f"❌ [LisSkins] Scraper error: {e}")
        
        return items
