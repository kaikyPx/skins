import time
import re
from src.item import SkinItem


class DashSkinsScraper:
    def __init__(self):
        self.base_url = "https://dashskins.gg/"
    
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
        Scrape items from DashSkins.gg
        
        Args:
            playwright: Playwright instance
            search_item: Item name (e.g., "Karambit")
            search_skin: Skin name (e.g., "Doppler")
            search_style: Style/Phase (e.g., "Phase 4")
            float_min: Minimum float value
            float_max: Maximum float value
            stattrak_allowed: Whether StatTrak items are included
            on_item_found: Callback function for each item found
            user_data_dir: Chrome user data directory
            executable_path: Chrome executable path
            cdp_url: Chrome DevTools Protocol URL
        
        Returns:
            List of SkinItem objects
        """
        items = []
        
        # Construct search URL
        # Example: https://dashskins.gg/?partialMarketHashName=Karambit+Doppler
        search_query = f"{search_item} {search_skin} {search_style}".strip().replace(" ", "+")
        if search_query:
            search_url = f"{self.base_url}?partialMarketHashName={search_query}"
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
        
        print(f"[DashSkins] Parâmetros: Item='{search_item}', Skin='{search_skin}', Estilo='{search_style}', Float={float_min}-{float_max}")
        
        try:
            print(f"[DashSkins] Navegando para: {search_url}")
            page.goto(search_url, wait_until="networkidle")
            
            # Wait for dynamic content to load - 10 seconds as confirmed
            print("[DashSkins] Aguardando 10 segundos para carregar...")
            time.sleep(10)
            
            print("[DashSkins] Aguardando seletor de cards...")
            try:
                page.wait_for_selector("div.itemCard_availableCard__abUPV", timeout=15000)
            except:
                print("[DashSkins] Nenhum item encontrado ou página não carregou cards.")
                return []
            
            # Get all item cards
            cards = page.query_selector_all("div.itemCard_availableCard__abUPV")
            print(f"[DashSkins] Encontrados {len(cards)} cards")
            
            for idx, card in enumerate(cards, 1):
                try:
                    print(f"\n[DashSkins] ========== CARD {idx}/{len(cards)} ==========")
                    
                    # Extract skin name
                    skin_name_elem = card.query_selector("span.text-body-2-bold.text-ellipsis.overflow-hidden")
                    skin_name = skin_name_elem.inner_text().strip() if skin_name_elem else ""
                    
                    # Extract item type (e.g., "Knives | Karambit")
                    item_type_elem = card.query_selector("span.text-caption-bold.text-neutral-5")
                    item_type = item_type_elem.inner_text().strip() if item_type_elem else ""
                    
                    print(f"[DashSkins] Item: '{item_type}' | Skin: '{skin_name}'")

                    # Check for StatTrak in name or type
                    is_stattrak = "StatTrak" in skin_name or "StatTrak" in item_type
                    if is_stattrak and not stattrak_allowed:
                        print(f"[DashSkins] ❌ StatTrak detectado mas não permitido, pulando.")
                        continue

                    # Filter by style if search_style is provided
                    if search_style:
                        if search_style.lower() not in skin_name.lower():
                            print(f"[DashSkins] ❌ Estilo '{search_style}' não encontrado em '{skin_name}', pulando.")
                            continue
                        else:
                            print(f"[DashSkins] ✅ Estilo '{search_style}' encontrado.")

                    # Combine to create full name: "Karambit | Doppler (Phase 4)"
                    if item_type and skin_name:
                        item_parts = item_type.split("|")
                        if len(item_parts) >= 2:
                            weapon_name = item_parts[1].strip()
                            full_name = f"{weapon_name} | {skin_name}"
                        else:
                            full_name = f"{item_type} | {skin_name}"
                    else:
                        full_name = skin_name or item_type or "Unknown Item"
                    
                    print(f"[DashSkins] Nome completo: '{full_name}'")

                    # Extract price (comes in BRL)
                    price_elem = card.query_selector("span.text-body-2-bold.text-neutral-8")
                    price_text = price_elem.inner_text().strip() if price_elem else "R$ 0,00"
                    price_brl = self._parse_price(price_text)
                    
                    # Convert BRL to USD (Approximate rate: 5.0)
                    conversion_rate = 5.0
                    price_usd = round(price_brl / conversion_rate, 2)
                    print(f"[DashSkins] Preço: {price_text} -> ${price_usd} USD")
                    
                    # Extract float value
                    float_elem = card.query_selector("div[data-tooltip-content]")
                    if float_elem:
                        float_str = float_elem.get_attribute("data-tooltip-content")
                        try:
                            float_value = float(float_str) if float_str else 0.0
                        except ValueError:
                            match = re.search(r"0\.\d+", float_str)
                            float_value = float(match.group()) if match else 0.0
                    else:
                        float_value = 0.0
                    
                    print(f"[DashSkins] Float: {float_value}")

                    # Filter by float
                    if not (float_min <= float_value <= float_max):
                        print(f"[DashSkins] ❌ Float {float_value} fora do range [{float_min} - {float_max}], pulando.")
                        continue
                    else:
                        print(f"[DashSkins] ✅ Float dentro do range.")

                    # Extract image URL
                    img_elem = card.query_selector("img[alt='loading...']")
                    image_url = img_elem.get_attribute("src") if img_elem else ""
                    if image_url and not image_url.startswith("http"):
                        image_url = f"https://dashskins.gg{image_url}"
                    
                    # Extract item URL
                    link_elem = card.query_selector("a[href^='/item/']")
                    if link_elem:
                        item_href = link_elem.get_attribute("href")
                        item_url = f"https://dashskins.gg{item_href}"
                    else:
                        item_url = search_url
                    
                    # Create SkinItem
                    skin_item = SkinItem(
                        site="DashSkins",
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
                    print(f"[DashSkins] Erro ao processar card {idx}: {e}")
                    continue
            
            print(f"[DashSkins] Total de itens extraídos: {len(items)}")
            
        except Exception as e:
            print(f"[DashSkins] Erro durante scraping: {e}")
        
        finally:
            if not cdp_url and context:
                context.close()
        
        return items
    
    def _parse_price(self, price_text):
        """
        Parse Brazilian price format to float
        Example: "R$ 9.500,00" -> 9500.00
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
