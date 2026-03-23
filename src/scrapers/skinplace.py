
import time
import re
from playwright.sync_api import Page
from src.item import SkinItem

class SkinPlaceScraper:
    def __init__(self, page: Page):
        self.page = page
        self.base_url = "https://skin.place"

    def scrape(self, item_name, style=None):
        print(f"[SkinPlace] Iniciando busca por: {item_name} | Filtro de Estilo: {style}")
        search_url = f"{self.base_url}/en/buy-cs2-skins?search={item_name.replace(' ', '%20')}"
        
        try:
            self.page.goto(search_url)
            self.page.wait_for_selector("div.item-buy-card", timeout=30000)
        except Exception as e:
            print(f"[SkinPlace] Erro ao carregar página de busca: {e}")
            return []

        # Get all skin type cards from the search results
        # These are aggregate cards (e.g., "Karambit Doppler Phase 1", "Karambit Doppler Ruby")
        # We need to collect their URLs first to avoid stale elements when navigating back and forth
        product_links = []
        try:
            cards = self.page.locator("div.item-buy-card").all()
            print(f"[SkinPlace] Encontrados {len(cards)} cards de tipos de skin.")
            
            for card in cards:
                try:
                    # Apply style filter if requested
                    if style:
                        card_text = card.inner_text()
                        if style.lower() not in card_text.lower():
                            continue # Skip if style (e.g. "Phase 1") is not in card text
                    
                    link_el = card.locator("a").first
                    href = link_el.get_attribute("href")
                    if href:
                        full_url = self.base_url + href if href.startswith("/") else href
                        product_links.append(full_url)
                except Exception as e:
                    print(f"[SkinPlace] Erro ao extrair link do card: {e}")
        except Exception as e:
            print(f"[SkinPlace] Erro ao listar cards: {e}")
            return []

        all_skins = []
        
        # Iterate through each skin type page
        for url in product_links:
            try:
                print(f"[SkinPlace] Navegando para: {url}")
                self.page.goto(url)
                
                # Wait for the main content or offers table
                # We check for .item-title (name) or .offers-table
                try:
                    self.page.wait_for_selector("div.item-page", timeout=10000)
                except:
                    print(f"[SkinPlace] Timeout esperando página do item: {url}")
                    continue

                # IMPORTANT: 5-second delay as requested
                time.sleep(5)

                # Extract basic info from the main page header
                try:
                    # Name construction
                    # h1.item-title__name -> "★ Karambit Doppler Phase 3"
                    # Structure: 
                    # <h1 class="item-title__name">
                    #   ★ Karambit
                    #   <span> Doppler</span>
                    #   <span class="item-title__phase ...">Phase 3</span>
                    # </h1>
                    name_el = self.page.locator("h1.item-title__name")
                    full_name = name_el.inner_text().replace('\n', ' ').strip()
                    
                    # Clean up name (remove extra spaces)
                    full_name = re.sub(r'\s+', ' ', full_name)
                    print(f"[SkinPlace] Processando skin: {full_name}")
                except Exception as e:
                    print(f"[SkinPlace] Erro ao extrair nome do item: {e}")
                    full_name = item_name # Fallback

                # Now scrape the offers table for specific items with floats
                offers = self.page.locator("div.offer-item").all()
                print(f"[SkinPlace] Encontradas {len(offers)} ofertas.")

                for offer in offers:
                    try:
                        # Extract float
                        float_val = "N/A"
                        float_el = offer.locator(".float-stripe__number")
                        if float_el.count() > 0:
                            float_val = float_el.inner_text().strip()
                        
                        # Extract price
                        price_val = "0.00" # Default
                        price_el = offer.locator(".offer-item__price")
                        if price_el.count() > 0:
                            raw_price = price_el.inner_text()
                            # Price text might be like "$ 1 500.00 -18%"
                            clean_price = raw_price.replace('\xa0', ' ').strip() 
                            
                            # Extract number sequence. Use stricter regex to avoid matching newlines if possible,
                            # or just clean up afterwards.
                            price_match = re.search(r'[\d\s.,]+', clean_price)
                            if price_match:
                                number_str = price_match.group(0)
                                # Remove ALL whitespace (spaces, newlines, tabs)
                                number_str = re.sub(r'\s+', '', number_str)
                                
                                # Verify format. If it has comma and dot, assume dot is decimal if it's last
                                # If it has only comma, replace with dot
                                number_str = number_str.replace(',', '.')
                                # If multiple dots (e.g. 1.500.00), keep only the last one
                                if number_str.count('.') > 1:
                                    parts = number_str.split('.')
                                    number_str = "".join(parts[:-1]) + "." + parts[-1]
                                    
                                price_val = number_str

                        # Check for trade lock
                        trade_lock = "Tradable"
                        lock_el = offer.locator(".offer-item__trade-lock .info-label__title")
                        if lock_el.count() > 0:
                            trade_lock = lock_el.inner_text().strip()

                        # Image (thumbnail)
                        image_url = ""
                        img_el = offer.locator(".offer-item__image img")
                        if img_el.count() > 0:
                            image_url = img_el.get_attribute("src")

                        # Create SkinItem
                        try:
                            if float_val in ["Unavailable", "N/A"]:
                                print(f"  > Pular oferta: Float {float_val}")
                                continue
                            float_v = float(float_val)
                        except ValueError:
                            print(f"  > Pular oferta: Erro ao converter float '{float_val}'")
                            continue
                            
                        try:
                            price_v = float(price_val)
                        except ValueError:
                            price_v = 0.0 # extra safety
                        
                        skin = SkinItem(
                            site="SkinPlace",
                            name=full_name,
                            float_value=float_v,
                            price=price_v,
                            url=url,
                            image_url=image_url
                        )
                        
                        print(f"  > Oferta: Float {float_val} | Preço {price_val} | Lock: {trade_lock}")
                        all_skins.append(skin)

                    except Exception as e:
                        print(f"[SkinPlace] Erro ao processar oferta: {e}")

            except Exception as e:
                print(f"[SkinPlace] Erro ao processar URL {url}: {e}")

        return all_skins
