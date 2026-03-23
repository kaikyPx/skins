import time
import re
from src.item import SkinItem


class SkinportScraper:
    def __init__(self):
        self.base_url = "https://skinport.com/pt/market"
    
    def scrape(
        self, 
        playwright, 
        search_item, 
        search_skin, 
        search_style="", 
        float_min=0.0, 
        float_max=1.0, 
        stattrak_allowed=False,
        on_item_found=None,
        user_data_dir="chrome_bot_profile", 
        executable_path=None, 
        cdp_url=None
    ):
        """
        Scrape items from Skinport.com
        """
        items = []
        
        # Construct search URL
        # Example: https://skinport.com/pt/market?search=Karambit+Doppler
        search_query = f"{search_item} {search_skin}".strip().replace(" ", "+")
        if search_query:
            search_url = f"{self.base_url}?search={search_query}"
        else:
            search_url = self.base_url
        
        # Connect to browser via CDP
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
        
        print(f"[Skinport] Parâmetros: Item='{search_item}', Skin='{search_skin}', Estilo='{search_style}', Float={float_min}-{float_max}")
        
        try:
            print(f"[Skinport] Navegando para: {search_url}")
            page.goto(search_url, wait_until="networkidle")
            
            # Wait for dynamic content
            print("[Skinport] Aguardando 5 segundos para carregar...")
            time.sleep(5)
            
            print("[Skinport] Aguardando seletor de cards...")
            try:
                page.wait_for_selector("div.CatalogPage-item", timeout=15000)
            except:
                print("[Skinport] Nenhum item encontrado ou página não carregou cards.")
                return []
            
            # --- Sidebar Style Selection ---
            if search_style:
                try:
                    print(f"[Skinport] Tentando selecionar estilo no menu lateral: {search_style}")
                    # Find the "Fase" filter wrapper
                    fase_filter = page.locator(".FilterWrapper", has_text=re.compile(r"Fase", re.IGNORECASE))
                    if fase_filter.count() > 0:
                        # Expand if not already opened
                        class_attr = fase_filter.get_attribute("class") or ""
                        if "FilterWrapper--opened" not in class_attr:
                            print("[Skinport] Abrindo menu 'Fase'...")
                            fase_filter.locator(".FilterWrapper-header").click()
                            time.sleep(1)
                        
                        # Check if it's a searchable dropdown (based on user feedback)
                        search_input = fase_filter.locator("input.rc-select-selection-search-input")
                        if search_input.count() > 0:
                            print(f"[Skinport] Usando campo de busca para estilo: {search_style}")
                            search_input.first.click()
                            search_input.first.fill(search_style)
                            time.sleep(1)
                            # Wait for results and click the first one
                            # Specific to rc-select: result list is usually at the bottom of body
                            # but sometimes selecting by text works
                            page.keyboard.press("Enter")
                            time.sleep(3)
                            
                            # Wait for cards to reload
                            page.wait_for_selector("div.CatalogPage-item", timeout=10000)
                        else:
                            # Fallback to checkbox search
                            option = fase_filter.locator(".Checkbox-label", has_text=re.compile(fr"{search_style}", re.IGNORECASE))
                            if option.count() > 0:
                                print(f"[Skinport] Aplicando filtro de estilo via checkbox: {search_style}")
                                option.first.click()
                                time.sleep(3)
                                page.wait_for_selector("div.CatalogPage-item", timeout=10000)
                            else:
                                print(f"[Skinport] ⚠️ Estilo '{search_style}' não encontrado no menu lateral.")
                    else:
                        print("[Skinport] ⚠️ Filtro 'Fase' não encontrado lateralmente.")
                except Exception as e:
                    print(f"[Skinport] Erro ao interagir com filtro de estilo: {e}")
            # -------------------------------
            
            # Get initial card count
            last_card_count = 0
            scroll_attempts = 0
            max_scrolls = 25 # Increased for safety
            
            print("[Skinport] Rolando para carregar todos os itens...")
            while scroll_attempts < max_scrolls:
                # Scroll to bottom
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                current_cards = page.query_selector_all("div.CatalogPage-item")
                current_count = len(current_cards)
                print(f"[Skinport] Itens carregados: {current_count}")
                
                if current_count == last_card_count:
                    break
                
                last_card_count = current_count
                scroll_attempts += 1

            # Get final list of item cards
            cards = page.query_selector_all("div.CatalogPage-item")
            print(f"[Skinport] Total final: {len(cards)} cards")
            
            for idx, card in enumerate(cards, 1):
                try:
                    print(f"\n[Skinport] ========== CARD {idx}/{len(cards)} ==========")
                    # Extract item title (e.g., "Karambit ★")
                    item_title_elem = card.query_selector("div.ItemPreview-itemTitle")
                    item_title = item_title_elem.inner_text().strip() if item_title_elem else ""
                    
                    # Extract item name (e.g., "Doppler")
                    item_name_elem = card.query_selector("div.ItemPreview-itemName")
                    item_name = item_name_elem.inner_text().strip() if item_name_elem else ""
                    
                    # Check for version badge (Phase 1, 2, 3, 4)
                    badge_elem = card.query_selector(".ItemVersionBadge-value")
                    badge_val = badge_elem.inner_text().strip() if badge_elem else ""
                    
                    # If we have a badge, specifically format it as "Phase X" for better matching
                    if badge_val and "phase" not in item_name.lower():
                        # Avoid duplicates if inner_text already caught it
                        if badge_val in item_name:
                            item_name = item_name.replace(badge_val, f"Phase {badge_val}")
                        else:
                            item_name = f"{item_name} Phase {badge_val}"
                    
                    print(f"[Skinport] Item: '{item_title}' | Skin: '{item_name}'")

                    # Check for StatTrak
                    is_stattrak = "StatTrak" in item_title or "StatTrak" in item_name
                    if is_stattrak and not stattrak_allowed:
                        print(f"[Skinport] ❌ StatTrak detectado mas não permitido, pulando.")
                        continue

                    # Filter by style (Phase)
                    # For Skinport, style is often inside itemName or as a badge
                    full_name = f"{item_title} | {item_name}"
                    
                    if search_style:
                        # Extract phase if possible
                        style_match = False
                        if search_style.lower() in full_name.lower():
                            style_match = True
                        
                        if not style_match:
                            print(f"[Skinport] ❌ Estilo '{search_style}' não encontrado em '{full_name}', pulando.")
                            continue
                        else:
                            print(f"[Skinport] ✅ Estilo '{search_style}' encontrado.")

                    print(f"[Skinport] Nome completo: '{full_name}'")

                    # Extract price (comes in BRL based on HTML)
                    price_elem = card.query_selector("div.ItemPreview-priceValue div.Tooltip-link")
                    price_text = price_elem.inner_text().strip() if price_elem else "0,00 R$"
                    price_brl = self._parse_price(price_text)
                    
                    # Convert BRL to USD (Approximate rate: 5.0)
                    conversion_rate = 5.0
                    price_usd = round(price_brl / conversion_rate, 2)
                    print(f"[Skinport] Preço: {price_text} -> ${price_usd} USD")
                    
                    # Extract float value
                    float_elem = card.query_selector("div.WearBar-value")
                    if float_elem:
                        float_str = float_elem.inner_text().strip()
                        try:
                            float_value = float(float_str)
                        except ValueError:
                            float_value = 0.0
                    else:
                        float_value = 0.0
                    
                    print(f"[Skinport] Float: {float_value}")

                    # Filter by float
                    if not (float_min <= float_value <= float_max):
                        print(f"[Skinport] ❌ Float {float_value} fora do range [{float_min} - {float_max}], pulando.")
                        continue
                    else:
                        print(f"[Skinport] ✅ Float dentro do range.")

                    # Extract image URL
                    img_elem = card.query_selector("div.ItemPreview-itemImage img")
                    image_url = img_elem.get_attribute("src") if img_elem else ""
                    
                    # Extract item URL
                    link_elem = card.query_selector("a.ItemPreview-link")
                    if link_elem:
                        item_href = link_elem.get_attribute("href")
                        item_url = f"https://skinport.com{item_href}"
                    else:
                        item_url = search_url
                    
                    # Create SkinItem
                    skin_item = SkinItem(
                        site="Skinport",
                        name=full_name,
                        price=price_usd,
                        float_value=float_value,
                        image_url=image_url,
                        url=item_url
                    )
                    
                    if on_item_found:
                        on_item_found(skin_item)
                    
                    items.append(skin_item)
                    
                except Exception as e:
                    print(f"[Skinport] Erro ao processar card {idx}: {e}")
                    continue
            
            print(f"[Skinport] Total de itens extraídos: {len(items)}")
            
        except Exception as e:
            print(f"[Skinport] Erro durante scraping: {e}")
        
        # We don't close the browser if we're using a persistent context or CDP
        # but if we launched it temporarily, we should. 
        # For now, following DashSkins pattern (not closing here).
        
        return items

    def _parse_price(self, price_text):
        """
        Parse BRL price format from Skinport
        Example: "8.613,38 R$" -> 8613.38
        """
        try:
            # Remove "R$" and spaces
            price_clean = price_text.replace("R$", "").replace("\xa0", "").replace(" ", "").strip()
            # Remove thousand separators (.)
            price_clean = price_clean.replace(".", "")
            # Replace decimal comma with dot
            price_clean = price_clean.replace(",", ".")
            return float(price_clean)
        except (ValueError, AttributeError):
            return 0.0
