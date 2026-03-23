
import time
import re
from ..item import SkinItem

class SkinsMonkeyScraper:
    def __init__(self, page):
        self.page = page
        self.base_url = "https://skinsmonkey.com/trade"

    def scrape(self, item_name, search_skin=None, search_style=None, min_float=0.0, max_float=1.0, stattrak=False):
        print(f"Iniciando scrape no SkinsMonkey para: {item_name}, Skin: {search_skin}, Estilo: {search_style}")
        self.page.goto(self.base_url)
        print("Página carregada. Aguardando 5 segundos...")
        time.sleep(5)
        
        # Search
        try:
            print("Procurando campo de busca...")
            # The search input is in the "SITE" inventory section (right side)
            # Use the inventory-toolbar with type="SITE" to get the correct search input
            search_input = self.page.wait_for_selector('.inventory-toolbar[type="SITE"] .search-input input[placeholder="Search inventory…"]', timeout=10000)
            if search_input:
                print("Campo de busca encontrado. Clicando e digitando...")
                search_input.click()
                time.sleep(0.5)
                
                # Combine item_name with style if provided
                search_query = item_name
                if search_style:
                    search_query += f" {search_style}"
                
                search_input.fill(search_query)  # Use fill instead of type for faster input
                print(f"Texto digitado: '{search_query}'. Aguardando resultados dinâmicos (5s)...")
                time.sleep(5) # Wait for dynamic results
            else:
                print("Campo de busca não encontrado.")
                return []
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []

        items = []
        try:
            print("Procurando cards de itens...")
            # Wait for at least one card or timeout
            self.page.wait_for_selector('.item-card', timeout=5000)
            cards = self.page.query_selector_all('.item-card')
            print(f"Encontrados {len(cards)} cards.")

            for card in cards:
                try:
                    # Name & Image
                    # Try specific class first, then generic img
                    img_elem = card.query_selector('img.item-image')
                    if not img_elem:
                        img_elem = card.query_selector('img')
                    
                    if not img_elem:
                         print("Imagem não encontrada no card.")
                         continue
                    
                    name_part = img_elem.get_attribute("alt")
                    image = img_elem.get_attribute("src")
                    
                    if not image:
                        # Try data-src or srcset if src is missing (lazy load)
                        image = img_elem.get_attribute("data-src") or img_elem.get_attribute("srcset")
                    
                    if not image:
                        print(f"URL da imagem não encontrada para: {name_part}")
                        image = "https://via.placeholder.com/150" # Fallback placeholder

                    # FILTERING: Extract skin name from full name and check if it matches search_skin
                    if search_skin:
                        # Full name format: "★ Karambit | Doppler Phase 1 (Factory New)"
                        # We need to extract the skin part after "|" and before "("
                        # Split by "|" to get the skin part
                        if "|" in name_part:
                            skin_part = name_part.split("|")[1].split("(")[0].strip()
                        else:
                            skin_part = name_part.split("(")[0].strip()
                        
                        print(f"DEBUG: Full name: '{name_part}'")
                        print(f"DEBUG: Extracted skin_part: '{skin_part}'")
                        print(f"DEBUG: search_skin: '{search_skin}'")
                        print(f"DEBUG: '{search_skin.strip().lower()}' in '{skin_part.lower()}' = {search_skin.strip().lower() in skin_part.lower()}")
                        
                        # Check if the skin part contains the search_skin
                        # Ex: search_skin="Doppler", skin_part="Doppler Phase 1" -> MATCH
                        # Ex: search_skin="Doppler", skin_part="Gamma Doppler Emerald" -> MATCH (contains "Doppler")
                        if search_skin.strip().lower() not in skin_part.lower():
                             print(f"Skipping item: '{name_part}' (Skin part '{skin_part}' does not contain '{search_skin}')")
                             continue
                    
                    # Construct full name from alt attribute
                    # The alt already contains the full name like "★ Karambit | Doppler Phase 1 (Factory New)"
                    full_name = name_part

                    # Price
                    price_elem = card.query_selector('.item-price')
                    if price_elem:
                        price_text = price_elem.inner_text().replace("$", "").replace(",", "").replace(".", "")
                        # The price format is like "$ 2,224.47" where the last part after dot is in a span
                        # We need to extract both parts
                        try:
                            # Try to get the span content for decimal part
                            decimal_span = price_elem.query_selector('span')
                            if decimal_span:
                                decimal_part = decimal_span.inner_text()
                                # Remove the decimal part from the main text
                                main_part = price_text.replace(decimal_part, "")
                                price = float(f"{main_part}.{decimal_part}")
                            else:
                                price = float(price_text)
                        except:
                            price = 0.0
                    else:
                        price = 0.0

                    # Float value extraction from CSS variable
                    float_value = None
                    float_elem = card.query_selector('.item-float')
                    if float_elem:
                        style_attr = float_elem.get_attribute("style")
                        if style_attr:
                            # Extract --float-value from style attribute
                            # Example: "--float-background-color: #56524d; --float-value: 5.46%; --float-range-start: 0%; --float-range-end: 8%;"
                            # The --float-value is the ACTUAL float value as a percentage (e.g., 5.46% = 0.0546 float)
                            # The range values are just for visual display on the bar
                            float_match = re.search(r'--float-value:\s*([\d.]+)%', style_attr)
                            if float_match:
                                # Simply divide by 100 to get the actual float value
                                float_value = float(float_match.group(1)) / 100.0
                                print(f"DEBUG: Extracted float from CSS: {float_match.group(1)}% = {float_value}")

                    # FILTRO STATTRAK
                    is_stattrak = "StatTrak" in full_name
                    if not stattrak and is_stattrak:
                        print(f"DEBUG: Item {full_name} ignorado - StatTrak e filtro OFF")
                        continue

                    # Float Filtering
                    print(f"DEBUG: float_value = {float_value}, min_float = {min_float}, max_float = {max_float}")
                    if float_value is not None:
                        if float_value < min_float or float_value > max_float:
                            print(f"DEBUG: Rejecting item due to float filter: {float_value} not in range [{min_float}, {max_float}]")
                            continue
                        else:
                            print(f"DEBUG: Item passed float filter: {float_value} in range [{min_float}, {max_float}]")
                    else:
                        print(f"DEBUG: No float value found for item, using default 0.0")

                    items.append(SkinItem(
                        site="skinsmonkey",
                        name=full_name,
                        float_value=float_value if float_value is not None else 0.0,
                        price=price,
                        url=self.base_url, 
                        image_url=image
                    ))

                except Exception as e:
                    print(f"Erro ao processar card SkinsMonkey: {e}")
                    continue

        except Exception as e:
            print(f"Erro geral no scraper SkinsMonkey: {e}")

        return items
